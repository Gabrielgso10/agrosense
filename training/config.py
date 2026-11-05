"""Parâmetros compartilhados. Mudar IMG_SIZE aqui muda o contrato com o firmware."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
GENERATED = ROOT / "firmware" / "main" / "generated"

IMG_SIZE = 96          # entrada 96x96x3 (RGB)
ALPHA = 0.35           # largura da MobileNetV2
SEED = 42
REP_SAMPLES = 200      # imagens para calibrar a quantização int8
VAL_SAMPLES = 300      # imagens para a comparação entre interpretadores
GOLDEN_TOLERANCE = 2   # LSB: kernels otimizados (ESP-NN) podem diferir 1-2 unidades da referência
ARENA_MARGIN = 0.3     # folga sobre a arena medida no PC (ESP-NN pede buffers de rascunho)


def read_labels(path: Path = MODELS / "labels.txt") -> list[str]:
    """Um rótulo por linha; preserva espaços e acentos dos nomes das pastas."""
    return [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
