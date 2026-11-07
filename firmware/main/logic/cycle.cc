#include "cycle.h"

namespace agrosense {

bool NeedsVision(const SpeciesTracker* trackers, int count, int64_t now_s, int64_t last_vision_s,
                 int64_t interval_s, bool first_cycle) {
  if (first_cycle) return true;
  for (int i = 0; i < count; ++i) {
    if (trackers[i].confirmed() < 0) return true;
  }
  return now_s - last_vision_s >= interval_s;
}

bool CanSleep(const PotState* pots, int count) {
  for (int i = 0; i < count; ++i) {
    if (pots[i].pump_on) return false;
  }
  return true;
}

MessagePolicy PotMessagePolicy(bool pump_changed) {
  return pump_changed ? MessagePolicy{1, true} : MessagePolicy{0, false};
}

}  // namespace agrosense
