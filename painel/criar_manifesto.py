"""Cria (ou completa) o manifesto.json de um lote de fotos em data/originais/<lote>/, no mesmo
formato do primeiro lote: nome, tamanho e SHA-256 de cada foto, com o rótulo pendente.

  python criar_manifesto.py ../data/originais/2026-11-13
  python criar_manifesto.py ../data/originais/2026-11-13 --origem "celular do Leonardo"

Rodar de novo na mesma pasta só acrescenta as fotos novas; as entradas antigas não mudam.
"""
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

IMAGENS = (".jpg", ".jpeg", ".png")


def criar(pasta, origem: str | None = None) -> int:
    pasta = Path(pasta)
    arquivo = pasta / "manifesto.json"
    if arquivo.is_file():
        manifesto = json.loads(arquivo.read_text(encoding="utf-8"))
    else:
        manifesto = {"data_importacao": date.today().isoformat(), "origem": origem or "fotos do grupo", "imagens": []}
    if origem:
        manifesto["origem"] = origem
    conhecidas = {i["arquivo"] for i in manifesto["imagens"]}
    novas = 0
    for foto in sorted(pasta.iterdir()):
        if foto.suffix.lower() in IMAGENS and foto.name not in conhecidas:
            dados = foto.read_bytes()
            manifesto["imagens"].append({"arquivo": foto.name, "bytes": len(dados),
                                         "sha256": hashlib.sha256(dados).hexdigest(), "rotulo": None})
            novas += 1
    arquivo.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return novas


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pasta", help="pasta do lote, ex.: ../data/originais/2026-11-13")
    p.add_argument("--origem", help="de onde vieram as fotos")
    args = p.parse_args()
    print(f"{criar(args.pasta, args.origem)} fotos novas no manifesto de {args.pasta}")


if __name__ == "__main__":
    main()
