// Perfis hídricos por espécie e confirmação da espécie vista pela câmera.
#pragma once

namespace agrosense {

struct SpeciesProfile {
  const char* label;   // igual ao rótulo do modelo (nome da pasta do dataset)
  bool irrigate;       // false para a classe "vazio" (sem planta no lugar)
  float depletion_p;   // fator de depleção p da FAO 56 (Tabela 22): fração da água disponível
                       // que a planta consome sem estresse; define o limiar de ligar
  int max_run_s;       // tempo máximo de bomba ligada por rega
  int cooldown_s;      // espera mínima entre regas, para a água infiltrar
};

// Perfil pelo rótulo; nullptr se a espécie não tiver perfil cadastrado.
const SpeciesProfile* FindProfile(const char* label);

// Rótulo usado para o vaso: a espécie fixa, se houver (fase de germinação), senão a
// espécie confirmada pela câmera; nullptr se nenhuma das duas existir.
const char* ResolveSpeciesLabel(const char* fixed_label, int confirmed_index, const char* const* labels,
                                int num_labels);

// Só confirma uma espécie depois de `confirmations` classificações seguidas
// iguais. Classificações abaixo de `min_confidence` contam como desconhecida.
class SpeciesTracker {
 public:
  // constexpr: permite guardar o rastreador na memória RTC sem inicialização em tempo de
  // execução, que apagaria o estado a cada despertar do sono profundo.
  constexpr explicit SpeciesTracker(int confirmations = 2, float min_confidence = 0.6f)
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
