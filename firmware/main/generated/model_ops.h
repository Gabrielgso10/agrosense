// GERADO AUTOMATICAMENTE pelos scripts de training/ — não edite à mão.
#pragma once
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"

constexpr int kNumOps = 7;

template <unsigned int tOpCount>
inline TfLiteStatus RegisterOps(tflite::MicroMutableOpResolver<tOpCount>& r) {
  if (r.AddAdd() != kTfLiteOk) return kTfLiteError;
  if (r.AddConv2D() != kTfLiteOk) return kTfLiteError;
  if (r.AddDepthwiseConv2D() != kTfLiteOk) return kTfLiteError;
  if (r.AddFullyConnected() != kTfLiteOk) return kTfLiteError;
  if (r.AddMean() != kTfLiteOk) return kTfLiteError;
  if (r.AddMul() != kTfLiteOk) return kTfLiteError;
  if (r.AddSoftmax() != kTfLiteOk) return kTfLiteError;
  return kTfLiteOk;
}
