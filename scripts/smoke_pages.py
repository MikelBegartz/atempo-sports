"""Smoke test: arrenca l'app amb una CÒPIA de la BD i comprova que les
pàgines principals no peten. Executar ABANS de cada desplegament.

Ús:  python scripts/smoke_pages.py
Surt amb codi 1 si alguna pàgina retorna 500.
"""

from __future__ import annotations

import http.cookiejar
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DB = ROOT / "data" / "atempo.db"

# Credencials del club demo local (entorn de desenvolupament)
CLUB_CODE = os.environ.get("ATEMPO_SMOKE_CLUB", "mataro")
CLUB_SECRET = os.environ.get("ATEMPO_SMOKE_SECRET", "mataro")
PORT = 8931

PAGES = [
    "/",
    "/login",
    "/guia",
    "/privacitat",
    "/app",
    "/season/{sid}/teams",
    "/season/{sid}/people",
    "/season/{sid}/venues",
    "/season/{sid}/matches",
    "/season/{sid}/calendar",
    "/season/{sid}/trainings",
    "/season/{sid}/data",
    "/season/{sid}/import",
    "/season/{sid}/fed",
    "/season/{sid}/federation-changes",
    "/season/{sid}/conflicts",
    "/season/{sid}/overlaps",
    "/season/{sid}/club",
]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _req(opener, url, data=None):
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    try:
        return opener.open(req, timeout=20).status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


def main() -> int:
    if not SRC_DB.exists():
        print(f"ERROR: no hi ha {SRC_DB}")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="atempo_smoke_"))
    shutil.copy(SRC_DB, tmp / "atempo.db")
    # fitxers de sessió/permisos que l'app espera al data dir
    for extra in SRC_DB.parent.glob(".*"):
        if extra.is_file():
            shutil.copy(extra, tmp / extra.name)

    port = _free_port()
    env = dict(os.environ, ATEMPO_DATA_DIR=str(tmp))
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', "
         f"port={port})"],
        cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPRedirectHandler(),
    )
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/login", timeout=2)
                break
            except Exception:
                if proc.poll() is not None:
                    print("ERROR: el servidor no ha arrancat")
                    return 1
                time.sleep(0.5)

        # login
        _req(opener, base + "/login",
             data=f"club_code={CLUB_CODE}&club_secret={CLUB_SECRET}".encode())

        # temporada activa: la primera del club demo (la BD en té)
        import sqlite3
        con = sqlite3.connect(tmp / "atempo.db")
        sid = con.execute(
            "SELECT id FROM seasons ORDER BY id LIMIT 1"
        ).fetchone()[0]
        con.close()

        fails = []
        for p in PAGES:
            url = base + p.format(sid=sid)
            code = _req(opener, url)
            mark = "OK" if code in (200, 303) else "FAIL"
            print(f"{mark}  {code}  {p.format(sid=sid)}")
            if code == 500 or code == -1:
                fails.append((p.format(sid=sid), code))
        if fails:
            print("\nPÀGINES TRENCADES:")
            for p, c in fails:
                print(f"  {c}  {p}")
            return 1
        print("\nTOTES LES PÀGINES OK")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
