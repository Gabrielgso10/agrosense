"""Gera os arquivos C++ que o firmware consome (firmware/main/generated/)."""
import math

import numpy as np

BANNER = "// GERADO AUTOMATICAMENTE pelos scripts de training/ — não edite à mão.\n"

# Operador do TFLite -> método do tflite::MicroMutableOpResolver
OP_TO_METHOD = {
    "ABS": "AddAbs",
    "ADD": "AddAdd",
    "AVERAGE_POOL_2D": "AddAveragePool2D",
    "CONCATENATION": "AddConcatenation",
    "CONV_2D": "AddConv2D",
    "DEPTHWISE_CONV_2D": "AddDepthwiseConv2D",
    "DEQUANTIZE": "AddDequantize",
    "FULLY_CONNECTED": "AddFullyConnected",
    "HARD_SWISH": "AddHardSwish",
    "LEAKY_RELU": "AddLeakyRelu",
    "LOGISTIC": "AddLogistic",
    "MAX_POOL_2D": "AddMaxPool2D",
    "MEAN": "AddMean",
    "MUL": "AddMul",
    "PAD": "AddPad",
    "QUANTIZE": "AddQuantize",
    "RELU": "AddRelu",
    "RELU6": "AddRelu6",
    "RESHAPE": "AddReshape",
    "SOFTMAX": "AddSoftmax",
    "SUB": "AddSub",
    "TANH": "AddTanh",
    "TRANSPOSE": "AddTranspose",
}


class UnsupportedOpError(ValueError):
    pass


def c_array_definition(name: str, data, ctype: str, align: int = 16) -> str:
    if isinstance(data, (bytes, bytearray)):
        values = [f"0x{b:02x}" for b in data]
    else:
        values = [str(int(v)) for v in np.asarray(data).ravel()]
    rows = [", ".join(values[i : i + 12]) for i in range(0, len(values), 12)]
    body = ",\n  ".join(rows)
    return (
        f"alignas({align}) const {ctype} {name}[] = {{\n  {body}\n}};\n"
        f"const unsigned int {name}_len = {len(values)};\n"
    )


def resolver_methods(op_names) -> list[str]:
    unique = sorted(set(op_names))
    unknown = [op for op in unique if op not in OP_TO_METHOD]
    if unknown:
        raise UnsupportedOpError(
            "Operadores sem mapeamento para o MicroMutableOpResolver: "
            + ", ".join(unknown)
            + ". Adicione em OP_TO_METHOD (codegen.py) se o TFLM suportar."
        )
    return sorted(OP_TO_METHOD[op] for op in unique)


def ops_header(op_names) -> str:
    methods = resolver_methods(op_names)
    calls = "\n".join(f"  if (r.{m}() != kTfLiteOk) return kTfLiteError;" for m in methods)
    return (
        BANNER
        + "#pragma once\n"
        + '#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"\n\n'
        + f"constexpr int kNumOps = {len(methods)};\n\n"
        + "template <unsigned int tOpCount>\n"
        + "inline TfLiteStatus RegisterOps(tflite::MicroMutableOpResolver<tOpCount>& r) {\n"
        + calls
        + "\n  return kTfLiteOk;\n}\n"
    )


def _cfloat(x: float) -> str:
    return f"{x:.9e}f"


def _cstring(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def settings_header(input_shape, input_scale, input_zero_point, output_scale, output_zero_point, labels) -> str:
    h, w, c = input_shape
    label_list = ", ".join(_cstring(label) for label in labels)
    return (
        BANNER
        + "#pragma once\n#include <cmath>\n#include <cstdint>\n\n"
        + f"constexpr int kInputHeight = {h};\n"
        + f"constexpr int kInputWidth = {w};\n"
        + f"constexpr int kInputChannels = {c};\n"
        + f"constexpr float kInputScale = {_cfloat(input_scale)};\n"
        + f"constexpr int kInputZeroPoint = {int(input_zero_point)};\n"
        + f"constexpr float kOutputScale = {_cfloat(output_scale)};\n"
        + f"constexpr int kOutputZeroPoint = {int(output_zero_point)};\n"
        + f"constexpr int kNumClasses = {len(labels)};\n"
        + f"constexpr const char* kLabels[kNumClasses] = {{{label_list}}};\n\n"
        + "// Pixel RGB888 (0..255) -> entrada int8 do modelo. Mesma regra do quant.py.\n"
        + "inline int8_t QuantizePixel(uint8_t pixel) {\n"
        + "  int32_t q = static_cast<int32_t>(std::lround(pixel / kInputScale)) + kInputZeroPoint;\n"
        + "  if (q < -128) q = -128;\n  if (q > 127) q = 127;\n"
        + "  return static_cast<int8_t>(q);\n}\n\n"
        + "inline float DequantizeOutput(int8_t q) { return (q - kOutputZeroPoint) * kOutputScale; }\n"
    )


def arena_header(measured_bytes: int, margin: float = 0.2, align: int = 1024) -> str:
    size = math.ceil(measured_bytes * (1 + margin) / align) * align
    return (
        BANNER
        + "#pragma once\n\n"
        + f"// Arena medida pelo TFLM no PC: {measured_bytes} bytes; +{margin:.0%} de folga.\n"
        + f"constexpr int kTensorArenaSize = {size};\n"
    )


def model_data_sources(tflite_bytes: bytes) -> tuple[str, str]:
    header = (
        BANNER
        + "#pragma once\n\n"
        + "extern const unsigned char g_model[];\n"
        + "extern const unsigned int g_model_len;\n"
    )
    source = BANNER + '#include "model_data.h"\n\n' + c_array_definition("g_model", tflite_bytes, "unsigned char")
    return header, source


def golden_sources(input_int8, expected_int8, label_index: int, tolerance: int) -> tuple[str, str]:
    header = (
        BANNER
        + "#pragma once\n#include <cstdint>\n\n"
        + "extern const int8_t g_golden_input[];\n"
        + "extern const unsigned int g_golden_input_len;\n"
        + "extern const int8_t g_golden_expected[];\n"
        + "extern const unsigned int g_golden_expected_len;\n\n"
        + f"constexpr int kGoldenLabelIndex = {int(label_index)};\n"
        + f"constexpr int kGoldenTolerance = {int(tolerance)};\n"
    )
    source = (
        BANNER
        + '#include "golden_data.h"\n\n'
        + c_array_definition("g_golden_input", np.asarray(input_int8, dtype=np.int8), "int8_t")
        + "\n"
        + c_array_definition("g_golden_expected", np.asarray(expected_int8, dtype=np.int8), "int8_t")
    )
    return header, source
