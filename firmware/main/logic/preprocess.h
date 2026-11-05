// Pré-processamento da imagem no nó, idêntico ao de training/data.py:
// recorte quadrado -> redimensionamento bilinear (igual ao tf.image.resize)
// -> quantização int8 com os parâmetros do modelo.
#pragma once
#include <cstdint>

namespace agrosense {

struct Roi {
  int x, y, size;  // quadrado na imagem da câmera, em pixels
};

// RGB565 -> RGB888. O esp32-camera entrega RGB565 big-endian (byte alto primeiro).
void DecodeRgb565(const uint8_t* src, int pixels, uint8_t* rgb, bool big_endian);

// Recorta o ROI do quadro RGB565 e redimensiona para out_size x out_size em RGB888,
// com a interpolação bilinear de meio pixel do tf.image.resize (TF2).
// Retorna false se o ROI não couber no quadro.
bool CropResizeRgb565(const uint8_t* rgb565, int width, int height, Roi roi, int out_size,
                      uint8_t* out_rgb, bool big_endian);

// RGB888 -> entrada int8 do modelo, via QuantizePixel() de model_settings.h.
void QuantizeImage(const uint8_t* rgb, int count, int8_t* out);

}  // namespace agrosense
