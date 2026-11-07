import json

from fastapi.testclient import TestClient

import app as painel


def montar():
    aplicacao = painel.criar_app(db_path=":memory:", conectar_mqtt=False)
    return aplicacao, TestClient(aplicacao)


def test_pagina_e_estado_vazio():
    aplicacao, c = montar()
    with c:
        r = c.get("/")
        assert r.status_code == 200 and "AgroSense" in r.text
        assert c.get("/api/estado").json()["vasos"] == []


def test_sem_foto_responde_404_explicando_o_motivo():
    aplicacao, c = montar()
    with c:
        r = c.get("/api/foto")
        assert r.status_code == 404 and "câmera" in r.json()["erro"]


def test_mensagens_recebidas_aparecem_na_api():
    aplicacao, c = montar()
    with c:
        leitura = {"vaso": 0, "especie": "alface", "fixa": True, "confianca": 0.4, "solo_pct": 52,
                   "liga_abaixo": 55, "desliga_em": 70, "bomba": True, "motivo": "ligou_solo_seco"}
        aplicacao.state.ingerir("agrosense/vaso/0", json.dumps(leitura).encode(), False)
        assert c.get("/api/estado").json()["vasos"][0]["solo_pct"] == 52
        assert len(c.get("/api/historico?horas=1").json()["vasos"]["0"]) == 1
        assert c.get("/api/eventos").json()[0]["bomba"] is True
        aplicacao.state.ingerir("agrosense/camera", b"\xff\xd8x\xff\xd9", False)
        r = c.get("/api/foto")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
