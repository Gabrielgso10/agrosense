"""Utilitários de comparação entre interpretadores."""
import numpy as np
from tflite_micro.tensorflow.lite.python import schema_py_generated as schema

_CODE_TO_NAME = {v: k for k, v in vars(schema.BuiltinOperator).items() if not k.startswith("_")}


def op_names_in_model(tflite_bytes: bytes) -> list[str]:
    """Lê do flatbuffer a lista de operadores que o modelo usa."""
    model = schema.Model.GetRootAs(tflite_bytes, 0)
    names = set()
    for i in range(model.OperatorCodesLength()):
        oc = model.OperatorCodes(i)
        code = max(oc.BuiltinCode(), oc.DeprecatedBuiltinCode())
        names.add(_CODE_TO_NAME.get(code, f"UNKNOWN_{code}"))
    return sorted(names)


def pick_golden_index(y_true, *predictions) -> int:
    """Primeira amostra em que todos os interpretadores acertam — evita teste de ouro instável."""
    ok = np.ones(len(y_true), dtype=bool)
    for pred in predictions:
        ok &= np.asarray(pred) == np.asarray(y_true)
    hits = np.flatnonzero(ok)
    return int(hits[0]) if hits.size else 0


def max_abs_diff_lsb(a, b) -> int:
    return int(np.max(np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16))))
