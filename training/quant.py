"""Quantização int8 com a mesma regra do TFLite/TFLM (arredonda para longe do zero)."""
import numpy as np


def quantize(x, scale: float, zero_point: int) -> np.ndarray:
    v = np.asarray(x, dtype=np.float64) / scale
    rounded = np.sign(v) * np.floor(np.abs(v) + 0.5)
    return np.clip(rounded + zero_point, -128, 127).astype(np.int8)


def dequantize(q, scale: float, zero_point: int) -> np.ndarray:
    return (np.asarray(q, dtype=np.float32) - zero_point) * scale
