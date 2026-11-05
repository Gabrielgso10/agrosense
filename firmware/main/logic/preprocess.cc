#include "preprocess.h"

#include <cmath>

#include "model_settings.h"

namespace agrosense {
namespace {

inline void Decode(const uint8_t* p, bool big_endian, float rgb[3]) {
  const uint16_t v = big_endian ? static_cast<uint16_t>((p[0] << 8) | p[1])
                                : static_cast<uint16_t>((p[1] << 8) | p[0]);
  const int r5 = (v >> 11) & 0x1F, g6 = (v >> 5) & 0x3F, b5 = v & 0x1F;
  rgb[0] = static_cast<float>((r5 << 3) | (r5 >> 2));  // expande para 0..255
  rgb[1] = static_cast<float>((g6 << 2) | (g6 >> 4));
  rgb[2] = static_cast<float>((b5 << 3) | (b5 >> 2));
}

// Peso e vizinhos de uma coordenada de saída (centros de pixel deslocados
// de meio pixel, com borda repetida), como o kernel ResizeBilinear do TF.
inline void Weights(int out, float scale, int in_size, int* lo, int* hi, float* lerp) {
  const float in = (static_cast<float>(out) + 0.5f) * scale - 0.5f;
  const float in_floor = std::floor(in);
  *lo = in_floor < 0.0f ? 0 : static_cast<int>(in_floor);
  const int up = static_cast<int>(std::ceil(in));
  *hi = up > in_size - 1 ? in_size - 1 : up;
  *lerp = in - in_floor;
}

}  // namespace

void DecodeRgb565(const uint8_t* src, int pixels, uint8_t* rgb, bool big_endian) {
  float c[3];
  for (int i = 0; i < pixels; ++i) {
    Decode(src + 2 * i, big_endian, c);
    for (int k = 0; k < 3; ++k) rgb[3 * i + k] = static_cast<uint8_t>(c[k]);
  }
}

bool CropResizeRgb565(const uint8_t* src, int width, int height, Roi roi, int out_size,
                      uint8_t* out, bool big_endian) {
  if (roi.size <= 0 || roi.x < 0 || roi.y < 0 || roi.x + roi.size > width ||
      roi.y + roi.size > height || out_size <= 0) {
    return false;
  }
  const float scale = static_cast<float>(roi.size) / static_cast<float>(out_size);
  auto pixel = [&](int x, int y) { return src + 2 * ((roi.y + y) * width + (roi.x + x)); };

  for (int oy = 0; oy < out_size; ++oy) {
    int y0, y1;
    float wy;
    Weights(oy, scale, roi.size, &y0, &y1, &wy);
    for (int ox = 0; ox < out_size; ++ox) {
      int x0, x1;
      float wx;
      Weights(ox, scale, roi.size, &x0, &x1, &wx);
      float tl[3], tr[3], bl[3], br[3];
      Decode(pixel(x0, y0), big_endian, tl);
      Decode(pixel(x1, y0), big_endian, tr);
      Decode(pixel(x0, y1), big_endian, bl);
      Decode(pixel(x1, y1), big_endian, br);
      uint8_t* o = out + 3 * (oy * out_size + ox);
      for (int k = 0; k < 3; ++k) {
        const float top = tl[k] + (tr[k] - tl[k]) * wx;
        const float bottom = bl[k] + (br[k] - bl[k]) * wx;
        const float v = top + (bottom - top) * wy;
        o[k] = static_cast<uint8_t>(std::lround(v < 0.0f ? 0.0f : (v > 255.0f ? 255.0f : v)));
      }
    }
  }
  return true;
}

void QuantizeImage(const uint8_t* rgb, int count, int8_t* out) {
  for (int i = 0; i < count; ++i) out[i] = QuantizePixel(rgb[i]);
}

}  // namespace agrosense
