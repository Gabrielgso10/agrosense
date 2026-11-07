"""Simula o nó AgroSense para ver o painel funcionando antes do protótipo.

  python simular.py --direto      # grava 2 dias de histórico no banco do painel e sai
  python simular.py               # publica no broker (localhost:1883), um ciclo a cada 3 s
"""
import argparse
import io
import json
import math
import sqlite3
import time
from pathlib import Path

from PIL import Image, ImageDraw

import store

AQUI = Path(__file__).resolve().parent
ESPECIES = [("alface", 0.30), ("cebolinha", 0.30), ("rucula", 0.30)]  # p da FAO 56 (rúcula: premissa)
CONFIANCA = (0.93, 0.88, 0.95)
CAPACIDADE, MURCHA = 70, 20
ROIS = [(0, 60, 106), (107, 60, 106), (214, 60, 106)]
CICLO_S = 600


def limiares(p):
    return round(CAPACIDADE - p * (CAPACIDADE - MURCHA)), CAPACIDADE


def foto_simulada() -> bytes:
    img = Image.new("RGB", (320, 240), (214, 222, 210))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 170, 320, 240], fill=(160, 140, 112))  # bancada
    verde, contorno = (70, 140, 60), (48, 110, 44)
    for i, (x, _y, lado) in enumerate(ROIS):
        cx = x + lado // 2
        d.polygon([(cx - 34, 120), (cx + 34, 120), (cx + 26, 168), (cx - 26, 168)], fill=(150, 92, 62))
        d.ellipse([cx - 34, 114, cx + 34, 126], fill=(92, 70, 52))
        if i == 0:  # alface: roseta de folhas largas
            for dx, dy in [(-18, -6), (18, -6), (0, -14), (-10, -2), (10, -2)]:
                d.ellipse([cx + dx - 16, 96 + dy, cx + dx + 16, 122 + dy], fill=verde, outline=contorno)
        elif i == 1:  # cebolinha: folhas tubulares
            for dx in range(-14, 15, 5):
                d.line([(cx + dx, 118), (cx + dx + dx // 4, 72)], fill=verde, width=3)
        else:  # rúcula: folhas alongadas e recortadas, em roseta
            for graus in (-55, -28, 0, 28, 55):
                a = math.radians(graus)
                ponta = (cx + 42 * math.sin(a), 118 - 42 * math.cos(a))
                d.line([(cx, 118), ponta], fill=contorno, width=2)
                for t, r in ((0.5, 5), (0.75, 6), (1.0, 8)):  # lobos da folha
                    px, py = cx + (ponta[0] - cx) * t, 118 + (ponta[1] - 118) * t
                    d.ellipse([px - r, py - r * 0.8, px + r, py + r * 0.8], fill=verde)
    d.text((6, 6), "imagem simulada", fill=(80, 90, 80))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


class Bancada:
    def __init__(self):
        self.solo = [64.0, 60.0, 57.0]
        self.secagem = [1.1, 0.8, 0.6]  # pontos por hora; a alface perde água mais rápido
        self.ciclos = 0

    def _leitura(self, i, liga, desliga, bomba, motivo):
        return json.dumps({"vaso": i, "especie": ESPECIES[i][0], "fixa": True, "confianca": CONFIANCA[i],
                           "solo_pct": round(self.solo[i]), "liga_abaixo": liga, "desliga_em": desliga,
                           "bomba": bomba, "motivo": motivo}).encode()

    def ciclo(self, ts):
        """Mensagens de um ciclo de 10 min do nó, como (instante, tópico, conteúdo)."""
        msgs = [(ts, "agrosense/no/status", b"online")]
        local = time.localtime(ts)
        sol = max(0.0, math.sin((local.tm_hour + local.tm_min / 60 - 6) / 12 * math.pi))
        if self.ciclos % 6 == 0:  # câmera a cada hora
            msgs.append((ts, "agrosense/camera", foto_simulada()))
            vasos = [{"vaso": i, "x": x, "y": y, "lado": lado, "visto": ESPECIES[i][0], "confianca": CONFIANCA[i]}
                     for i, (x, y, lado) in enumerate(ROIS)]
            msgs.append((ts + 1, "agrosense/camera/info",
                         json.dumps({"largura": 320, "altura": 240, "vasos": vasos}).encode()))
        for i, (_especie, p) in enumerate(ESPECIES):
            liga, desliga = limiares(p)
            self.solo[i] -= self.secagem[i] * (0.4 + sol) * CICLO_S / 3600
            if self.solo[i] < liga:  # rega: liga, sobe até o limiar de parada, desliga
                msgs.append((ts + 2, f"agrosense/vaso/{i}", self._leitura(i, liga, desliga, True, "ligou_solo_seco")))
                self.solo[i] = desliga + 0.5
                msgs.append((ts + 50, f"agrosense/vaso/{i}", self._leitura(i, liga, desliga, False, "parou_solo_umido")))
            else:
                msgs.append((ts + 2, f"agrosense/vaso/{i}", self._leitura(i, liga, desliga, False, "ocioso")))
        ambiente = {"temperatura_c": round(21 + 7 * sol, 1), "umidade_ar_pct": round(72 - 18 * sol, 1),
                    "lux": round(40 + 900 * sol), "reservatorio_ok": True, "sensores_ok": True}
        msgs.append((ts + 3, "agrosense/ambiente", json.dumps(ambiente).encode()))
        msgs.append((ts + 60, "agrosense/no/status", b"dormindo"))
        self.ciclos += 1
        return msgs


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--direto", action="store_true", help="grava no banco do painel, sem broker")
    p.add_argument("--horas", type=float, default=48, help="histórico gerado com --direto")
    p.add_argument("--db", default=str(AQUI / "agrosense.db"))
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--intervalo", type=float, default=3.0, help="segundos entre ciclos no modo broker")
    args = p.parse_args()
    bancada = Bancada()

    if args.direto:
        conn = sqlite3.connect(args.db)
        store.criar_tabelas(conn)
        agora, ts, total = time.time(), time.time() - args.horas * 3600, 0
        while ts <= agora:
            for instante, topico, conteudo in bancada.ciclo(ts):
                if instante <= agora:
                    total += store.ingerir(conn, topico, conteudo, instante) is not None
            ts += CICLO_S
        conn.close()
        print(f"{total} mensagens gravadas em {args.db}. Agora rode: python app.py")
        return

    import paho.mqtt.client as mqtt

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="agrosense-simulador")
    cliente.connect(args.host, args.port)
    cliente.loop_start()
    print(f"Publicando em {args.host}:{args.port}, um ciclo a cada {args.intervalo} s. Ctrl+C para parar.")
    try:
        while True:
            for _instante, topico, conteudo in sorted(bancada.ciclo(time.time()), key=lambda m: m[0]):
                retida = topico in ("agrosense/camera", "agrosense/camera/info", "agrosense/no/status")
                cliente.publish(topico, conteudo, qos=1 if retida else 0, retain=retida)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        pass
    finally:
        cliente.loop_stop()
        cliente.disconnect()


if __name__ == "__main__":
    main()
