// Testes no PC (g++) da lógica pura do firmware: decisão de irrigação,
// confirmação da espécie, umidade do solo e pré-processamento da imagem.
#include <cstdio>
#include <cstring>

#include <type_traits>

#include "cycle.h"
#include "irrigation.h"
#include "model_settings.h"
#include "preprocess.h"
#include "species.h"

using namespace agrosense;

static int g_failures = 0, g_checks = 0;
#define CHECK(cond)                                                    \
  do {                                                                 \
    ++g_checks;                                                        \
    if (!(cond)) {                                                     \
      ++g_failures;                                                    \
      std::printf("FALHOU %s:%d  %s\n", __FILE__, __LINE__, #cond);    \
    }                                                                  \
  } while (0)

static const SpeciesProfile kTestProfile = {"teste", true, 0.30f, 20, 600};
static const SpeciesProfile kEmptyPot = {"vazio", false, 0.0f, 0, 0};
static const Thresholds kLimits = {30, 60};  // liga abaixo de 30%, desliga em 60%

static PotInputs Dry(int64_t now) { return {&kTestProfile, kLimits, true, 20, true, now}; }

static void TestIrrigation() {
  PotState s;
  Decision d = StepPot(s, Dry(0));
  CHECK(d.pump_on && d.reason == Reason::kStartDry);

  // Histerese: segue ligada entre os limiares e desliga ao chegar em stop_at
  d = StepPot(s, {&kTestProfile, kLimits, true, 45, true, 5});
  CHECK(d.pump_on && d.reason == Reason::kRunning);
  d = StepPot(s, {&kTestProfile, kLimits, true, 60, true, 8});
  CHECK(!d.pump_on && d.reason == Reason::kStopWet);

  // Intervalo mínimo entre regas, mesmo com o solo seco
  d = StepPot(s, Dry(100));
  CHECK(!d.pump_on && d.reason == Reason::kBlockedCooldown);
  d = StepPot(s, Dry(8 + 600));
  CHECK(d.pump_on && d.reason == Reason::kStartDry);

  // Tempo máximo de bomba ligada
  d = StepPot(s, Dry(8 + 600 + 20));
  CHECK(!d.pump_on && d.reason == Reason::kStopMaxRun);

  // Reservatório vazio impede ligar e desliga bomba em funcionamento
  PotState t;
  d = StepPot(t, {&kTestProfile, kLimits, true, 20, false, 0});
  CHECK(!d.pump_on && d.reason == Reason::kBlockedTankLow);
  StepPot(t, Dry(1));
  d = StepPot(t, {&kTestProfile, kLimits, true, 20, false, 2});
  CHECK(!d.pump_on && d.reason == Reason::kStopTankLow);

  // Espécie desconhecida, vaso vazio e sensor com falha nunca regam
  PotState u;
  d = StepPot(u, {nullptr, kLimits, true, 5, true, 0});
  CHECK(!d.pump_on && d.reason == Reason::kBlockedUnknownSpecies);
  d = StepPot(u, {&kEmptyPot, kLimits, true, 5, true, 0});
  CHECK(!d.pump_on && d.reason == Reason::kBlockedNoIrrigation);
  d = StepPot(u, {&kTestProfile, kLimits, false, 0, true, 0});
  CHECK(!d.pump_on && d.reason == Reason::kBlockedSensorFault);
  StepPot(u, Dry(1));
  d = StepPot(u, {&kTestProfile, kLimits, false, 0, true, 2});
  CHECK(!d.pump_on && d.reason == Reason::kStopSensorFault);
}

static void TestSpeciesTracker() {
  SpeciesTracker tr(2, 0.6f);
  CHECK(tr.Update(1, 0.9f) == -1);  // uma leitura só não confirma
  CHECK(tr.Update(1, 0.8f) == 1);   // duas seguidas confirmam
  CHECK(tr.Update(2, 0.9f) == 1);   // troca isolada não derruba a confirmada
  CHECK(tr.Update(1, 0.9f) == 1);
  CHECK(tr.Update(2, 0.4f) == 1);   // baixa confiança conta como "desconhecida"
  CHECK(tr.Update(0, 0.3f) == -1);  // duas seguidas -> volta a desconhecida
}

static void TestProfiles() {
  CHECK(FindProfile("vazio") != nullptr && !FindProfile("vazio")->irrigate);
  CHECK(FindProfile("especie que nao existe") == nullptr);
  // Fator de depleção p da Tabela 22 da FAO 56
  CHECK(FindProfile("alface") != nullptr && FindProfile("alface")->depletion_p == 0.30f);
  CHECK(FindProfile("cebolinha") != nullptr && FindProfile("cebolinha")->depletion_p == 0.30f);
  CHECK(FindProfile("rucula") != nullptr && FindProfile("rucula")->depletion_p == 0.30f);
  CHECK(FindProfile("feijao") == nullptr);  // o feijão saiu do projeto
}

static void TestThresholds() {
  // Capacidade de campo 70% e ponto de murcha 20%: 50 pontos de água disponível
  const Thresholds a = ThresholdsFromFao(0.30f, 70, 20);
  CHECK(a.low == 55 && a.high == 70);
  const Thresholds f = ThresholdsFromFao(0.45f, 70, 20);
  CHECK(f.low == 48 && f.high == 70);  // 47,5 arredonda para 48
  // p fora da faixa da FAO (0,1 a 0,8) é limitado: a histerese nunca some
  CHECK(ThresholdsFromFao(0.0f, 70, 20).low == 65);
  CHECK(ThresholdsFromFao(0.95f, 70, 20).low == 30);
}

static void TestResolveLabel() {
  const char* labels[] = {"alface", "cebolinha", "rucula"};
  CHECK(std::strcmp(ResolveSpeciesLabel(nullptr, 1, labels, 3), "cebolinha") == 0);
  CHECK(std::strcmp(ResolveSpeciesLabel("rucula", -1, labels, 3), "rucula") == 0);  // fixa vale sem confirmação
  CHECK(std::strcmp(ResolveSpeciesLabel("alface", 2, labels, 3), "alface") == 0);   // e tem prioridade sobre a câmera
  CHECK(ResolveSpeciesLabel(nullptr, -1, labels, 3) == nullptr);
  CHECK(ResolveSpeciesLabel(nullptr, 7, labels, 3) == nullptr);  // índice fora da lista
}

static void TestSoilPercent() {
  // Sensor capacitivo: tensão maior = solo mais seco
  CHECK(SoilPercent(2.8f, 2.8f, 1.2f) == 0);
  CHECK(SoilPercent(1.2f, 2.8f, 1.2f) == 100);
  CHECK(SoilPercent(2.0f, 2.8f, 1.2f) == 50);
  CHECK(SoilPercent(3.1f, 2.8f, 1.2f) == 0);    // abaixo do "seco" -> 0
  CHECK(SoilPercent(0.9f, 2.8f, 1.2f) == 100);  // além do "molhado" -> 100
  CHECK(SoilPercent(2.0f, 2.0f, 2.0f) == -1);   // calibração inválida
}

static void TestRgb565Decode() {
  // big-endian: primeiro o byte alto (como o esp32-camera entrega)
  const uint8_t red[] = {0xF8, 0x00}, green[] = {0x07, 0xE0}, blue[] = {0x00, 0x1F};
  uint8_t out[3];
  DecodeRgb565(red, 1, out, true);
  CHECK(out[0] == 255 && out[1] == 0 && out[2] == 0);
  DecodeRgb565(green, 1, out, true);
  CHECK(out[0] == 0 && out[1] == 255 && out[2] == 0);
  DecodeRgb565(blue, 1, out, true);
  CHECK(out[0] == 0 && out[1] == 0 && out[2] == 255);
  const uint8_t red_le[] = {0x00, 0xF8};
  DecodeRgb565(red_le, 1, out, false);
  CHECK(out[0] == 255 && out[1] == 0 && out[2] == 0);
}

static void TestCropResize() {
  // Imagem 8x6 de cor única: qualquer recorte redimensionado mantém a cor
  static uint8_t img[8 * 6 * 2];
  for (int i = 0; i < 8 * 6; ++i) { img[2 * i] = 0x07; img[2 * i + 1] = 0xE0; }  // verde
  static uint8_t out[4 * 4 * 3];
  CHECK(CropResizeRgb565(img, 8, 6, {1, 1, 4}, 4, out, true));
  bool all_green = true;
  for (int i = 0; i < 16; ++i) all_green &= out[3 * i] == 0 && out[3 * i + 1] == 255 && out[3 * i + 2] == 0;
  CHECK(all_green);
  // Recorte fora da imagem é recusado
  CHECK(!CropResizeRgb565(img, 8, 6, {6, 0, 4}, 4, out, true));
}

static void TestQuantizeImage() {
  uint8_t px[256];
  for (int i = 0; i < 256; ++i) px[i] = static_cast<uint8_t>(i);
  int8_t q[256];
  QuantizeImage(px, 256, q);
  bool same = true;
  for (int i = 0; i < 256; ++i) same &= q[i] == QuantizePixel(px[i]);
  CHECK(same);
}

// O estado guardado na memória RTC precisa ser copiável byte a byte e iniciável em
// tempo de compilação; caso contrário o C++ o reinicializaria a cada despertar.
static_assert(std::is_trivially_copyable<PotState>::value, "PotState precisa caber na memória RTC");
static_assert(std::is_trivially_copyable<SpeciesTracker>::value, "SpeciesTracker precisa caber na memória RTC");
constexpr SpeciesTracker kCompileTimeTracker(2, 0.6f);

static void TestCycle() {
  SpeciesTracker trackers[2] = {SpeciesTracker(2, 0.6f), SpeciesTracker(2, 0.6f)};
  // Primeiro ciclo ou espécie ainda não confirmada: a câmera roda
  CHECK(NeedsVision(trackers, 2, 100, 0, 3600, true));
  CHECK(NeedsVision(trackers, 2, 100, 50, 3600, false));
  for (auto& t : trackers) { t.Update(1, 0.9f); t.Update(1, 0.9f); }
  // Tudo confirmado e dentro do intervalo: não roda; intervalo vencido: roda
  CHECK(!NeedsVision(trackers, 2, 100, 50, 3600, false));
  CHECK(NeedsVision(trackers, 2, 50 + 3600, 50, 3600, false));

  PotState pots[2];
  CHECK(CanSleep(pots, 2));
  pots[1].pump_on = true;
  CHECK(!CanSleep(pots, 2));  // regando: o nó não dorme

  // Mudança da bomba vai com QoS 1 e retenção; leitura periódica, com QoS 0
  CHECK(PotMessagePolicy(true).qos == 1 && PotMessagePolicy(true).retain);
  CHECK(PotMessagePolicy(false).qos == 0 && !PotMessagePolicy(false).retain);
}

int main() {
  TestIrrigation();
  TestSpeciesTracker();
  TestProfiles();
  TestThresholds();
  TestResolveLabel();
  TestSoilPercent();
  TestRgb565Decode();
  TestCropResize();
  TestQuantizeImage();
  TestCycle();
  std::printf("%d verificações, %d falhas\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
