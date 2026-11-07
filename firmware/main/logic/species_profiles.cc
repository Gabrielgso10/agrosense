// Perfis das espécies do protótipo — responsabilidade do Leonardo.
// p vem da Tabela 22 da FAO 56 (ALLEN et al., 1998). Os limiares de cada vaso saem de p
// e da calibração do vaso (capacidade de campo e ponto de murcha, em app_config.h).
// Tempo máximo e intervalo dependem da vazão da bomba e do tamanho do vaso: ajustar na bancada.
// O rótulo precisa ser idêntico ao nome da pasta do dataset.
#include <cstring>

#include "species.h"

namespace agrosense {
namespace {

const SpeciesProfile kProfiles[] = {
    //  rótulo       rega   p (FAO 56)  máx. s  intervalo s
    {"alface",       true,  0.30f,      15,     3600},  // Lettuce
    {"cebolinha",    true,  0.30f,      15,     3600},  // Onions - green
    {"rucula",       true,  0.30f,      15,     3600},  // não consta na tabela: mesmo p da
                                                       // alface e do rabanete (premissa)
    {"vazio",        false, 0.00f,      0,      0},
};

}  // namespace

const SpeciesProfile* FindProfile(const char* label) {
  if (label == nullptr) return nullptr;
  for (const SpeciesProfile& p : kProfiles) {
    if (std::strcmp(p.label, label) == 0) return &p;
  }
  return nullptr;
}

}  // namespace agrosense
