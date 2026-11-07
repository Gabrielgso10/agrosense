// AgroSense — nó de borda. A câmera identifica a espécie de cada vaso, o nó decide
// a irrigação localmente com o perfil da espécie e a nuvem recebe só telemetria por
// MQTT, inclusive a foto da bancada. Com sono profundo (padrão), o nó acorda a cada
// período de amostragem, decide, publica e volta a dormir. Sem rede, tudo continua.
#include <sys/time.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <type_traits>

#include "esp_attr.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "img_converters.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#include "actuators.h"
#include "app_config.h"
#include "camera.h"
#include "classifier.h"
#include "cycle.h"
#include "irrigation.h"
#include "model_settings.h"
#include "preprocess.h"
#include "sensors.h"
#include "species.h"
#include "telemetry.h"

using namespace agrosense;

namespace {

const char* TAG = "agrosense";
uint8_t g_crop[kInputWidth * kInputHeight * kInputChannels];  // recorte 96x96 RGB888

// Estado que precisa sobreviver ao sono profundo: fica na memória RTC. Os tipos são
// triviais e a inicialização é constante, então nenhum construtor roda sobre ele a
// cada despertar (o que apagaria a espécie confirmada e o horário da última rega).
struct NodeState {
  uint32_t magic = 0;
  uint32_t cycles = 0;
  int64_t last_vision_s = 0;
  PotState pots[kNumPots];
  SpeciesTracker trackers[kNumPots];
  float last_confidence[kNumPots] = {};
};
static_assert(std::is_trivially_copyable<NodeState>::value, "NodeState precisa caber na memória RTC");
constexpr uint32_t kStateMagic = 0xA6E05E02;  // muda junto com o layout: força partida limpa

#if defined(__cpp_constinit)
#define AGROSENSE_CONSTINIT constinit
#else
#define AGROSENSE_CONSTINIT
#endif
RTC_DATA_ATTR AGROSENSE_CONSTINIT NodeState g_state;

// Mensagens do ciclo: a decisão não espera a rede; elas saem quando houver conexão.
struct Message {
  char topic[40];
  char json[384];
  MessagePolicy policy;
};
constexpr int kOutboxSize = kNumPots + 2;  // um estado por vaso + ambiente + legenda da foto
Message g_outbox[kOutboxSize];
int g_outbox_count = 0;

// Última foto da bancada em JPEG e o que a câmera viu em cada vaso
uint8_t* g_photo = nullptr;
size_t g_photo_len = 0;
int g_frame_width = 0;
int g_frame_height = 0;
int g_seen[kNumPots];

Message* NextSlot() { return g_outbox_count < kOutboxSize ? &g_outbox[g_outbox_count++] : nullptr; }

void DropPhoto() {
  free(g_photo);
  g_photo = nullptr;
  g_photo_len = 0;
}

void SendQueued() {
  if (g_photo != nullptr) {
    TelemetryPublishBinary("agrosense/camera", g_photo, static_cast<int>(g_photo_len), 0, true);
    DropPhoto();
  }
  for (int i = 0; i < g_outbox_count; ++i) {
    TelemetryPublish(g_outbox[i].topic, g_outbox[i].json, g_outbox[i].policy.qos, g_outbox[i].policy.retain);
  }
  g_outbox_count = 0;
}

// Segundos desde a partida; a hora do sistema continua contando no sono profundo.
int64_t NowSeconds() {
  timeval tv;
  gettimeofday(&tv, nullptr);
  return static_cast<int64_t>(tv.tv_sec);
}

void InitNvs() {
  esp_err_t err = nvs_flash_init();  // exigido pelo Wi-Fi
  if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    ESP_ERROR_CHECK(nvs_flash_erase());
    err = nvs_flash_init();
  }
  ESP_ERROR_CHECK(err);
}

void ClassifyPots(Classifier& classifier, bool keep_photo) {
  camera_fb_t* fb = CameraCapture();
  if (fb == nullptr) {
    ESP_LOGW(TAG, "Sem quadro da câmera nesta rodada");
    return;
  }
  g_frame_width = static_cast<int>(fb->width);
  g_frame_height = static_cast<int>(fb->height);
  for (int p = 0; p < kNumPots; ++p) {
    if (!CropResizeRgb565(fb->buf, g_frame_width, g_frame_height, kPotRois[p], kInputWidth, g_crop,
                          kRgb565BigEndian)) {
      ESP_LOGE(TAG, "Vaso %d: região fora do quadro (ajuste kPotRois)", p);
      continue;
    }
    const Prediction pr = classifier.Classify(g_crop);
    const int confirmed = g_state.trackers[p].Update(pr.index, pr.confidence);
    g_seen[p] = pr.index;
    g_state.last_confidence[p] = pr.confidence;
    ESP_LOGI(TAG, "Vaso %d: viu '%s' (%.0f%%, %.0f ms) | espécie confirmada: %s", p,
             pr.index >= 0 ? kLabels[pr.index] : "?", 100.0 * static_cast<double>(pr.confidence),
             static_cast<double>(classifier.last_latency_us()) / 1000.0,
             confirmed >= 0 ? kLabels[confirmed] : "nenhuma");
  }
  if (keep_photo) {
    DropPhoto();
    if (!frame2jpg(fb, static_cast<uint8_t>(kPhotoJpegQuality), &g_photo, &g_photo_len)) {
      g_photo = nullptr;
      g_photo_len = 0;
      ESP_LOGW(TAG, "Não foi possível converter a foto para JPEG");
    }
  }
  CameraRelease(fb);
}

// Legenda da foto: a região de cada vaso no quadro e o que a câmera viu nela.
void QueueCameraInfo() {
  Message* m = NextSlot();
  if (m == nullptr) return;
  snprintf(m->topic, sizeof(m->topic), "agrosense/camera/info");
  const int cap = static_cast<int>(sizeof(m->json));
  int used = snprintf(m->json, sizeof(m->json), "{\"largura\":%d,\"altura\":%d,\"vasos\":[", g_frame_width,
                      g_frame_height);
  for (int p = 0; p < kNumPots && used >= 0 && used < cap; ++p) {
    const int seen = g_seen[p];
    used += snprintf(m->json + used, static_cast<size_t>(cap - used),
                     "%s{\"vaso\":%d,\"x\":%d,\"y\":%d,\"lado\":%d,\"visto\":\"%s\",\"confianca\":%.2f}",
                     p > 0 ? "," : "", p, kPotRois[p].x, kPotRois[p].y, kPotRois[p].size,
                     seen >= 0 ? kLabels[seen] : "", static_cast<double>(g_state.last_confidence[p]));
  }
  if (used >= 0 && used < cap) snprintf(m->json + used, static_cast<size_t>(cap - used), "]}");
  m->policy = {0, true};  // retida: o painel sempre tem a legenda da última foto
}

// Lê o solo, aplica a lei de controle de cada vaso e enfileira a telemetria.
// Retorna true se alguma bomba ficou ligada.
bool RunControl(int64_t now_s, bool report_all) {
  const bool tank_ok = TankOk();
  bool any_pump_on = false;
  for (int p = 0; p < kNumPots; ++p) {
    float volts = 0.0f;
    const bool read_ok = ReadSoilVolts(kPotSoilChannel[p], &volts);
    const int soil = read_ok ? SoilPercent(volts, kSoilDryVolts[p], kSoilWetVolts[p]) : -1;
    const bool fixed = kFixedSpecies[p] != nullptr;
    const char* label = ResolveSpeciesLabel(kFixedSpecies[p], g_state.trackers[p].confirmed(), kLabels, kNumClasses);
    const SpeciesProfile* profile = FindProfile(label);
    const Thresholds limits = profile != nullptr ? ThresholdsFromFao(profile->depletion_p, kSoilFieldCapacityPct[p],
                                                                     kSoilWiltingPct[p])
                                                 : Thresholds{-1, -1};
    const bool was_on = g_state.pots[p].pump_on;
    const Decision d = StepPot(g_state.pots[p], {profile, limits, soil >= 0, soil, tank_ok, now_s});
    SetPump(p, d.pump_on);
    any_pump_on = any_pump_on || d.pump_on;

    const bool changed = d.pump_on != was_on;
    if (!report_all && !changed) continue;
    ESP_LOGI(TAG, "Vaso %d (%s%s): solo %d%% (%.2f V) | liga abaixo de %d%%, desliga em %d%% | bomba %s | %s", p,
             label != nullptr ? label : "sem espécie", fixed ? ", fixa" : "", soil, static_cast<double>(volts),
             limits.low, limits.high, d.pump_on ? "LIGADA" : "desligada", ReasonName(d.reason));
    if (Message* m = NextSlot()) {
      snprintf(m->topic, sizeof(m->topic), "agrosense/vaso/%d", p);
      snprintf(m->json, sizeof(m->json),
               "{\"vaso\":%d,\"especie\":\"%s\",\"fixa\":%s,\"confianca\":%.2f,\"solo_pct\":%d,"
               "\"liga_abaixo\":%d,\"desliga_em\":%d,\"bomba\":%s,\"motivo\":\"%s\"}",
               p, label != nullptr ? label : "", fixed ? "true" : "false",
               static_cast<double>(g_state.last_confidence[p]), soil, limits.low, limits.high,
               d.pump_on ? "true" : "false", ReasonName(d.reason));
      m->policy = PotMessagePolicy(changed);
    }
  }
  if (report_all) {
    const Environment env = ReadEnvironment();
    if (Message* m = NextSlot()) {
      snprintf(m->topic, sizeof(m->topic), "agrosense/ambiente");
      snprintf(m->json, sizeof(m->json),
               "{\"temperatura_c\":%.1f,\"umidade_ar_pct\":%.1f,\"lux\":%.0f,\"reservatorio_ok\":%s,\"sensores_ok\":%s}",
               static_cast<double>(env.temperature_c), static_cast<double>(env.humidity_pct),
               static_cast<double>(env.lux), tank_ok ? "true" : "false", env.valid ? "true" : "false");
      m->policy = {0, false};
    }
  }
  return any_pump_on;
}

}  // namespace

extern "C" void app_main(void) {
  ActuatorsInit();  // primeiro: bombas desligadas e travas do sono profundo liberadas
  InitNvs();

  const bool cold_boot = g_state.magic != kStateMagic;
  if (cold_boot) {
    g_state = NodeState();
    g_state.magic = kStateMagic;
    for (int p = 0; p < kNumPots; ++p) g_state.trackers[p] = SpeciesTracker(kSpeciesConfirmations, kMinConfidence);
  }
  for (int p = 0; p < kNumPots; ++p) g_seen[p] = -1;
  ++g_state.cycles;
  ESP_LOGI(TAG, "%s | ciclo %u", cold_boot ? "Partida a frio" : "Despertou do sono profundo",
           static_cast<unsigned>(g_state.cycles));

  static Classifier classifier;
  const bool model_ok = classifier.Init();
  if (model_ok && cold_boot) classifier.SelfTest();  // só na partida: poupa tempo a cada despertar
  if (SensorsInit() != ESP_OK) ESP_LOGE(TAG, "ADS1115 não respondeu: sem leitura de solo, nada será regado");
  TelemetryStart();

  bool camera_ready = false;
  bool first_loop = true;
  int64_t last_report_s = 0;
  while (true) {
    const int64_t now_s = NowSeconds();
    const bool vision = model_ok && NeedsVision(g_state.trackers, kNumPots, now_s, g_state.last_vision_s,
                                                CONFIG_AGROSENSE_VISION_SECONDS, cold_boot && first_loop);
    if (vision) {
      if (!camera_ready) {
        camera_ready = CameraInit() == ESP_OK;
        if (!camera_ready) ESP_LOGE(TAG, "Câmera não iniciou: confira os pinos em app_config.h");
      }
      if (camera_ready) {
        bool unconfirmed = false;
        for (int p = 0; p < kNumPots; ++p) unconfirmed = unconfirmed || g_state.trackers[p].confirmed() < 0;
        const int passes = unconfirmed ? kSpeciesConfirmations : 1;  // confirma a espécie no mesmo ciclo
        for (int i = 0; i < passes; ++i) ClassifyPots(classifier, i == passes - 1);
        QueueCameraInfo();
        g_state.last_vision_s = now_s;
      }
    }

    const bool report_all = first_loop || vision || now_s - last_report_s >= kContinuousReportSeconds;
    if (report_all) last_report_s = now_s;
    const bool any_pump_on = RunControl(now_s, report_all);
    first_loop = false;

#if CONFIG_AGROSENSE_DEEP_SLEEP
    if (CanSleep(g_state.pots, kNumPots)) {
      if (TelemetryWaitConnected(kTelemetryConnectTimeoutMs)) {
        SendQueued();
        TelemetryPublish(kStatusTopic, "dormindo", 1, true);
        if (!TelemetryFlush(kTelemetryFlushTimeoutMs)) ESP_LOGW(TAG, "Broker não confirmou tudo; segue para o sono");
      } else {
        ESP_LOGW(TAG, "Sem rede neste ciclo: a decisão foi local e o estado sai no próximo");
        DropPhoto();
      }
      TelemetryStop();
      ActuatorsPrepareSleep();
      ESP_LOGI(TAG, "Dormindo por %d s", CONFIG_AGROSENSE_SLEEP_SECONDS);
      esp_sleep_enable_timer_wakeup(static_cast<uint64_t>(CONFIG_AGROSENSE_SLEEP_SECONDS) * 1000000ULL);
      esp_deep_sleep_start();
    }
    (void)any_pump_on;
    SendQueued();
    vTaskDelay(pdMS_TO_TICKS(1000));  // regando: o controlador fica acordado e confere o solo a cada 1 s
#else
    SendQueued();
    vTaskDelay(pdMS_TO_TICKS(any_pump_on ? 1000 : 5000));
#endif
  }
}
