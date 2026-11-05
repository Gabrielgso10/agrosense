// AgroSense — nó de borda. A câmera identifica a espécie de cada vaso, o nó
// decide a irrigação localmente com o perfil da espécie e a nuvem recebe só
// telemetria por MQTT. Sem rede, tudo continua funcionando.
#include <cstdio>

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#include "actuators.h"
#include "app_config.h"
#include "camera.h"
#include "classifier.h"
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

void InitNvs() {
  esp_err_t err = nvs_flash_init();  // exigido pelo Wi-Fi
  if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    ESP_ERROR_CHECK(nvs_flash_erase());
    err = nvs_flash_init();
  }
  ESP_ERROR_CHECK(err);
}

void ClassifyPots(Classifier& classifier, SpeciesTracker* trackers) {
  camera_fb_t* fb = CameraCapture();
  if (fb == nullptr) {
    ESP_LOGW(TAG, "Sem quadro da câmera nesta rodada");
    return;
  }
  for (int p = 0; p < kNumPots; ++p) {
    if (!CropResizeRgb565(fb->buf, static_cast<int>(fb->width), static_cast<int>(fb->height), kPotRois[p],
                          kInputWidth, g_crop, kRgb565BigEndian)) {
      ESP_LOGE(TAG, "Vaso %d: região fora do quadro (ajuste kPotRois)", p);
      continue;
    }
    const Prediction pr = classifier.Classify(g_crop);
    const int confirmed = trackers[p].Update(pr.index, pr.confidence);
    ESP_LOGI(TAG, "Vaso %d: viu '%s' (%.0f%%, %.0f ms) | espécie confirmada: %s", p,
             pr.index >= 0 ? kLabels[pr.index] : "?", 100.0 * static_cast<double>(pr.confidence),
             static_cast<double>(classifier.last_latency_us()) / 1000.0,
             confirmed >= 0 ? kLabels[confirmed] : "nenhuma");
  }
  CameraRelease(fb);
}

}  // namespace

extern "C" void app_main(void) {
  ActuatorsInit();  // primeiro: bombas garantidamente desligadas
  InitNvs();

  static Classifier classifier;
  if (!classifier.Init()) return;
  classifier.SelfTest();
  if (CameraInit() != ESP_OK) ESP_LOGE(TAG, "Câmera não iniciou: confira os pinos em app_config.h");
  if (SensorsInit() != ESP_OK) ESP_LOGE(TAG, "ADS1115 não respondeu: sem leitura de solo, nada será regado");
  TelemetryStart();

  static SpeciesTracker trackers[kNumPots];
  static PotState pots[kNumPots];
  for (int p = 0; p < kNumPots; ++p) trackers[p] = SpeciesTracker(kSpeciesConfirmations, kMinConfidence);

  int64_t next_vision_s = 0;
  char topic[32];
  char json[256];
  while (true) {
    const int64_t now_s = esp_timer_get_time() / 1000000;
    const bool vision_due = now_s >= next_vision_s;
    if (vision_due) {
      ClassifyPots(classifier, trackers);
      next_vision_s = now_s + CONFIG_AGROSENSE_VISION_SECONDS;
    }

    const bool tank_ok = TankOk();
    bool any_pump_on = false;
    for (int p = 0; p < kNumPots; ++p) {
      float volts = 0.0f;
      const bool read_ok = ReadSoilVolts(kPotSoilChannel[p], &volts);
      const int soil = read_ok ? SoilPercent(volts, kSoilDryVolts[p], kSoilWetVolts[p]) : -1;
      const int species = trackers[p].confirmed();
      const SpeciesProfile* profile = species >= 0 ? FindProfile(kLabels[species]) : nullptr;
      const bool was_on = pots[p].pump_on;
      const Decision d = StepPot(pots[p], {profile, soil >= 0, soil, tank_ok, now_s});
      SetPump(p, d.pump_on);
      any_pump_on = any_pump_on || d.pump_on;

      if (vision_due || d.pump_on != was_on) {
        ESP_LOGI(TAG, "Vaso %d: solo %d%% (%.2f V) | bomba %s | %s", p, soil, static_cast<double>(volts),
                 d.pump_on ? "LIGADA" : "desligada", ReasonName(d.reason));
        snprintf(topic, sizeof(topic), "agrosense/vaso/%d", p);
        snprintf(json, sizeof(json), "{\"vaso\":%d,\"especie\":\"%s\",\"solo_pct\":%d,\"bomba\":%s,\"motivo\":\"%s\"}",
                 p, species >= 0 ? kLabels[species] : "", soil, d.pump_on ? "true" : "false", ReasonName(d.reason));
        TelemetryPublish(topic, json);
      }
    }

    if (vision_due) {
      const Environment env = ReadEnvironment();
      snprintf(json, sizeof(json),
               "{\"temperatura_c\":%.1f,\"umidade_ar_pct\":%.1f,\"lux\":%.0f,\"reservatorio_ok\":%s,\"sensores_ok\":%s}",
               static_cast<double>(env.temperature_c), static_cast<double>(env.humidity_pct),
               static_cast<double>(env.lux), tank_ok ? "true" : "false", env.valid ? "true" : "false");
      TelemetryPublish("agrosense/ambiente", json);
    }
    vTaskDelay(pdMS_TO_TICKS(any_pump_on ? 1000 : 5000));  // regando: confere o solo a cada 1 s
  }
}
