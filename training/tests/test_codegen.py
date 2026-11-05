import re

import numpy as np
import pytest

from codegen import (
    UnsupportedOpError,
    arena_header,
    c_array_definition,
    golden_sources,
    ops_header,
    resolver_methods,
    settings_header,
)


def _numbers_in_braces(src: str) -> list[int]:
    body = src[src.index("{") + 1 : src.index("}")]
    return [int(tok, 0) for tok in re.findall(r"-?0x[0-9a-fA-F]+|-?\d+", body)]


def test_model_bytes_round_trip_through_c_array():
    data = bytes(range(256)) * 3
    src = c_array_definition("g_model", data, ctype="unsigned char")
    assert "alignas(16) const unsigned char g_model[]" in src
    assert f"const unsigned int g_model_len = {len(data)};" in src
    assert bytes(_numbers_in_braces(src)) == data


def test_int8_array_keeps_negative_values():
    data = np.array([-128, -1, 0, 127], dtype=np.int8)
    src = c_array_definition("g_golden_input", data, ctype="int8_t")
    assert _numbers_in_braces(src) == [-128, -1, 0, 127]


def test_known_ops_map_to_resolver_methods_sorted_and_unique():
    methods = resolver_methods(["SOFTMAX", "CONV_2D", "CONV_2D", "DEPTHWISE_CONV_2D"])
    assert methods == ["AddConv2D", "AddDepthwiseConv2D", "AddSoftmax"]


def test_unknown_op_fails_loudly_with_its_name():
    with pytest.raises(UnsupportedOpError, match="FOO_BAR"):
        resolver_methods(["CONV_2D", "FOO_BAR"])


def test_ops_header_declares_count_and_registers_each_op():
    src = ops_header(["MEAN", "FULLY_CONNECTED", "MEAN"])
    assert "constexpr int kNumOps = 2;" in src
    assert "r.AddMean()" in src and "r.AddFullyConnected()" in src


def test_settings_header_escapes_labels_and_counts_classes():
    src = settings_header(
        input_shape=(96, 96, 3), input_scale=1.0, input_zero_point=-128,
        output_scale=1 / 256, output_zero_point=-128,
        labels=['espada "sao jorge"', "samambaia"],
    )
    assert "constexpr int kNumClasses = 2;" in src
    assert r'"espada \"sao jorge\""' in src
    assert "constexpr int kInputZeroPoint = -128;" in src


def test_arena_size_gets_margin_and_rounds_up_to_1kb():
    src = arena_header(measured_bytes=100_000, margin=0.2)
    # 100000 * 1.2 = 120000 -> next multiple of 1024 = 120832
    assert "constexpr int kTensorArenaSize = 120832;" in src


def test_golden_sources_declare_matching_lengths():
    x = np.zeros((4, 4, 3), dtype=np.int8)
    y = np.array([-100, 90, -120], dtype=np.int8)
    header, source = golden_sources(x, y, label_index=1, tolerance=2)
    assert "constexpr int kGoldenLabelIndex = 1;" in header
    assert "constexpr int kGoldenTolerance = 2;" in header
    assert "const unsigned int g_golden_input_len = 48;" in source
    assert "const unsigned int g_golden_expected_len = 3;" in source
