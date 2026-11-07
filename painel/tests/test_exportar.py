import io
import json
import sqlite3

from PIL import Image

import exportar_dataset
import store


def leitura(n, especie, fixa):
    return json.dumps({"vaso": n, "especie": especie, "fixa": fixa, "confianca": 0.1, "solo_pct": 60,
                       "liga_abaixo": 55, "desliga_em": 70, "bomba": False, "motivo": "ocioso"}).encode()


def test_exporta_recortes_rotulados_pela_especie_fixa(tmp_path):
    db = tmp_path / "agrosense.db"
    c = sqlite3.connect(db)
    store.criar_tabelas(c)
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (40, 120, 40)).save(buf, "JPEG")
    store.ingerir(c, "agrosense/camera", buf.getvalue(), 1000.0)
    info = {"largura": 320, "altura": 240, "vasos": [
        {"vaso": 0, "x": 0, "y": 60, "lado": 106, "visto": "", "confianca": 0.1},
        {"vaso": 1, "x": 107, "y": 60, "lado": 106, "visto": "", "confianca": 0.1},
        {"vaso": 2, "x": 214, "y": 60, "lado": 106, "visto": "rucula", "confianca": 0.9}]}
    store.ingerir(c, "agrosense/camera/info", json.dumps(info).encode(), 1001.0)
    store.ingerir(c, "agrosense/vaso/0", leitura(0, "alface", True), 1002.0)
    store.ingerir(c, "agrosense/vaso/1", leitura(1, "vazio", True), 1002.0)
    store.ingerir(c, "agrosense/vaso/2", leitura(2, "rucula", False), 1002.0)  # rótulo da própria câmera
    c.close()

    saida = tmp_path / "dataset"
    assert exportar_dataset.exportar(db, saida) == 2  # sem a câmera rotulando a si mesma
    assert sorted(p.parent.name for p in saida.rglob("*.jpg")) == ["alface", "vazio"]
    assert Image.open(next((saida / "alface").glob("*.jpg"))).size == (106, 106)
    # a sessão (data) vai no começo do nome, para o train.py separar treino e teste por sessão
    assert all(p.name[4] == "-" and "__no__" in p.name for p in saida.rglob("*.jpg"))
    assert exportar_dataset.exportar(db, saida) == 0  # rodar de novo não duplica
