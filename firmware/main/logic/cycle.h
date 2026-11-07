// Planejamento do ciclo de trabalho (sono profundo): quando rodar a câmera,
// quando o nó pode dormir e com que QoS cada mensagem sai. Lógica pura,
// testada no PC por firmware/test/host.
#pragma once
#include <cstdint>

#include "irrigation.h"
#include "species.h"

namespace agrosense {

// A câmera roda no primeiro ciclo, sempre que algum vaso ainda não tiver espécie
// confirmada e quando vence o intervalo de reverificação.
bool NeedsVision(const SpeciesTracker* trackers, int count, int64_t now_s, int64_t last_vision_s,
                 int64_t interval_s, bool first_cycle);

// O nó só dorme sem nenhuma bomba ligada: uma rega em andamento precisa do
// controlador acordado até atingir o limiar de parada ou o tempo máximo.
bool CanSleep(const PotState* pots, int count);

struct MessagePolicy {
  int qos;
  bool retain;
};

// Mudança de estado da bomba: QoS 1 com retenção. Leitura periódica: QoS 0,
// pois a próxima substitui a anterior.
MessagePolicy PotMessagePolicy(bool pump_changed);

}  // namespace agrosense
