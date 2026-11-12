"""Inicializa AgroSense sem consoles visiveis, com logs para diagnostico.

Mantem os arquivos da IA, firmware e simulacao intactos.
Atualiza so a frequencia de leitura do frontend de 15 s para 5 s.
"""
from __future__ import annotations

import ctypes
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
PAINEL = ROOT / "painel"
PONTE = ROOT / "simulacao" / "wokwi_3_bombas" / "bridge_wokwi_3bombas.py"
URL_FILE = ROOT / "URL_WOKWI_3_BOMBAS.txt"
LOG_DIR = Path(os.environ.get("LOCALAPPDATA") or ROOT) / "AgroSense" / "logs"
STATE_FILE = LOG_DIR / "processos.json"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def preparar_logs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def aviso(texto: str) -> None:
    preparar_logs()
    with (LOG_DIR / "inicializador.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " | " + texto + "\n")


def alerta(texto: str) -> None:
    aviso("ERRO: " + texto)
    ctypes.windll.user32.MessageBoxW(0, texto + "\n\nLogs: " + str(LOG_DIR), "AgroSense", 0x10)


def porta_aberta(porta: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=0.8):
            return True
    except OSError:
        return False


def painel_respondendo() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/estado", timeout=1.4) as r:
            return r.status == 200
    except Exception:
        return False


def processo_ativo(pid) -> bool:
    """Checa se o PID existe sem precisar de pacotes externos."""
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return False
    if pid <= 0:
        return False
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def ler_estado() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salvar_estado(estado: dict) -> None:
    STATE_FILE.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def iniciar_oculto(comando: list[str], cwd: Path, log: str, env: dict | None = None) -> subprocess.Popen:
    saida = (LOG_DIR / log).open("a", encoding="utf-8")
    try:
        processo = subprocess.Popen(
            comando, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
            stdout=saida, stderr=subprocess.STDOUT, creationflags=NO_WINDOW,
        )
        aviso(f"Processo oculto iniciado: {log} (PID {processo.pid})")
        return processo
    finally:
        saida.close()  # o processo filho permanece com o descritor aberto


def procurar_mosquitto(arquivo: str) -> Path | None:
    achado = shutil.which(arquivo)
    if achado:
        return Path(achado)
    for raiz in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        p = Path(raiz) / "mosquitto" / arquivo
        if p.is_file():
            return p
    return None


def iniciar_broker() -> bool:
    if porta_aberta(1883):
        aviso("Mosquitto ja esta ativo em localhost:1883")
        return True
    aviso("Tentando iniciar servico Mosquitto...")
    try:
        result = subprocess.run(["sc.exe", "start", "mosquitto"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=NO_WINDOW, timeout=9)
        aviso(f"sc start mosquitto: codigo {result.returncode}")
    except (OSError, subprocess.TimeoutExpired) as e:
        aviso(f"Servico nao iniciou: {e}")
    for _ in range(12):
        if porta_aberta(1883):
            return True
        time.sleep(0.5)
    exe = procurar_mosquitto("mosquitto.exe")
    if exe:
        proc = iniciar_oculto([str(exe), "-v"], exe.parent, "mosquitto.log")
        for _ in range(10):
            if porta_aberta(1883):
                return True
            if proc.poll() is not None:
                break
            time.sleep(0.5)
    return False


def ajustar_autoatualizacao() -> None:
    """Altera a frequencia no JS existente, sem sobrescrever o codigo do grupo."""
    arquivo = PAINEL / "static" / "painel.js"
    texto = arquivo.read_text(encoding="utf-8")
    novo, n = re.subn(r"setInterval\(\s*atualizar\s*,\s*\d+\s*\)\s*;",
                       "setInterval(atualizar, 5000);", texto)
    if n != 1:
        raise RuntimeError("Nao encontrei uma unica configuracao 'setInterval(atualizar, ...)' em painel.js")
    if novo != texto:
        arquivo.write_text(novo, encoding="utf-8")
        aviso("painel.js atualizado: leituras a cada 5 segundos")
    else:
        aviso("painel.js ja esta configurado para 5 segundos")
    # Evita que o navegador reutilize a copia antiga do JavaScript.
    pagina = PAINEL / "static" / "index.html"
    html = pagina.read_text(encoding="utf-8")
    atualizado, _ = re.subn(r'src="painel\.js(?:\?[^"]*)?"', 'src="painel.js?v=5s"', html)
    if atualizado != html:
        pagina.write_text(atualizado, encoding="utf-8")
        aviso("index.html atualizado: cache do script renovado")


def link_wokwi() -> str | None:
    if not URL_FILE.exists():
        aviso("URL_WOKWI_3_BOMBAS.txt ausente. Mantenha o arquivo com seu link salvo.")
        return None
    for linha in URL_FILE.read_text(encoding="utf-8-sig").splitlines():
        url = linha.strip()
        if re.fullmatch(r"https://wokwi\.com/projects/\d+(?:[/?#][^\s]*)?", url):
            return url
    aviso("O arquivo URL_WOKWI_3_BOMBAS.txt nao tem uma URL valida.")
    return None


def dependencias_ok() -> bool:
    ausentes = []
    for modulo in ("fastapi", "uvicorn", "paho.mqtt", "PIL"):
        try:
            importlib.import_module(modulo)
        except ImportError:
            ausentes.append(modulo)
    if ausentes:
        alerta("Faltam bibliotecas Python: " + ", ".join(ausentes) +
               "\nInstale com: py -m pip install -r painel\\requirements.txt")
        return False
    return True


def main() -> int:
    if os.name != "nt":
        print("Este inicializador foi desenvolvido para Windows.")
        return 1
    preparar_logs()
    aviso("==== Iniciando AgroSense (modo silencioso) ====")
    for arquivo in (PAINEL / "app.py", PAINEL / "static" / "painel.js", PONTE):
        if not arquivo.is_file():
            alerta(f"Arquivo nao encontrado: {arquivo}\nConfira a pasta simulacao/wokwi_3_bombas.")
            return 1
    if not dependencias_ok():
        return 1
    try:
        ajustar_autoatualizacao()
    except Exception as e:
        alerta(f"Nao consegui configurar o painel para 5 segundos: {e}")
        return 1
    if not iniciar_broker():
        alerta("Mosquitto nao esta ativo na porta 1883. Verifique o servico do Windows.")
        return 1
    estado = ler_estado()
    if painel_respondendo():
        aviso("Painel ja responde na porta 8000; nao iniciei outro.")
    else:
        if porta_aberta(8000):
            alerta("A porta 8000 esta ocupada por outro programa.")
            return 1
        env = dict(os.environ)
        env["AGROSENSE_DB"] = str(PAINEL / "agrosense_wokwi_3bombas.db")
        env["AGROSENSE_MQTT_HOST"] = "127.0.0.1"
        painel = iniciar_oculto([sys.executable, "-u", "app.py"], PAINEL, "painel.log", env=env)
        estado["painel"] = painel.pid
        salvar_estado(estado)
        for _ in range(30):
            if painel_respondendo():
                break
            if painel.poll() is not None:
                alerta("Painel terminou ao iniciar. Veja painel.log para identificar o erro.")
                return 1
            time.sleep(0.5)
        else:
            alerta("Painel nao respondeu na porta 8000. Veja painel.log.")
            return 1
    if processo_ativo(estado.get("ponte")):
        aviso(f"Ponte ja estava ativa (PID {estado.get('ponte')}); sem duplicar.")
    else:
        ponte = iniciar_oculto([sys.executable, "-u", str(PONTE)], PONTE.parent, "ponte.log",
                               env={**os.environ, "AGROSENSE_MQTT_HOST": "127.0.0.1"})
        estado["ponte"] = ponte.pid
        salvar_estado(estado)
        time.sleep(1)
        if ponte.poll() is not None:
            alerta("Ponte MQTT terminou ao iniciar. Veja ponte.log.")
            return 1
    webbrowser.open("http://localhost:8000", new=2)
    aviso("Painel aberto em localhost:8000")
    link = link_wokwi()
    if link:
        webbrowser.open(link, new=2)
        aviso("Wokwi aberto com a URL informada no arquivo de configuracao")
    else:
        webbrowser.open("https://wokwi.com", new=2)
        aviso("Wokwi aberto, mas sem URL da copia salva com tres bombas")
    aviso("Tudo iniciado. No Wokwi, clique em Start Simulation.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as erro:
        if os.name == "nt":
            traceback.print_exc(file=(LOG_DIR / "inicializador_erros.log").open("a", encoding="utf-8"))
            alerta("Erro inesperado: " + str(erro))
        raise
