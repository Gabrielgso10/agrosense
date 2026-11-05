"""Treino por transfer learning: MobileNetV2 (alpha 0.35) a 96x96.

Exemplos:
  python train.py                                  # tf_flowers (placeholder da S1)
  python train.py --data-dir ../data/especies      # dataset do grupo (pastas por classe)
"""
import argparse
import json

import numpy as np
import tensorflow as tf

import data
from config import ALPHA, IMG_SIZE, MODELS, REP_SAMPLES, SEED, VAL_SAMPLES


def build_model(num_classes: int, weights: str | None) -> tf.keras.Model:
    inputs = tf.keras.Input((IMG_SIZE, IMG_SIZE, 3), name="image")  # pixels 0..255
    x = tf.keras.layers.Rescaling(1 / 127.5, offset=-1.0)(inputs)     # [-1, 1], como a MobileNetV2 espera
    base = tf.keras.applications.MobileNetV2(
        input_shape=(IMG_SIZE, IMG_SIZE, 3), alpha=ALPHA, include_top=False, weights=weights
    )
    base.trainable = False  # S2: descongelar as últimas camadas para fine-tuning
    x = base(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax", name="scores")(x)
    return tf.keras.Model(inputs, outputs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="tf_flowers", help="nome no TensorFlow Datasets")
    p.add_argument("--data-dir", help="pasta com uma subpasta por classe (substitui --dataset)")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--weights", default="imagenet", help="'imagenet' ou 'none'")
    args = p.parse_args()

    tf.keras.utils.set_random_seed(SEED)
    MODELS.mkdir(parents=True, exist_ok=True)
    train, val, labels = data.load(args.dataset, args.data_dir)
    print(f"Classes ({len(labels)}): {labels}")

    # Amostras fixas para calibrar a quantização e para a comparação/teste de ouro
    x_rep, _ = data.to_numpy(train, REP_SAMPLES)
    x_val, y_val = data.to_numpy(val, VAL_SAMPLES)
    np.savez_compressed(MODELS / "rep_samples.npz", x=x_rep)
    np.savez_compressed(MODELS / "val_samples.npz", x=x_val, y=y_val)

    train_b = train.shuffle(1000, seed=SEED).map(data.augment, data.AUTOTUNE).batch(args.batch).prefetch(data.AUTOTUNE)
    val_b = val.batch(args.batch).prefetch(data.AUTOTUNE)

    model = build_model(len(labels), None if args.weights == "none" else args.weights)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    history = model.fit(train_b, validation_data=val_b, epochs=args.epochs)

    model.save(MODELS / "model.keras")
    (MODELS / "labels.txt").write_text("\n".join(labels) + "\n", encoding="utf-8")
    (MODELS / "train_history.json").write_text(json.dumps(history.history, indent=2), encoding="utf-8")
    print(f"Modelo salvo em {MODELS / 'model.keras'} — próximo passo: python convert.py")


if __name__ == "__main__":
    main()
