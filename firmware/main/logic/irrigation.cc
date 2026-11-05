#include "irrigation.h"

#include <cmath>

namespace agrosense {
namespace {

Decision Stop(PotState& s, int64_t now, Reason why) {
  s.pump_on = false;
  s.last_stop_s = now;
  s.has_stopped = true;
  return {false, why};
}

}  // namespace

Decision StepPot(PotState& s, const PotInputs& in) {
  const SpeciesProfile* p = in.profile;

  if (s.pump_on) {
    if (!in.tank_ok) return Stop(s, in.now_s, Reason::kStopTankLow);
    if (!in.soil_valid) return Stop(s, in.now_s, Reason::kStopSensorFault);
    if (p == nullptr || !p->irrigate) return Stop(s, in.now_s, Reason::kBlockedUnknownSpecies);
    if (in.now_s - s.pump_started_s >= p->max_run_s) return Stop(s, in.now_s, Reason::kStopMaxRun);
    if (in.soil_pct >= p->stop_at_pct) return Stop(s, in.now_s, Reason::kStopWet);
    return {true, Reason::kRunning};
  }

  if (p == nullptr) return {false, Reason::kBlockedUnknownSpecies};
  if (!p->irrigate) return {false, Reason::kBlockedNoIrrigation};
  if (!in.soil_valid) return {false, Reason::kBlockedSensorFault};
  if (!in.tank_ok) return {false, Reason::kBlockedTankLow};
  if (s.has_stopped && in.now_s - s.last_stop_s < p->cooldown_s) return {false, Reason::kBlockedCooldown};
  if (in.soil_pct < p->start_below_pct) {
    s.pump_on = true;
    s.pump_started_s = in.now_s;
    return {true, Reason::kStartDry};
  }
  return {false, Reason::kIdle};
}

const char* ReasonName(Reason r) {
  switch (r) {
    case Reason::kIdle: return "ocioso";
    case Reason::kStartDry: return "ligou_solo_seco";
    case Reason::kRunning: return "regando";
    case Reason::kStopWet: return "parou_solo_umido";
    case Reason::kStopMaxRun: return "parou_tempo_maximo";
    case Reason::kStopTankLow: return "parou_reservatorio_vazio";
    case Reason::kStopSensorFault: return "parou_falha_sensor";
    case Reason::kBlockedUnknownSpecies: return "bloqueado_especie_desconhecida";
    case Reason::kBlockedNoIrrigation: return "bloqueado_sem_irrigacao";
    case Reason::kBlockedSensorFault: return "bloqueado_falha_sensor";
    case Reason::kBlockedTankLow: return "bloqueado_reservatorio_vazio";
    case Reason::kBlockedCooldown: return "bloqueado_intervalo";
  }
  return "?";
}

int SoilPercent(float volts, float dry_volts, float wet_volts) {
  const float span = wet_volts - dry_volts;
  if (std::fabs(span) < 1e-3f) return -1;
  float pct = (volts - dry_volts) / span * 100.0f;
  if (pct < 0.0f) pct = 0.0f;
  if (pct > 100.0f) pct = 100.0f;
  return static_cast<int>(std::lround(pct));
}

}  // namespace agrosense
