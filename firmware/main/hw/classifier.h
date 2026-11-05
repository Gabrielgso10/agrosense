// Classificador de espécies com o TFLM: carrega o modelo, roda o teste de ouro
// e classifica recortes RGB888 96x96.
#pragma once
#include <cstdint>

namespace agrosense {

struct Prediction {
  int index;         // -1 em caso de erro
  float confidence;  // 0..1
};

class Classifier {
 public:
  bool Init();
  bool SelfTest();  // imagem gravada pelo compare.py; registra PASSOU/FALHOU
  Prediction Classify(const uint8_t* rgb);
  int64_t last_latency_us() const { return last_latency_us_; }

 private:
  int64_t last_latency_us_ = 0;
};

}  // namespace agrosense
