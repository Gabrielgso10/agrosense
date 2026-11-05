"""Converte o modelo treinado para int8 e gera os fontes do firmware.

Saídas:
  models/model_int8.tflite
  firmware/main/generated/model_data.{h,cc}, model_ops.h, model_settings.h
"""
import numpy as np
import tensorflow as tf
from ai_edge_litert.interpreter import Interpreter

import codegen
from config import GENERATED, IMG_SIZE, MODELS, read_labels
from evaluation import op_names_in_model


def representative_data():
    for img in np.load(MODELS / "rep_samples.npz")["x"]:
        yield [img[None].astype(np.float32)]


def main():
    model = tf.keras.models.load_model(MODELS / "model.keras")
    saved_model_dir = MODELS / "saved_model"
    model.export(str(saved_model_dir))  # Keras 3 -> SavedModel (caminho recomendado para o conversor)

    conv = tf.lite.TFLiteConverter.from_saved_model(str(saved_model_dir))
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = representative_data
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    tflite_bytes = conv.convert()
    (MODELS / "model_int8.tflite").write_bytes(tflite_bytes)

    ops = op_names_in_model(tflite_bytes)
    itp = Interpreter(model_content=tflite_bytes)
    inp, out = itp.get_input_details()[0], itp.get_output_details()[0]
    in_scale, in_zp = inp["quantization"]
    out_scale, out_zp = out["quantization"]
    labels = read_labels()

    GENERATED.mkdir(parents=True, exist_ok=True)
    header, source = codegen.model_data_sources(tflite_bytes)
    (GENERATED / "model_data.h").write_text(header, encoding="utf-8")
    (GENERATED / "model_data.cc").write_text(source, encoding="utf-8")
    (GENERATED / "model_ops.h").write_text(codegen.ops_header(ops), encoding="utf-8")
    (GENERATED / "model_settings.h").write_text(
        codegen.settings_header((IMG_SIZE, IMG_SIZE, 3), in_scale, in_zp, out_scale, out_zp, labels),
        encoding="utf-8",
    )

    print(f"\nmodel_int8.tflite: {len(tflite_bytes) / 1024:.1f} KB")
    print(f"Operadores ({len(ops)}): {', '.join(ops)}")
    print(f"Entrada: {inp['shape']} {inp['dtype'].__name__}  escala={in_scale:.6g}  zero_point={in_zp}")
    print(f"Saída:   {out['shape']} {out['dtype'].__name__}  escala={out_scale:.6g}  zero_point={out_zp}")
    print(f"Fontes gerados em {GENERATED} — próximo passo: python compare.py")


if __name__ == "__main__":
    main()
