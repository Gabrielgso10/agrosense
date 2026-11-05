"""Compara os três interpretadores nas mesmas imagens e gera o teste de ouro do firmware.

  Keras (float32)  x  LiteRT (int8)  x  TFLM (int8, o mesmo interpretador do microcontrolador)

Saídas:
  models/compare_report.md / .json, models/confusion_matrix_tflm.png
  firmware/main/generated/golden_data.{h,cc}, arena_config.h
"""
import json
import os
import re
import tempfile

import numpy as np
import tensorflow as tf
from ai_edge_litert.interpreter import Interpreter, OpResolverType
from tflite_micro import runtime

import codegen
from config import ARENA_MARGIN, GENERATED, GOLDEN_TOLERANCE, MODELS, read_labels
from evaluation import max_abs_diff_lsb, pick_golden_index
from quant import quantize


def tflm_arena_bytes(itp) -> int:
    """O TFLM imprime o uso da arena no stderr (nível C); capturamos no descritor 2."""
    saved = os.dup(2)
    with tempfile.TemporaryFile() as tmp:
        os.dup2(tmp.fileno(), 2)
        try:
            itp.print_allocations()
        finally:
            os.dup2(saved, 2)
            os.close(saved)
        tmp.seek(0)
        text = tmp.read().decode(errors="replace")
    match = re.search(r"Arena allocation total (\d+) bytes", text)
    if not match:
        raise RuntimeError(f"Não achei o total da arena na saída do TFLM:\n{text}")
    return int(match.group(1))


def main():
    labels = read_labels()
    val = np.load(MODELS / "val_samples.npz")
    x, y = val["x"], val["y"]
    model_path = str(MODELS / "model_int8.tflite")

    # 1) Keras float32
    keras_model = tf.keras.models.load_model(MODELS / "model.keras")
    pred_float = keras_model.predict(x.astype(np.float32), batch_size=32, verbose=0).argmax(1)

    # 2) LiteRT int8 com kernels de REFERÊNCIA: mesma aritmética do TFLM.
    #    (o delegate XNNPACK, padrão no PC, arredonda diferente e se afasta até ~20 LSB)
    lite = Interpreter(model_path=model_path, experimental_op_resolver_type=OpResolverType.BUILTIN_REF)
    lite.allocate_tensors()
    inp, out = lite.get_input_details()[0], lite.get_output_details()[0]
    in_scale, in_zp = inp["quantization"]
    xq = quantize(x.astype(np.float32), in_scale, in_zp)
    out_lite = []
    for sample in xq:
        lite.set_tensor(inp["index"], sample[None])
        lite.invoke()
        out_lite.append(lite.get_tensor(out["index"])[0].copy())
    out_lite = np.stack(out_lite)

    # 3) TFLM int8 — mesmo interpretador e kernels de referência do firmware
    tflm = runtime.Interpreter.from_file(model_path)
    out_tflm = []
    for sample in xq:
        tflm.set_input(sample[None], 0)
        tflm.invoke()
        out_tflm.append(np.array(tflm.get_output(0))[0].copy())
    out_tflm = np.stack(out_tflm)
    arena = tflm_arena_bytes(tflm)

    pred_lite, pred_tflm = out_lite.argmax(1), out_tflm.argmax(1)
    report = {
        "amostras": int(len(y)),
        "acuracia_keras_float": float((pred_float == y).mean()),
        "acuracia_litert_int8": float((pred_lite == y).mean()),
        "acuracia_tflm_int8": float((pred_tflm == y).mean()),
        "concordancia_float_vs_int8": float((pred_float == pred_lite).mean()),
        "concordancia_litert_vs_tflm": float((pred_lite == pred_tflm).mean()),
        "max_diff_litert_vs_tflm_lsb": max_abs_diff_lsb(out_lite, out_tflm),
        "arena_tflm_bytes": arena,
        "modelo_bytes": os.path.getsize(model_path),
    }

    # Teste de ouro: amostra em que os três acertam; saída esperada = TFLM no PC
    g = pick_golden_index(y, pred_float, pred_lite, pred_tflm)
    header, source = codegen.golden_sources(xq[g], out_tflm[g], int(y[g]), GOLDEN_TOLERANCE)
    GENERATED.mkdir(parents=True, exist_ok=True)
    (GENERATED / "golden_data.h").write_text(header, encoding="utf-8")
    (GENERATED / "golden_data.cc").write_text(source, encoding="utf-8")
    (GENERATED / "arena_config.h").write_text(codegen.arena_header(arena, ARENA_MARGIN), encoding="utf-8")
    report["golden_indice"], report["golden_classe"] = g, labels[int(y[g])]

    # Matriz de confusão do TFLM (vai para o cap. 3)
    from sklearn.metrics import ConfusionMatrixDisplay

    disp = ConfusionMatrixDisplay.from_predictions(y, pred_tflm, display_labels=labels, xticks_rotation=45, colorbar=False)
    disp.ax_.set_title("Matriz de confusão — TFLM int8")
    disp.figure_.tight_layout()
    disp.figure_.savefig(MODELS / "confusion_matrix_tflm.png", dpi=150)

    (MODELS / "compare_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    rows = [
        ("Amostras de validação", report["amostras"]),
        ("Acurácia Keras (float32)", f"{report['acuracia_keras_float']:.1%}"),
        ("Acurácia LiteRT (int8)", f"{report['acuracia_litert_int8']:.1%}"),
        ("Acurácia TFLM (int8)", f"{report['acuracia_tflm_int8']:.1%}"),
        ("Concordância float × int8", f"{report['concordancia_float_vs_int8']:.1%}"),
        ("Concordância LiteRT × TFLM", f"{report['concordancia_litert_vs_tflm']:.1%}"),
        ("Maior diferença LiteRT × TFLM", f"{report['max_diff_litert_vs_tflm_lsb']} LSB"),
        ("Tamanho do modelo", f"{report['modelo_bytes'] / 1024:.1f} KB"),
        ("Arena TFLM medida (PC)", f"{arena / 1024:.1f} KB"),
    ]
    md = "| Métrica | Valor |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows) + "\n"
    (MODELS / "compare_report.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"Teste de ouro: amostra {g} ({labels[int(y[g])]}) gravada em {GENERATED}")


if __name__ == "__main__":
    main()
