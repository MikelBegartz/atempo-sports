"""Test real de /season/{sid}/data: arranca uvicorn amb CÒPIA de la BD
i prova els 3 camins d'importació (xlsx, CSV cp1252, text enganxat TSV).
"""
from __future__ import annotations

import io
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SRC_DB = ROOT / "data" / "atempo.db"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="atempo_imp_"))
    shutil.copy(SRC_DB, tmp / "atempo.db")
    for extra in SRC_DB.parent.glob(".*"):
        if extra.is_file():
            shutil.copy(extra, tmp / extra.name)

    # temporada del club demo
    con = sqlite3.connect(tmp / "atempo.db")
    sid = con.execute("SELECT id FROM seasons ORDER BY id LIMIT 1").fetchone()[0]
    con.close()

    port = free_port()
    env = dict(os.environ, ATEMPO_DATA_DIR=str(tmp))
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', "
         f"port={port})"],
        cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    s = requests.Session()
    try:
        for _ in range(60):
            try:
                s.get(base + "/login", timeout=2)
                break
            except Exception:
                if proc.poll() is not None:
                    print("ERROR: el servidor no ha arrancat")
                    return 1
                time.sleep(0.5)

        s.post(base + "/login", data={"club_code": "mataro", "club_secret": "mataro"})

        def rep(html: str):
            nums = re.findall(r"\+\d+|omitits \d+", html)
            err = re.findall(r"No s'ha pogut[^<]*|format \.xls[^<]*", html)
            return nums, err[:1]

        ok = True

        # 1) XLSX real
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["equipo", "persona", "rol"])
        ws.append(["TEST_Sènior", "TEST Jordi García", "jugador"])
        ws.append(["TEST_Sènior", "TEST Anna Martí", "entrenadora"])
        buf = io.BytesIO()
        wb.save(buf)
        r = s.post(
            f"{base}/season/{sid}/data",
            data={"kind": "roster"},
            files={"file": ("plantilla.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        print("1) XLSX:", r.status_code, rep(r.text))
        ok &= r.status_code == 200 and "+2" in r.text

        # 2) CSV cp1252 amb accents
        csv_bytes = "equipo;persona;rol\nTEST_Benjamí;TEST Pere López;jugador\n".encode("cp1252")
        r2 = s.post(
            f"{base}/season/{sid}/data",
            data={"kind": "roster"},
            files={"file": ("lista.csv", csv_bytes, "text/csv")},
        )
        print("2) CSV cp1252:", r2.status_code, rep(r2.text))
        ok &= r2.status_code == 200 and "+1" in r2.text

        # 3) Enganxar text amb tabuladors (clipboard d'Excel)
        r3 = s.post(
            f"{base}/season/{sid}/data",
            data={"kind": "roster",
                  "paste": "equipo\tpersona\trol\nTEST_Juvenil\tTEST Marta Roig\tjugador\n"},
        )
        print("3) TSV enganxat:", r3.status_code, rep(r3.text))
        ok &= r3.status_code == 200 and "+1" in r3.text

        # 4) XLSX multi-full estil llistat de club: capçalera a fila 3 amb
        #    NOM I COGNOM / EQUIP / ENTRENADOR + full sense capçalera
        wb2 = Workbook()
        ws2 = wb2.active
        ws2.title = "INICIACIÓ"
        for _ in range(4):
            ws2.append([None] * 8)
        ws2.append([None, "TEST TESTÀ, LAIA", None, "42381417F", None,
                    "LTS000001", "TEST_INICIACIÓ ÚNIC", "COMPETICIÓ X"])
        ws3 = wb2.create_sheet("BENJAMÍ")
        ws3.append([None] * 8)
        ws3.append([None, "NOM I COGNOM", "DATA NAIEXEMENT", "ANY INICI OK",
                    "DNI", "EQUIP", "ENTRENADOR", "TECNIFICACIONS"])
        ws3.append([None] * 8)
        ws3.append([None, "TEST RIBAS, POL", "2016-01-01", "24/25",
                    "46171735V", "TEST_BENJAMÍ C", "TEST LORENZO", "6"])
        buf2 = io.BytesIO()
        wb2.save(buf2)
        r_fed = s.post(
            f"{base}/season/{sid}/data",
            data={"kind": "roster"},
            files={"file": ("dades_jugadors.xlsx", buf2.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        print("4) XLSX multi-full:", r_fed.status_code, rep(r_fed.text))
        ok &= r_fed.status_code == 200 and "+2" in r_fed.text

        # 5) Formulari "Persones" amb columna equipo -> vincula a l'equip
        r5 = s.post(
            f"{base}/season/{sid}/data",
            data={"kind": "people",
                  "paste": "nombre;equipo\nTEST Núria Soler;TEST_Sènior\n"},
        )
        print("5) Persones+equip:", r5.status_code, rep(r5.text))
        ok &= r5.status_code == 200 and "+1" in r5.text

        # 6) .xls antic -> error entenedor
        r4 = s.post(
            f"{base}/season/{sid}/data",
            data={"kind": "roster"},
            files={"file": ("vell.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 50,
                            "application/vnd.ms-excel")},
        )
        print("6) XLS antic:", r4.status_code, "| avís visible:", ".xls" in r4.text and ("xlsx" in r4.text or "CSV" in r4.text))
        ok &= ".xls" in r4.text

        con = sqlite3.connect(tmp / "atempo.db")
        names = [r[0] for r in con.execute("SELECT name FROM teams WHERE name LIKE 'TEST_%'")]
        people = [r[0] for r in con.execute("SELECT full_name FROM people WHERE full_name LIKE 'TEST %'")]
        links = con.execute(
            "SELECT COUNT(*) FROM team_memberships m JOIN people p ON p.id=m.person_id WHERE p.full_name LIKE 'TEST %'"
        ).fetchone()[0]
        con.close()
        print()
        print("Teams:", names)
        print("Persons:", people)
        print("Links:", links)
        ok &= len(names) == 5 and len(people) == 8 and links == 8
        print("\nRESULTAT:", "TOT OK" if ok else "FALLOWS")
        return 0 if ok else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
