// Testes no PC (g++) da lógica pura do firmware: decisão de irrigação,
// confirmação da espécie, umidade do solo e pré-processamento da imagem.
#include <cstdio>
#include <cstring>

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

static const SpeciesProfile kTestProfile = {"teste", true, 30, 60, 20, 600};
static const SpeciesProfile kEmptyPot = {"vazio", false, 0, 0, 0, 0};

static PotInputs Dry(int64_t now) { return {&kTestProfile, true, 20, true, now}; }

static void TestIrrigation() {
  PotState s;
  Decision d = StepPot(s, Dry(0));
  CHECK(d.pump_on && d.reason == Reason::kStartDry);

  // Histerese: segue ligada entre os limiares e desliga ao chegar em stop_at
  d = StepPot(s, {&kTestProfile, true, 45, true, 5});
  CHECK(d.pump_on && d.reason == Reason::kRunning);
  d = StepPot(s, {&kTestProfile, true, 60, true, 8});
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
  d = StepPot(t, {&kTestProfile, true, 20, false, 0});
  CHECK(!d.pump_on && d.reason == Reason::kBlockedTankLow);
  StepPot(t, Dry(1));
  d = StepPot(t, {&kTestProfile, true, 20, false, 2});
  CHECK(!d.pump_on && d.reason == Reason::kStopTankLow);

  // Espécie desconhecida, vaso vazio e sensor com falha nunca regam
  PotState u;
  d = StepPot(u, {nullptr, true, 5, true, 0});
  CHECK(!d.pump_on && d.reason == Reason::kBlockedUnknownSpecies);
  d = StepPot(u, {&kEmptyPot, true, 5, true, 0});
  CHECK(!d.pump_on && d.reason == Reason::kBlockedNoIrrigation);
  d = StepPot(u, {&kTestProfile, false, 0, true, 0});
  CHECK(!d.pump_on && d.reason == Reason::kBlockedSensorFault);
  StepPot(u, Dry(1));
  d = StepPot(u, {&kTestProfile, false, 0, true, 2});
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

int main() {
  TestIrrigation();
  TestSpeciesTracker();
  TestProfiles();
  TestSoilPercent();
  TestRgb565Decode();
  TestCropResize();
  TestQuantizeImage();
  std::printf("%d verificações, %d falhas\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
