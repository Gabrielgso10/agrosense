// Usado por test_resize_parity.py: aplica CropResizeRgb565 a um quadro em disco.
// uso: resize_harness entrada.bin largura altura x y lado saida_lado saida.bin
#include <cstdio>
#include <cstdlib>
#include <vector>

#include "preprocess.h"

int main(int argc, char** argv) {
  if (argc != 9) return 2;
  const int w = std::atoi(argv[2]), h = std::atoi(argv[3]), out = std::atoi(argv[7]);
  const agrosense::Roi roi{std::atoi(argv[4]), std::atoi(argv[5]), std::atoi(argv[6])};
  std::vector<uint8_t> src(static_cast<size_t>(w) * h * 2), dst(static_cast<size_t>(out) * out * 3);
  FILE* f = std::fopen(argv[1], "rb");
  if (!f || std::fread(src.data(), 1, src.size(), f) != src.size()) return 3;
  std::fclose(f);
  if (!agrosense::CropResizeRgb565(src.data(), w, h, roi, out, dst.data(), true)) return 4;
  f = std::fopen(argv[8], "wb");
  std::fwrite(dst.data(), 1, dst.size(), f);
  std::fclose(f);
  return 0;
}
