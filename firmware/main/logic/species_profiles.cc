// Tabela de perfis por espécie — responsabilidade do Leonardo.
// Os valores abaixo são EXEMPLOS para o protótipo funcionar; substitua pelos
// definidos para cada espécie (FAO 56 e literatura da fundamentação).
// O rótulo precisa ser idêntico ao nome da pasta do dataset.
#include <cstring>

#include "species.h"

namespace agrosense {
namespace {

const SpeciesProfile kProfiles[] = {
    //  rótulo          rega   liga<%  desliga>=%  máx. s  intervalo s
    {"suculenta",       true,  15,     30,         10,     6 * 3600},
    {"folha larga",     true,  40,     60,         20,     2 * 3600},
    {"flor vermelha",   true,  35,     55,         15,     2 * 3600},
    {"vazio",           false, 0,      0,          0,      0},
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
