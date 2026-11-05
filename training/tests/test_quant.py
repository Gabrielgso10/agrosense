import numpy as np

from quant import dequantize, quantize


def test_pixel_range_maps_to_full_int8_range_with_unit_scale():
    q = quantize(np.array([0.0, 128.0, 255.0]), scale=1.0, zero_point=-128)
    assert q.dtype == np.int8
    assert q.tolist() == [-128, 0, 127]


def test_values_outside_range_are_clamped():
    q = quantize(np.array([-10.0, 300.0]), scale=1.0, zero_point=-128)
    assert q.tolist() == [-128, 127]


def test_rounds_half_away_from_zero_like_tflite():
    # numpy.round would give 0 and -0 (banker's rounding); TFLite uses std::round
    q = quantize(np.array([0.5, -0.5, 1.5]), scale=1.0, zero_point=0)
    assert q.tolist() == [1, -1, 2]


def test_dequantize_inverts_quantize_within_half_step():
    x = np.array([0.1, 0.37, -0.8])
    scale, zp = 0.01, 5
    back = dequantize(quantize(x, scale, zp), scale, zp)
    assert np.allclose(back, x, atol=scale / 2 + 1e-9)
