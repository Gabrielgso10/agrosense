"""Carga do dataset com o MESMO pré-processamento que o firmware vai reproduzir:
recorte central quadrado -> redimensiona para IMG_SIZE (bilinear) -> pixels 0..255.
A normalização para [-1, 1] fica DENTRO do modelo (camada Rescaling)."""
import random
from pathlib import Path

import numpy as np
import tensorflow as tf

from config import IMG_SIZE, SEED
from sessoes import dividir_por_sessao

IMAGENS = (".jpg", ".jpeg", ".png")

AUTOTUNE = tf.data.AUTOTUNE


def square_crop_resize(image):
    image = tf.cast(image, tf.float32)
    h, w = tf.shape(image)[0], tf.shape(image)[1]
    side = tf.minimum(h, w)
    image = tf.image.crop_to_bounding_box(image, (h - side) // 2, (w - side) // 2, side, side)
    return tf.image.resize(image, (IMG_SIZE, IMG_SIZE), method="bilinear")


def listar_imagens(data_dir):
    """(caminhos, rótulos, classes): uma subpasta por classe, em ordem alfabética."""
    raiz = Path(data_dir)
    classes = sorted(p.name for p in raiz.iterdir() if p.is_dir() and not p.name.startswith("."))
    caminhos, rotulos = [], []
    for indice, classe in enumerate(classes):
        for arquivo in sorted((raiz / classe).iterdir()):
            if arquivo.suffix.lower() in IMAGENS:
                caminhos.append(arquivo)
                rotulos.append(indice)
    if not caminhos:
        raise ValueError(f"Nenhuma imagem em {raiz}/<classe>/. Exportem os recortes da rotulagem primeiro.")
    return caminhos, rotulos, classes


def _dataset(caminhos, rotulos):
    def ler(caminho, rotulo):
        imagem = tf.io.decode_image(tf.io.read_file(caminho), channels=3, expand_animations=False)
        return square_crop_resize(imagem), rotulo

    return tf.data.Dataset.from_tensor_slices(([str(c) for c in caminhos], rotulos)).map(ler, AUTOTUNE)


def load(dataset: str | None, data_dir: str | None, teste=None):
    """Retorna (train, val, labels) com amostras individuais (sem batch).
    teste = "ultima" ou lista de sessões: a validação vira um teste independente por sessão."""
    if data_dir:
        caminhos, rotulos, labels = listar_imagens(data_dir)
        rotulo_de = dict(zip(caminhos, rotulos))
        if teste:
            treino, avaliacao, sessoes = dividir_por_sessao(caminhos, teste)
            print(f"Teste independente: sessões {', '.join(sessoes)} ({len(avaliacao)} imagens); "
                  f"treino: {len(treino)} imagens das demais sessões")
        else:
            embaralhados = list(caminhos)
            random.Random(SEED).shuffle(embaralhados)
            corte = int(len(embaralhados) * 0.8)
            treino, avaliacao = embaralhados[:corte], embaralhados[corte:]
            print("Aviso: divisão aleatória; fotos da mesma sessão podem cair no treino e na validação. "
                  "Para os resultados do TCC, use --teste-ultima-sessao.")
        train = _dataset(treino, [rotulo_de[c] for c in treino])
        val = _dataset(avaliacao, [rotulo_de[c] for c in avaliacao])
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
