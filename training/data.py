"""Carga do dataset com o MESMO pré-processamento que o firmware vai reproduzir:
recorte central quadrado -> redimensiona para IMG_SIZE (bilinear) -> pixels 0..255.
A normalização para [-1, 1] fica DENTRO do modelo (camada Rescaling)."""
import numpy as np
import tensorflow as tf

from config import IMG_SIZE, SEED

AUTOTUNE = tf.data.AUTOTUNE


def square_crop_resize(image):
    image = tf.cast(image, tf.float32)
    h, w = tf.shape(image)[0], tf.shape(image)[1]
    side = tf.minimum(h, w)
    image = tf.image.crop_to_bounding_box(image, (h - side) // 2, (w - side) // 2, side, side)
    return tf.image.resize(image, (IMG_SIZE, IMG_SIZE), method="bilinear")


def load(dataset: str | None, data_dir: str | None):
    """Retorna (train, val, labels) com amostras individuais (sem batch)."""
    if data_dir:
        # Estrutura esperada: data_dir/<classe>/*.jpg
        train, val = tf.keras.utils.image_dataset_from_directory(
            data_dir, validation_split=0.2, subset="both", seed=SEED, batch_size=None,
            image_size=(IMG_SIZE, IMG_SIZE), interpolation="bilinear", crop_to_aspect_ratio=True,
        )
        labels = list(train.class_names)
    else:
        import tensorflow_datasets as tfds

        (train, val), info = tfds.load(
            dataset, split=["train[:80%]", "train[80%:]"], as_supervised=True, with_info=True
        )
        labels = list(info.features["label"].names)
        train = train.map(lambda x, y: (square_crop_resize(x), y), AUTOTUNE)
        val = val.map(lambda x, y: (square_crop_resize(x), y), AUTOTUNE)
    return train, val, labels


def augment(image, label):
    """Aumento de dados só no treino e fora do modelo (não vai para o .tflite)."""
    image = tf.image.random_flip_left_right(image)
    image = tf.image.random_brightness(image, max_delta=25.0)
    image = tf.image.random_contrast(image, 0.8, 1.2)
    return tf.clip_by_value(image, 0.0, 255.0), label


def to_numpy(ds, limit: int):
    """Materializa até `limit` amostras como uint8 (o que a câmera entrega) + rótulos."""
    xs, ys = [], []
    for x, y in ds.take(limit):
        xs.append(np.clip(np.round(x.numpy()), 0, 255).astype(np.uint8))
        ys.append(int(y.numpy()))
    return np.stack(xs), np.array(ys, dtype=np.int32)
