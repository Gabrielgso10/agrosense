"""Confere se o recorte + redimensionamento do firmware (C++) bate com o
tf.image.resize usado no treino. Rode no ambiente de treino:  python test_resize_parity.py"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import tensorflow as tf

HERE = Path(__file__).resolve().parent
MAIN = HERE.parents[1] / "main"


def decode_rgb565_be(raw: np.ndarray) -> np.ndarray:
    v = (raw[..., 0].astype(np.uint16) << 8) | raw[..., 1]
    r5, g6, b5 = (v >> 11) & 0x1F, (v >> 5) & 0x3F, v & 0x1F
    return np.stack([(r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2)], -1).astype(np.float32)


def run_case(tmp: Path, harness: Path, frame: np.ndarray, x: int, y: int, side: int, out: int) -> int:
    h, w = frame.shape[:2]
    (tmp / "in.bin").write_bytes(frame.tobytes())
    subprocess.run([str(harness), str(tmp / "in.bin"), str(w), str(h), str(x), str(y), str(side), str(out),
                    str(tmp / "out.bin")], check=True)
    ours = np.frombuffer((tmp / "out.bin").read_bytes(), np.uint8).reshape(out, out, 3).astype(np.int16)
    crop = decode_rgb565_be(frame[y:y + side, x:x + side])
    ref = tf.image.resize(crop[None], (out, out), method="bilinear").numpy()[0]
    ref = np.floor(np.clip(ref, 0, 255) + 0.5).astype(np.int16)
    return int(np.abs(ours - ref).max())


def test_firmware_resize_matches_tensorflow():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        harness = tmp / "resize_harness"
        subprocess.run(["g++", "-std=c++17", "-O2", f"-I{MAIN / 'logic'}", f"-I{MAIN / 'generated'}",
                        str(HERE / "resize_harness.cc"), str(MAIN / "logic" / "preprocess.cc"), "-o", str(harness)],
                       check=True)
        rng = np.random.default_rng(0)
        frame = rng.integers(0, 256, (240, 320, 2), dtype=np.uint8)  # quadro QVGA RGB565 aleatório
        cases = [(0, 0, 240, 96), (37, 21, 150, 96), (214, 60, 106, 96), (5, 7, 60, 96), (100, 50, 96, 96)]
        worst = max(run_case(tmp, harness, frame, *c) for c in cases)
        print(f"maior diferença firmware x TensorFlow: {worst} (em 0..255)")
        assert worst <= 1


if __name__ == "__main__":
    test_firmware_resize_matches_tensorflow()
    print("OK")
