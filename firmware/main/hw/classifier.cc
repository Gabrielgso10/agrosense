#include "classifier.h"

#include <cstdlib>
#include <cstring>

#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_memory_utils.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "arena_config.h"
#include "golden_data.h"
#include "model_data.h"
#include "model_ops.h"
#include "model_settings.h"
#include "preprocess.h"

namespace agrosense {
namespace {

const char* TAG = "classificador";

// Buffers de rascunho do ESP-NN (mesma reserva do exemplo person_detection da Espressif)
#if CONFIG_NN_OPTIMIZED
constexpr int kEspNnScratchBytes = 60 * 1024;
#else
constexpr int kEspNnScratchBytes = 0;
#endif
constexpr int kArenaBytes = kTensorArenaSize + kEspNnScratchBytes;

tflite::MicroInterpreter* g_interpreter = nullptr;

int ArgMax(const int8_t* v, int n) {
  int best = 0;
  for (int i = 1; i < n; ++i) {
    if (v[i] > v[best]) best = i;
  }
  return best;
}

}  // namespace

bool Classifier::Init() {
  const tflite::Model* model = tflite::GetModel(g_model);
  if (model->version() != TFLITE_SCHEMA_VERSION) {
    ESP_LOGE(TAG, "Versão de schema do modelo incompatível");
    return false;
  }
  static tflite::MicroMutableOpResolver<kNumOps> resolver;
  if (RegisterOps(resolver) != kTfLiteOk) {
    ESP_LOGE(TAG, "Falha ao registrar operadores");
    return false;
  }
  auto* arena = static_cast<uint8_t*>(heap_caps_malloc_prefer(
      kArenaBytes, 2, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (arena == nullptr) {
    ESP_LOGE(TAG, "Sem memória para a arena de %d bytes", kArenaBytes);
    return false;
  }
  static tflite::MicroInterpreter interpreter(model, resolver, arena, kArenaBytes);
  if (interpreter.AllocateTensors() != kTfLiteOk) {
    ESP_LOGE(TAG, "AllocateTensors falhou: aumente ARENA_MARGIN em training/config.py");
    return false;
  }
  g_interpreter = &interpreter;
  ESP_LOGI(TAG, "Modelo %u KB, arena %d KB na %s (%u KB em uso)", g_model_len / 1024, kArenaBytes / 1024,
           esp_ptr_external_ram(arena) ? "PSRAM" : "RAM interna",
           static_cast<unsigned>(interpreter.arena_used_bytes() / 1024));
  return true;
}

bool Classifier::SelfTest() {
  if (g_interpreter == nullptr) return false;
  TfLiteTensor* in = g_interpreter->input(0);
  TfLiteTensor* out = g_interpreter->output(0);
  if (in->bytes != g_golden_input_len || out->bytes != g_golden_expected_len) {
    ESP_LOGE(TAG, "Teste de ouro não bate com o modelo: rode convert.py e compare.py");
    return false;
  }
  std::memcpy(in->data.int8, g_golden_input, g_golden_input_len);
  if (g_interpreter->Invoke() != kTfLiteOk) return false;
  int max_diff = 0;
  for (unsigned i = 0; i < g_golden_expected_len; ++i) {
    const int d = std::abs(out->data.int8[i] - g_golden_expected[i]);
    if (d > max_diff) max_diff = d;
  }
  const bool ok = ArgMax(out->data.int8, kNumClasses) == kGoldenLabelIndex && max_diff <= kGoldenTolerance;
  ESP_LOGI(TAG, "TESTE DE OURO: %s (maior diferença %d LSB)", ok ? "PASSOU" : "FALHOU", max_diff);
  return ok;
}

Prediction Classifier::Classify(const uint8_t* rgb) {
  if (g_interpreter == nullptr) return {-1, 0.0f};
  TfLiteTensor* in = g_interpreter->input(0);
  QuantizeImage(rgb, kInputWidth * kInputHeight * kInputChannels, in->data.int8);
  const int64_t start = esp_timer_get_time();
  if (g_interpreter->Invoke() != kTfLiteOk) return {-1, 0.0f};
  last_latency_us_ = esp_timer_get_time() - start;
  const int8_t* scores = g_interpreter->output(0)->data.int8;
  const int best = ArgMax(scores, kNumClasses);
  return {best, DequantizeOutput(scores[best])};
}

}  // namespace agrosense
