import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app as painel
import rotulagem

LOTE = "2026-11-06"


@pytest.fixture
def dados(tmp_path):
    lote = tmp_path / "originais" / LOTE
    lote.mkdir(parents=True)
    imagens = []
    for nome, tamanho in (("IMG-20261105-WA0001.jpg", (400, 300)), ("foto.jpg", (300, 400))):
        Image.new("RGB", tamanho, (40, 110, 40)).save(lote / nome, "JPEG")
        imagens.append({"arquivo": nome, "bytes": (lote / nome).stat().st_size, "sha256": "x", "rotulo": None})
    (lote / "manifesto.json").write_text(json.dumps({"data_importacao": LOTE, "origem": "teste", "imagens": imagens}),
                                         encoding="utf-8")
    return tmp_path


def test_lotes_mostram_o_progresso(dados):
    assert rotulagem.listar_lotes(dados) == [{"lote": LOTE, "fotos": 2, "revisadas": 0}]
    rotulagem.salvar(dados, LOTE, "foto.jpg", [], revisada=True)  # foto revisada sem planta útil
    assert rotulagem.listar_lotes(dados)[0]["revisadas"] == 1


def test_sessao_vem_da_data_no_nome_ou_do_lote(dados):
    fotos = {f["arquivo"]: f for f in rotulagem.fotos_do_lote(dados, LOTE)}
    assert fotos["IMG-20261105-WA0001.jpg"]["sessao"] == "2026-11-05"
    assert fotos["foto.jpg"]["sessao"] == LOTE


def test_salvar_valida_classe_limites_e_arquivo(dados):
    with pytest.raises(ValueError, match="classe"):
        rotulagem.salvar(dados, LOTE, "foto.jpg", [{"x": 0, "y": 0, "lado": 100, "classe": "feijao"}])
    with pytest.raises(ValueError, match="fora da foto"):
        rotulagem.salvar(dados, LOTE, "foto.jpg", [{"x": 250, "y": 0, "lado": 100, "classe": "alface"}])
    with pytest.raises(ValueError, match="manifesto"):
        rotulagem.salvar(dados, LOTE, "../../segredo.jpg", [])


def test_exportar_regera_os_recortes_quando_o_rotulo_muda(dados):
    rotulagem.salvar(dados, LOTE, "IMG-20261105-WA0001.jpg", [{"x": 10, "y": 20, "lado": 120, "classe": "alface"}])
    especies = dados / "especies"
    assert rotulagem.exportar(dados, especies)["recortes"] == 1
    recorte = next((especies / "alface").glob("*.jpg"))
    assert recorte.name.startswith("2026-11-05__2026-11-06__") and Image.open(recorte).size == (120, 120)
    rotulagem.salvar(dados, LOTE, "IMG-20261105-WA0001.jpg", [{"x": 10, "y": 20, "lado": 120, "classe": "cebolinha"}])
    rotulagem.exportar(dados, especies)
    assert not list((especies / "alface").glob("*.jpg"))
    assert len(list((especies / "cebolinha").glob("*.jpg"))) == 1


def test_recortes_da_camera_do_no_nao_sao_apagados(dados):
    pasta = dados / "especies" / "alface"
    pasta.mkdir(parents=True)
    do_no = pasta / "2026-11-20__no__143000_vaso0.jpg"
    Image.new("RGB", (50, 50)).save(do_no)
    rotulagem.exportar(dados, dados / "especies")
    assert do_no.exists()


def test_rotulagem_pela_api(dados):
    aplicacao = painel.criar_app(db_path=":memory:", conectar_mqtt=False, dados=dados)
    with TestClient(aplicacao) as c:
        assert c.get("/api/rotulagem/lotes").json()[0]["fotos"] == 2
        r = c.get(f"/api/rotulagem/lotes/{LOTE}/fotos/foto.jpg")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
        regiao = {"x": 0, "y": 0, "lado": 200, "classe": "rucula"}
        assert c.put(f"/api/rotulagem/lotes/{LOTE}/fotos/foto.jpg", json={"regioes": [regiao]}).status_code == 200
        assert c.put(f"/api/rotulagem/lotes/{LOTE}/fotos/foto.jpg",
                     json={"regioes": [{**regiao, "classe": "feijao"}]}).status_code == 400
        assert c.post("/api/rotulagem/exportar").json()["recortes"] == 1
