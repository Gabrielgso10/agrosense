"""Treino por transfer learning: MobileNetV2 (alpha 0.35) a 96x96.

Exemplos:
  python train.py                                  # tf_flowers (placeholder da S1)
  python train.py --data-dir ../data/especies --teste-ultima-sessao --ajuste-fino 5
                                                   # dataset do grupo, teste na sessão mais recente
"""
import argparse
import json

import numpy as np
import tensorflow as tf

import data
from config import ALPHA, IMG_SIZE, MODELS, REP_SAMPLES, SEED, VAL_SAMPLES


def build_model(num_classes: int, weights: str | None):
    inputs = tf.keras.Input((IMG_SIZE, IMG_SIZE, 3), name="image")  # pixels 0..255
    x = tf.keras.layers.Rescaling(1 / 127.5, offset=-1.0)(inputs)     # [-1, 1], como a MobileNetV2 espera
    base = tf.keras.applications.MobileNetV2(
        input_shape=(IMG_SIZE, IMG_SIZE, 3), alpha=ALPHA, include_top=False, weights=weights
    )
    base.trainable = False  # o ajuste fino (--ajuste-fino) libera as últimas camadas depois
    x = base(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax", name="scores")(x)
    return tf.keras.Model(inputs, outputs), base


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="tf_flowers", help="nome no TensorFlow Datasets")
    p.add_argument("--data-dir", help="pasta com uma subpasta por classe (substitui --dataset)")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--weights", default="imagenet", help="'imagenet' ou 'none'")
    p.add_argument("--teste-ultima-sessao", action="store_true",
                   help="avalia na sessão de fotos mais recente, sem nenhuma foto dela no treino")
    p.add_argument("--teste-sessoes", help="sessões de teste separadas por vírgula, ex.: 2026-11-19,2026-11-26")
    p.add_argument("--ajuste-fino", type=int, default=0,
                   help="épocas extras com as últimas camadas da MobileNetV2 liberadas (taxa de aprendizado baixa)")
    args = p.parse_args()
    teste = "ultima" if args.teste_ultima_sessao else (
        [x.strip() for x in args.teste_sessoes.split(",") if x.strip()] if args.teste_sessoes else None)

    tf.keras.utils.set_random_seed(SEED)
    MODELS.mkdir(parents=True, exist_ok=True)
    train, val, labels = data.load(args.dataset, args.data_dir, teste)
    print(f"Classes ({len(labels)}): {labels}")

    # Amostras fixas para calibrar a quantização e para a comparação/teste de ouro
    x_rep, _ = data.to_numpy(train, REP_SAMPLES)
    x_val, y_val = data.to_numpy(val, VAL_SAMPLES)
    np.savez_compressed(MODELS / "rep_samples.npz", x=x_rep)
    np.savez_compressed(MODELS / "val_samples.npz", x=x_val, y=y_val)

    train_b = train.shuffle(1000, seed=SEED).map(data.augment, data.AUTOTUNE).batch(args.batch).prefetch(data.AUTOTUNE)
    val_b = val.batch(args.batch).prefetch(data.AUTOTUNE)

    model, base = build_model(len(labels), None if args.weights == "none" else args.weights)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    history = model.fit(train_b, validation_data=val_b, epochs=args.epochs)
    historico = {k: list(v) for k, v in history.history.items()}

    if args.ajuste_fino > 0:
        # Libera as ~30 últimas camadas; a BatchNormalization continua congelada (a base roda com training=False)
        base.trainable = True
        for camada in base.layers[:-30]:
            camada.trainable = False
        for camada in base.layers:
            if isinstance(camada, tf.keras.layers.BatchNormalization):
                camada.trainable = False
        model.compile(optimizer=tf.keras.optimizers.Adam(1e-5), loss="sparse_categorical_crossentropy",
                      metrics=["accuracy"])
        ajuste = model.fit(train_b, validation_data=val_b, epochs=args.ajuste_fino)
        for k, v in ajuste.history.items():
            historico.setdefault(k, []).extend(v)

    model.save(MODELS / "model.keras")
    (MODELS / "labels.txt").write_text("\n".join(labels) + "\n", encoding="utf-8")
    (MODELS / "train_history.json").write_text(json.dumps(historico, indent=2), encoding="utf-8")
    divisao = {"teste": teste or "aleatoria", "classes": labels, "epocas": args.epochs, "ajuste_fino": args.ajuste_fino}
    (MODELS / "divisao.json").write_text(json.dumps(divisao, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Modelo salvo em {MODELS / 'model.keras'} — próximo passo: python convert.py")


if __name__ == "__main__":
    main()
