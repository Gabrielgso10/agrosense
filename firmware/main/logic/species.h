// Perfis hídricos por espécie e confirmação da espécie vista pela câmera.
#pragma once

namespace agrosense {

struct SpeciesProfile {
  const char* label;    // igual ao rótulo do modelo (models/labels.txt)
  bool irrigate;        // false para a classe "vazio" (sem planta no lugar)
  int start_below_pct;  // liga a bomba quando a umidade do solo cai abaixo disto
  int stop_at_pct;      // desliga quando a umidade chega a isto (histerese)
  int max_run_s;        // tempo máximo de bomba ligada por rega
  int cooldown_s;       // espera mínima entre regas, para a água infiltrar
};

// Perfil pelo rótulo; nullptr se a espécie não tiver perfil cadastrado.
const SpeciesProfile* FindProfile(const char* label);

// Só confirma uma espécie depois de `confirmations` classificações seguidas
// iguais. Classificações abaixo de `min_confidence` contam como desconhecida.
class SpeciesTracker {
 public:
  explicit SpeciesTracker(int confirmations = 2, float min_confidence = 0.6f)
      : needed_(confirmations), min_confidence_(min_confidence) {}

  // Registra uma classificação e devolve a espécie confirmada (-1 = nenhuma).
  int Update(int class_index, float confidence);
  int confirmed() const { return confirmed_; }

 private:
  int needed_;
  float min_confidence_;
  int candidate_ = -1;
  int count_ = 0;
  int confirmed_ = -1;
};

}  // namespace agrosense
