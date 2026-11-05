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

}  // namespace agrosense
