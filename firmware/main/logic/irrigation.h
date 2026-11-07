// Decisão de irrigação de um vaso: histerese entre os limiares da espécie,
// tempo máximo de bomba ligada, intervalo mínimo entre regas e travas de
// segurança (reservatório vazio, sensor com falha, espécie desconhecida).
// Lógica pura, sem ESP-IDF: testada no PC por firmware/test/host.
#pragma once
#include <cstdint>

#include "species.h"

namespace agrosense {

enum class Reason {
  kIdle,                   // solo dentro da faixa, nada a fazer
  kStartDry,               // ligou: solo abaixo do limiar da espécie
  kRunning,                // segue regando
  kStopWet,                // desligou: chegou ao limiar de parada
  kStopMaxRun,             // desligou: tempo máximo atingido
  kStopTankLow,            // desligou: reservatório vazio
  kStopSensorFault,        // desligou: leitura do solo inválida
  kBlockedUnknownSpecies,  // não rega: espécie não confirmada ou sem perfil
  kBlockedNoIrrigation,    // não rega: perfil sem irrigação (vaso vazio)
  kBlockedSensorFault,     // não rega: leitura do solo inválida
  kBlockedTankLow,         // não rega: reservatório vazio
  kBlockedCooldown,        // não rega: ainda no intervalo mínimo
};

struct PotState {
  bool pump_on = false;
  int64_t pump_started_s = 0;
  int64_t last_stop_s = 0;
  bool has_stopped = false;
};

// Limiares do vaso no índice de umidade (%): liga abaixo de low, desliga ao chegar em high.
struct Thresholds {
  int low;
  int high;
};

// FAO 56: rega-se quando a planta consumiu a fração p da água disponível entre a
// capacidade de campo e o ponto de murcha. p é limitado a 0,1..0,8, como na FAO.
Thresholds ThresholdsFromFao(float p, int field_capacity_pct, int wilting_pct);

struct PotInputs {
  const SpeciesProfile* profile;  // nullptr = espécie desconhecida
  Thresholds limits;
  bool soil_valid;
  int soil_pct;
  bool tank_ok;
  int64_t now_s;
};

struct Decision {
  bool pump_on;
  Reason reason;
};

Decision StepPot(PotState& state, const PotInputs& in);
const char* ReasonName(Reason reason);

// Converte a tensão do sensor capacitivo em umidade 0..100% pelos dois pontos
// de calibração (no ar = seco, na água = molhado). -1 se a calibração for inválida.
int SoilPercent(float volts, float dry_volts, float wet_volts);

}  // namespace agrosense
