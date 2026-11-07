"""Painel do AgroSense: assina a telemetria MQTT do nó, guarda em SQLite e mostra no navegador.

  python app.py                                   # broker em localhost:1883, painel em http://localhost:8000
  set AGROSENSE_MQTT_HOST=192.168.0.10            # (Windows) broker em outra máquina
"""
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import store

AQUI = Path(__file__).resolve().parent


def criar_app(db_path: str | None = None, conectar_mqtt: bool = True) -> FastAPI:
    db_path = db_path or os.environ.get("AGROSENSE_DB", str(AQUI / "agrosense.db"))
    host = os.environ.get("AGROSENSE_MQTT_HOST", "localhost")
    porta = int(os.environ.get("AGROSENSE_MQTT_PORT", "1883"))
    conn = sqlite3.connect(db_path, check_same_thread=False)
    store.criar_tabelas(conn)
    trava = threading.Lock()

    def ingerir(topico: str, payload: bytes, retida: bool):
        with trava:
            return store.ingerir(conn, topico, payload, time.time(), retida=retida)

    @asynccontextmanager
    async def ciclo_de_vida(_app):
        cliente = None
        if conectar_mqtt:
            import paho.mqtt.client as mqtt

            cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="agrosense-painel")
            cliente.on_connect = lambda c, _u, _f, _rc, _p: c.subscribe("agrosense/#", qos=1)
            cliente.on_message = lambda _c, _u, msg: ingerir(msg.topic, msg.payload, bool(msg.retain))
            cliente.connect_async(host, porta)  # tenta de novo sozinho se o broker cair
            cliente.loop_start()
        yield
        if cliente is not None:
            cliente.loop_stop()
            cliente.disconnect()
        conn.close()

    app = FastAPI(title="AgroSense", lifespan=ciclo_de_vida)
    app.state.ingerir = ingerir

    @app.get("/api/estado")
    def api_estado():
        with trava:
            return store.estado(conn, time.time())

    @app.get("/api/historico")
    def api_historico(horas: float = 24):
        with trava:
            return store.historico(conn, time.time() - horas * 3600)

    @app.get("/api/eventos")
    def api_eventos(limite: int = 20):
        with trava:
            return store.eventos(conn, limite)

    @app.get("/api/foto")
    def api_foto():
        with trava:
            f = store.foto(conn)
        if f is None:
            return JSONResponse({"erro": "Ainda não chegou nenhuma foto: ela vem depois da primeira classificação "
                                         "da câmera."}, status_code=404)
        return Response(f[0], media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    app.mount("/", StaticFiles(directory=AQUI / "static", html=True), name="static")
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:criar_app", factory=True, host="0.0.0.0", port=int(os.environ.get("AGROSENSE_PORTA", "8000")))
