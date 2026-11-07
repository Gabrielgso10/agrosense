"""Armazena a telemetria do nó AgroSense em SQLite e responde às consultas do painel."""
import json
import re
import sqlite3

TOPICO_VASO = re.compile(r"^agrosense/vaso/(\d+)$")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS leituras (
  ts REAL, vaso INTEGER, especie TEXT, fixa INTEGER, confianca REAL, solo INTEGER,
  liga INTEGER, desliga INTEGER, bomba INTEGER, motivo TEXT, mudou INTEGER);
CREATE INDEX IF NOT EXISTS idx_leituras ON leituras (vaso, ts);
CREATE TABLE IF NOT EXISTS ambiente (
  ts REAL, temperatura REAL, umidade REAL, lux REAL, reservatorio_ok INTEGER, sensores_ok INTEGER);
CREATE TABLE IF NOT EXISTS status (ts REAL, valor TEXT);
CREATE TABLE IF NOT EXISTS fotos (ts REAL PRIMARY KEY, jpeg BLOB, info TEXT);
"""


def criar_tabelas(conn: sqlite3.Connection) -> None:
    conn.executescript(ESQUEMA)
    conn.commit()


def _json(payload: bytes):
    try:
        dado = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return dado if isinstance(dado, dict) else None


def _inteiro(valor):
    """O firmware manda -1 quando não há valor (leitura inválida, espécie sem perfil)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0:
        return None
    return int(valor)


def _numero(valor):
    return float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def _existe(conn, sql, params=()):
    return conn.execute(sql, params).fetchone() is not None


def ingerir(conn: sqlite3.Connection, topico: str, payload: bytes, ts: float, retida: bool = False):
    """Grava uma mensagem MQTT. Mensagens retidas que o broker reenvia a cada reconexão só
    entram se o banco ainda não tiver aquele dado. Retorna o tipo gravado, ou None."""
    m = TOPICO_VASO.match(topico)
    if m:
        n, d = int(m.group(1)), _json(payload)
        if d is None or (retida and _existe(conn, "SELECT 1 FROM leituras WHERE vaso = ?", (n,))):
            return None
        anterior = conn.execute("SELECT bomba FROM leituras WHERE vaso = ? ORDER BY ts DESC LIMIT 1", (n,)).fetchone()
        bomba = bool(d.get("bomba"))
        mudou = bomba if anterior is None else bool(anterior[0]) != bomba
        conn.execute("INSERT INTO leituras VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (ts, n, d.get("especie") or "", int(bool(d.get("fixa"))), _numero(d.get("confianca")),
                      _inteiro(d.get("solo_pct")), _inteiro(d.get("liga_abaixo")), _inteiro(d.get("desliga_em")),
                      int(bomba), d.get("motivo") or "", int(mudou)))
        conn.commit()
        return "vaso"
    if topico == "agrosense/ambiente":
        d = _json(payload)
        if d is None or (retida and _existe(conn, "SELECT 1 FROM ambiente")):
            return None
        conn.execute("INSERT INTO ambiente VALUES (?,?,?,?,?,?)",
                     (ts, _numero(d.get("temperatura_c")), _numero(d.get("umidade_ar_pct")), _numero(d.get("lux")),
                      int(bool(d.get("reservatorio_ok"))), int(bool(d.get("sensores_ok")))))
        conn.commit()
        return "ambiente"
    if topico == "agrosense/no/status":
        if retida and _existe(conn, "SELECT 1 FROM status"):
            return None
        conn.execute("INSERT INTO status VALUES (?, ?)", (ts, payload.decode("utf-8", "replace").strip()))
        conn.commit()
        return "status"
    if topico == "agrosense/camera":
        if not payload or (retida and _existe(conn, "SELECT 1 FROM fotos")):
            return None
        conn.execute("INSERT OR REPLACE INTO fotos (ts, jpeg, info) VALUES (?, ?, NULL)", (ts, payload))
        conn.commit()
        return "foto"
    if topico == "agrosense/camera/info":
        d = _json(payload)
        ultima = conn.execute("SELECT ts, info FROM fotos ORDER BY ts DESC LIMIT 1").fetchone()
        if d is None or ultima is None or (retida and ultima[1]):
            return None
        conn.execute("UPDATE fotos SET info = ? WHERE ts = ?", (json.dumps(d), ultima[0]))
        conn.commit()
        return "foto_info"
    return None


def estado(conn: sqlite3.Connection, agora: float) -> dict:
    vasos = []
    for (n,) in conn.execute("SELECT DISTINCT vaso FROM leituras ORDER BY vaso").fetchall():
        r = conn.execute("SELECT ts, especie, fixa, confianca, solo, liga, desliga, bomba, motivo FROM leituras "
                         "WHERE vaso = ? ORDER BY ts DESC LIMIT 1", (n,)).fetchone()
        rega = conn.execute("SELECT MAX(ts) FROM leituras WHERE vaso = ? AND mudou = 1 AND bomba = 1", (n,)).fetchone()[0]
        vasos.append({"vaso": n, "ts": r[0], "especie": r[1], "fixa": bool(r[2]), "confianca": r[3], "solo_pct": r[4],
                      "liga_abaixo": r[5], "desliga_em": r[6], "bomba": bool(r[7]), "motivo": r[8], "ultima_rega": rega})
    amb = conn.execute("SELECT ts, temperatura, umidade, lux, reservatorio_ok, sensores_ok FROM ambiente "
                       "ORDER BY ts DESC LIMIT 1").fetchone()
    st = conn.execute("SELECT ts, valor FROM status ORDER BY ts DESC LIMIT 1").fetchone()
    foto = conn.execute("SELECT ts, info FROM fotos ORDER BY ts DESC LIMIT 1").fetchone()
    momentos = [v["ts"] for v in vasos] + [x[0] for x in (amb, st, foto) if x is not None]
    ultima = max(momentos) if momentos else None
    return {
        "no": {"status": st[1] if st else None, "status_ts": st[0] if st else None, "ultima_mensagem": ultima,
               "visto_ha_s": (agora - ultima) if ultima is not None else None},
        "vasos": vasos,
        "ambiente": None if amb is None else {
            "ts": amb[0], "temperatura_c": amb[1], "umidade_ar_pct": amb[2], "lux": amb[3],
            "reservatorio_ok": bool(amb[4]), "sensores_ok": bool(amb[5])},
        "foto": None if foto is None else {"ts": foto[0], **(json.loads(foto[1]) if foto[1] else {"vasos": []})},
    }


def historico(conn: sqlite3.Connection, desde: float) -> dict:
    series = {}
    for ts, n, solo, bomba, liga, desliga in conn.execute(
            "SELECT ts, vaso, solo, bomba, liga, desliga FROM leituras WHERE ts >= ? ORDER BY ts", (desde,)):
        series.setdefault(str(n), []).append([ts, solo, bool(bomba), liga, desliga])
    return {"vasos": series}


def eventos(conn: sqlite3.Connection, limite: int = 20) -> list:
    linhas = conn.execute("SELECT ts, vaso, especie, bomba, motivo FROM leituras WHERE mudou = 1 "
                          "ORDER BY ts DESC LIMIT ?", (limite,)).fetchall()
    return [{"ts": t, "vaso": n, "especie": e, "bomba": bool(b), "motivo": m} for t, n, e, b, m in linhas]


def foto(conn: sqlite3.Connection):
    r = conn.execute("SELECT jpeg, ts FROM fotos ORDER BY ts DESC LIMIT 1").fetchone()
    return (bytes(r[0]), r[1]) if r else None


def amostras_dataset(conn: sqlite3.Connection, janela_s: float = 600.0) -> list:
    """Cada foto com a região de cada vaso e a espécie registrada para ele naquele momento."""
    amostras = []
    for ts, jpeg, info in conn.execute("SELECT ts, jpeg, info FROM fotos WHERE info IS NOT NULL ORDER BY ts").fetchall():
        rois, especies = [], {}
        for v in json.loads(info).get("vasos", []):
            n = int(v["vaso"])
            rois.append((n, int(v["x"]), int(v["y"]), int(v["lado"])))
            r = conn.execute("SELECT especie, fixa FROM leituras WHERE vaso = ? AND ts BETWEEN ? AND ? "
                             "ORDER BY ABS(ts - ?) LIMIT 1", (n, ts - janela_s, ts + janela_s, ts)).fetchone()
            if r and r[0]:
                especies[n] = {"especie": r[0], "fixa": bool(r[1])}
        amostras.append({"ts": ts, "jpeg": bytes(jpeg), "rois": rois, "especies": especies})
    return amostras
