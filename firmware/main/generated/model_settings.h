// GERADO AUTOMATICAMENTE pelos scripts de training/ — não edite à mão.
#pragma once
#include <cmath>
#include <cstdint>

constexpr int kInputHeight = 96;
constexpr int kInputWidth = 96;
constexpr int kInputChannels = 3;
constexpr float kInputScale = 9.450980425e-01f;
constexpr int kInputZeroPoint = -128;
constexpr float kOutputScale = 3.906250000e-03f;
constexpr int kOutputZeroPoint = -128;
constexpr int kNumClasses = 3;
constexpr const char* kLabels[kNumClasses] = {"flor vermelha", "folha larga", "suculenta"};

// Pixel RGB888 (0..255) -> entrada int8 do modelo. Mesma regra do quant.py.
inline int8_t QuantizePixel(uint8_t pixel) {
  int32_t q = static_cast<int32_t>(std::lround(pixel / kInputScale)) + kInputZeroPoint;
  if (q < -128) q = -128;
  if (q > 127) q = 127;
  return static_cast<int8_t>(q);
}

inline float DequantizeOutput(int8_t q) { return (q - kOutputZeroPoint) * kOutputScale; }
