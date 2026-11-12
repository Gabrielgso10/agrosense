"""Encerra somente o painel e a ponte iniciados pelo atalho silencioso.
Nao para o servico Mosquitto e nao fecha o navegador.
"""
from pathlib import Path
import json
import os
import subprocess
import ctypes

ROOT = Path(__file__).resolve().parent
LOG_DIR = Path(os.environ.get("LOCALAPPDATA") or ROOT) / "AgroSense" / "logs"
FILE = LOG_DIR / "processos.json"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def main():
    if not FILE.exists():
        return
    dados = json.loads(FILE.read_text(encoding="utf-8"))
    for nome in ("ponte", "painel"):
        try:
            pid = int(dados.get(nome))
        except (ValueError, TypeError):
            continue
        if pid <= 0:
            continue
        subprocess.run(["taskkill.exe", "/PID", str(pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=NO_WINDOW)
    FILE.unlink(missing_ok=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, str(e), "AgroSense - encerramento", 0x10)
