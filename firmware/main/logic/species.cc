#include "species.h"

namespace agrosense {

int SpeciesTracker::Update(int class_index, float confidence) {
  const int seen = confidence >= min_confidence_ ? class_index : -1;
  if (seen == candidate_) {
    ++count_;
  } else {
    candidate_ = seen;
    count_ = 1;
  }
  if (count_ >= needed_) confirmed_ = candidate_;
  return confirmed_;
}

const char* ResolveSpeciesLabel(const char* fixed_label, int confirmed_index, const char* const* labels,
                                int num_labels) {
  if (fixed_label != nullptr) return fixed_label;
  if (confirmed_index >= 0 && confirmed_index < num_labels) return labels[confirmed_index];
  return nullptr;
}

}  // namespace agrosense
