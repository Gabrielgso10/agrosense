import json
import sqlite3

import store


def banco():
    conn = sqlite3.connect(":memory:")
    store.criar_tabelas(conn)
    return conn


def vaso(n, solo, bomba, especie="alface", motivo="ocioso", fixa=False, conf=0.9, liga=55, desliga=70):
    return json.dumps({"vaso": n, "especie": especie, "fixa": fixa, "confianca": conf, "solo_pct": solo,
                       "liga_abaixo": liga, "desliga_em": desliga, "bomba": bomba, "motivo": motivo}).encode()


def test_leitura_de_vaso_aparece_no_estado():
    c = banco()
    assert store.ingerir(c, "agrosense/vaso/0", vaso(0, 60, False), 1000.0) == "vaso"
    v = store.estado(c, 1010.0)["vasos"][0]
    assert v["vaso"] == 0 and v["solo_pct"] == 60 and v["especie"] == "alface" and v["liga_abaixo"] == 55


def test_mudanca_da_bomba_vira_evento_de_rega():
    c = banco()
    for ts, ligada in [(1000, False), (1100, True), (1160, True), (1200, False)]:
        store.ingerir(c, "agrosense/vaso/1", vaso(1, 50, ligada), float(ts))
    assert [(e["ts"], e["bomba"]) for e in store.eventos(c)] == [(1200.0, False), (1100.0, True)]
    assert store.estado(c, 1300.0)["vasos"][0]["ultima_rega"] == 1100.0


def test_historico_respeita_a_janela():
    c = banco()
    store.ingerir(c, "agrosense/vaso/0", vaso(0, 70, False), 0.0)
    store.ingerir(c, "agrosense/vaso/0", vaso(0, 65, False), 30 * 3600.0)
    h = store.historico(c, desde=31 * 3600.0 - 24 * 3600.0)
    assert [ponto[1] for ponto in h["vasos"]["0"]] == [65]


def test_status_do_no_e_ambiente():
    c = banco()
    store.ingerir(c, "agrosense/no/status", b"dormindo", 500.0)
    amb = {"temperatura_c": 24.5, "umidade_ar_pct": 61.0, "lux": 820, "reservatorio_ok": True, "sensores_ok": True}
    store.ingerir(c, "agrosense/ambiente", json.dumps(amb).encode(), 510.0)
    e = store.estado(c, 600.0)
    assert e["no"]["status"] == "dormindo" and e["no"]["visto_ha_s"] == 90.0
    assert e["ambiente"]["temperatura_c"] == 24.5 and e["ambiente"]["reservatorio_ok"] is True


def test_foto_e_legenda():
    c = banco()
    jpeg = b"\xff\xd8 foto \xff\xd9"
    store.ingerir(c, "agrosense/camera", jpeg, 700.0)
    info = {"largura": 320, "altura": 240,
            "vasos": [{"vaso": 0, "x": 0, "y": 60, "lado": 106, "visto": "alface", "confianca": 0.91}]}
    store.ingerir(c, "agrosense/camera/info", json.dumps(info).encode(), 701.0)
    assert store.foto(c) == (jpeg, 700.0)
    f = store.estado(c, 710.0)["foto"]
    assert f["ts"] == 700.0 and f["vasos"][0]["visto"] == "alface"


def test_mensagem_retida_reenviada_nao_duplica_o_historico():
    c = banco()
    store.ingerir(c, "agrosense/vaso/0", vaso(0, 60, True), 100.0)
    store.ingerir(c, "agrosense/vaso/0", vaso(0, 60, True), 200.0, retida=True)  # broker reenviou na reconexão
    assert len(store.historico(c, desde=0)["vasos"]["0"]) == 1


def test_mensagem_malformada_ou_desconhecida_e_ignorada():
    c = banco()
    assert store.ingerir(c, "agrosense/vaso/0", b"{nao e json", 1.0) is None
    assert store.ingerir(c, "agrosense/outra/coisa", b"x", 1.0) is None
    assert store.estado(c, 2.0)["vasos"] == []


def test_amostras_do_dataset_usam_a_especie_do_momento_da_foto():
    c = banco()
    store.ingerir(c, "agrosense/camera", b"jpg", 1000.0)
    info = {"largura": 320, "altura": 240,
            "vasos": [{"vaso": 0, "x": 0, "y": 60, "lado": 106, "visto": "", "confianca": 0.2}]}
    store.ingerir(c, "agrosense/camera/info", json.dumps(info).encode(), 1001.0)
    store.ingerir(c, "agrosense/vaso/0", vaso(0, 60, False, especie="rucula", fixa=True), 1002.0)
    a = store.amostras_dataset(c)
    assert len(a) == 1 and a[0]["rois"] == [(0, 0, 60, 106)]
    assert a[0]["especies"] == {0: {"especie": "rucula", "fixa": True}}
