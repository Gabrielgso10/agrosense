import json

from PIL import Image

import criar_manifesto
import rotulagem


def test_lote_novo_ganha_manifesto_e_aparece_na_rotulagem(tmp_path):
    lote = tmp_path / "originais" / "2026-11-13"
    lote.mkdir(parents=True)
    for nome in ("IMG-20261113-WA0001.jpg", "IMG-20261113-WA0002.jpg"):
        Image.new("RGB", (64, 48)).save(lote / nome)
    (lote / "anotacao.txt").write_text("não é foto")
    assert criar_manifesto.criar(lote) == 2
    m = json.loads((lote / "manifesto.json").read_text(encoding="utf-8"))
    assert [i["arquivo"] for i in m["imagens"]] == ["IMG-20261113-WA0001.jpg", "IMG-20261113-WA0002.jpg"]
    assert m["imagens"][0]["rotulo"] is None and len(m["imagens"][0]["sha256"]) == 64
    assert rotulagem.listar_lotes(tmp_path) == [{"lote": "2026-11-13", "fotos": 2, "revisadas": 0}]


def test_atualizar_acrescenta_fotos_novas_sem_mexer_nas_antigas(tmp_path):
    lote = tmp_path / "2026-11-13"
    lote.mkdir()
    Image.new("RGB", (64, 48)).save(lote / "a.jpg")
    criar_manifesto.criar(lote, origem="celular do Leonardo")
    Image.new("RGB", (64, 48)).save(lote / "b.jpg")
    assert criar_manifesto.criar(lote) == 1  # só a foto nova
    m = json.loads((lote / "manifesto.json").read_text(encoding="utf-8"))
    assert [i["arquivo"] for i in m["imagens"]] == ["a.jpg", "b.jpg"] and m["origem"] == "celular do Leonardo"
