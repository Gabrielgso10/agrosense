"""Transforma as fotos arquivadas pelo painel em dataset rotulado: um recorte por vaso, na
pasta da espécie, pronto para o train.py. Por padrão só usa vasos com espécie fixa, cujo
rótulo é a verdade de quem montou a bancada: a espécie que a própria câmera confirmou não
deve servir de rótulo para treinar a câmera.

  python exportar_dataset.py                       # grava em ../data/especies
  python exportar_dataset.py --saida outra/pasta
"""
import argparse
import io
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from PIL import Image

import store

AQUI = Path(__file__).resolve().parent


def exportar(db_path, saida, incluir_camera: bool = False) -> int:
    saida, novos = Path(saida), 0
    conn = sqlite3.connect(db_path)
    try:
        for a in store.amostras_dataset(conn):
            imagem = None
            for n, x, y, lado in a["rois"]:
                rotulo = a["especies"].get(n)
                if rotulo is None or (not rotulo["fixa"] and not incluir_camera):
                    continue
                momento = datetime.fromtimestamp(a["ts"])  # sessão = dia da foto, no começo do nome
                destino = saida / rotulo["especie"] / f"{momento:%Y-%m-%d}__no__{momento:%H%M%S}_vaso{n}.jpg"
                if destino.exists():
                    continue
                imagem = imagem or Image.open(io.BytesIO(a["jpeg"])).convert("RGB")
                if x < 0 or y < 0 or x + lado > imagem.width or y + lado > imagem.height:
                    continue
                destino.parent.mkdir(parents=True, exist_ok=True)
                imagem.crop((x, y, x + lado, y + lado)).save(destino, quality=95)
                novos += 1
    finally:
        conn.close()
    return novos


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(AQUI / "agrosense.db"))
    p.add_argument("--saida", default=str(AQUI.parent / "data" / "especies"))
    p.add_argument("--incluir-camera", action="store_true", help="usa também a espécie confirmada pela câmera")
    args = p.parse_args()
    novos = exportar(args.db, args.saida, args.incluir_camera)
    contagem = Counter(f.parent.name for f in Path(args.saida).rglob("*.jpg"))
    print(f"{novos} recortes novos em {args.saida}")
    for especie, total in sorted(contagem.items()):
        print(f"  {especie}: {total} imagens")


if __name__ == "__main__":
    main()
