"""Rotulagem das fotos originais (data/originais/<lote>/): regiões quadradas com a espécie de
cada área de plantio, guardadas em rotulos.json ao lado do manifesto, que fica intocado como
registro dos originais. A exportação gera os recortes em data/especies/<classe>/, com a
sessão no começo do nome para o train.py separar treino e teste por sessão."""
import json
import re
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

CLASSES = ("alface", "cebolinha", "rucula", "vazio")
LADO_MINIMO = 32
DATA_NO_NOME = re.compile(r"(20\d{2})(\d{2})(\d{2})")  # ex.: IMG-20261105-WA0020.jpg


def _pasta_lote(dados: Path, lote: str) -> Path:
    pasta = Path(dados) / "originais" / lote
    if "/" in lote or "\\" in lote or lote.startswith(".") or not (pasta / "manifesto.json").is_file():
        raise ValueError(f"Lote sem manifesto: {lote}")
    return pasta


def _manifesto(dados, lote) -> list:
    return json.loads((_pasta_lote(dados, lote) / "manifesto.json").read_text(encoding="utf-8")).get("imagens", [])


def _rotulos(dados, lote) -> dict:
    arq = _pasta_lote(dados, lote) / "rotulos.json"
    return json.loads(arq.read_text(encoding="utf-8")).get("imagens", {}) if arq.is_file() else {}


def sessao_da_foto(lote: str, arquivo: str) -> str:
    m = DATA_NO_NOME.search(arquivo)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else lote


def caminho_foto(dados, lote, arquivo) -> Path:
    if arquivo not in {i["arquivo"] for i in _manifesto(dados, lote)}:
        raise ValueError(f"Foto fora do manifesto do lote {lote}: {arquivo}")
    return _pasta_lote(dados, lote) / arquivo


def abrir(caminho: Path) -> Image.Image:
    """Aplica a orientação gravada pela câmera, a mesma que o navegador mostra."""
    return ImageOps.exif_transpose(Image.open(caminho)).convert("RGB")


def listar_lotes(dados) -> list:
    pasta = Path(dados) / "originais"
    lotes = []
    for p in sorted(pasta.iterdir()) if pasta.is_dir() else []:
        if (p / "manifesto.json").is_file():
            rotulos = _rotulos(dados, p.name)
            lotes.append({"lote": p.name, "fotos": len(_manifesto(dados, p.name)),
                          "revisadas": sum(1 for r in rotulos.values() if r.get("revisada"))})
    return lotes


def fotos_do_lote(dados, lote) -> list:
    rotulos = _rotulos(dados, lote)
    return [{"arquivo": i["arquivo"], "sessao": sessao_da_foto(lote, i["arquivo"]),
             "revisada": bool(rotulos.get(i["arquivo"], {}).get("revisada")),
             "regioes": rotulos.get(i["arquivo"], {}).get("regioes", [])} for i in _manifesto(dados, lote)]


def salvar(dados, lote, arquivo, regioes, revisada: bool = True) -> dict:
    caminho = caminho_foto(dados, lote, arquivo)
    with Image.open(caminho) as bruta:
        largura, altura = ImageOps.exif_transpose(bruta).size
    limpas = []
    for r in regioes:
        x, y, lado, classe = int(r["x"]), int(r["y"]), int(r["lado"]), r["classe"]
        if classe not in CLASSES:
            raise ValueError(f"classe desconhecida: {classe} (use {', '.join(CLASSES)})")
        if lado < LADO_MINIMO or x < 0 or y < 0 or x + lado > largura or y + lado > altura:
            raise ValueError(f"região fora da foto ou pequena demais: {r}")
        limpas.append({"x": x, "y": y, "lado": lado, "classe": classe})
    arq = _pasta_lote(dados, lote) / "rotulos.json"
    tudo = {"versao": 1, "classes": list(CLASSES), "imagens": _rotulos(dados, lote)}
    tudo["imagens"][arquivo] = {"revisada": bool(revisada), "regioes": limpas}
    arq.write_text(json.dumps(tudo, ensure_ascii=False, indent=2), encoding="utf-8")
    return tudo["imagens"][arquivo]


def exportar(dados, saida) -> dict:
    """Regera os recortes de todos os lotes. Recortes da câmera do nó (__no__) não são tocados."""
    saida, contagem = Path(saida), Counter()
    for lote in (item["lote"] for item in listar_lotes(dados)):
        for antigo in saida.glob(f"*/*__{lote}__*"):
            antigo.unlink()
        for foto in fotos_do_lote(dados, lote):
            if not foto["regioes"]:
                continue
            imagem = abrir(caminho_foto(dados, lote, foto["arquivo"]))
            for i, r in enumerate(foto["regioes"]):
                destino = saida / r["classe"] / f"{foto['sessao']}__{lote}__{Path(foto['arquivo']).stem}__r{i}.jpg"
                destino.parent.mkdir(parents=True, exist_ok=True)
                imagem.crop((r["x"], r["y"], r["x"] + r["lado"], r["y"] + r["lado"])).save(destino, quality=95)
                contagem[r["classe"]] += 1
    return {"recortes": sum(contagem.values()), "por_classe": dict(contagem)}
