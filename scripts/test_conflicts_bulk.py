"""Test real dels conflictes: arrenca uvicorn amb CÒPIA de la BD i prova

1. Solapament de plantilla completa -> UNA línia "Tot l'equip", no una per persona.
2. Solapament parcial -> línia per persona (sense colapsar).
3. POST /season/{sid}/conflicts/ignore-bulk -> ignora les claus seleccionades.
4. Unignore scope=series -> el conflicte torna.
"""
from __future__ import annotations

import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SRC_DB = ROOT / "data" / "atempo.db"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fixture(db_path: Path, sid: int, club_id: int) -> None:
    """TEST_A i TEST_B comparteixen TOTA la plantilla (col·lapse 'tot l'equip');
    TEST_C comparteix P4 (jugador, hard) i P5 (reforç a C, soft) amb A
    i té P6 que no és a A (solapament parcial real)
    -> UN sol grup 'TEST_A ⇄ TEST_C — 2 persones'."""
    day = (date.today() + timedelta(days=10)).isoformat()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    vids = {}
    for name in ("TEST_PISTA", "TEST_PISTA2"):
        cur.execute(
            "INSERT INTO venues (club_id, name, allows_share_default, allows_matches) "
            "VALUES (?, ?, 0, 1)",
            (club_id, name),
        )
        vids[name] = cur.lastrowid
    vid = vids["TEST_PISTA"]
    vid2 = vids["TEST_PISTA2"]
    team_ids = {}
    for name in ("TEST_A", "TEST_B", "TEST_C"):
        cur.execute(
            "INSERT INTO teams (season_id, name, immovable) VALUES (?, ?, 0)",
            (sid, name),
        )
        team_ids[name] = cur.lastrowid
    person_ids = {}
    for name in ("TEST P1", "TEST P2", "TEST P3", "TEST P4", "TEST P5", "TEST P6"):
        cur.execute(
            "INSERT INTO people (season_id, full_name, is_player, is_coach) "
            "VALUES (?, ?, 1, 0)",
            (sid, name),
        )
        person_ids[name] = cur.lastrowid
    for pname in ("TEST P1", "TEST P2", "TEST P3"):
        for tname in ("TEST_A", "TEST_B"):
            cur.execute(
                "INSERT INTO team_memberships (team_id, person_id, role) VALUES (?, ?, 'player')",
                (team_ids[tname], person_ids[pname]),
            )
    for pname in ("TEST P4", "TEST P5"):
        cur.execute(
            "INSERT INTO team_memberships (team_id, person_id, role) VALUES (?, ?, 'player')",
            (team_ids["TEST_A"], person_ids[pname]),
        )
    cur.execute(
        "INSERT INTO team_memberships (team_id, person_id, role) VALUES (?, ?, 'player')",
        (team_ids["TEST_C"], person_ids["TEST P4"]),
    )
    cur.execute(
        "INSERT INTO team_memberships (team_id, person_id, role) VALUES (?, ?, 'reinforce')",
        (team_ids["TEST_C"], person_ids["TEST P5"]),
    )
    cur.execute(
        "INSERT INTO team_memberships (team_id, person_id, role) VALUES (?, ?, 'player')",
        (team_ids["TEST_C"], person_ids["TEST P6"]),
    )
    now = "2026-01-01 00:00:00"
    cur.execute(
        "INSERT INTO trainings (season_id, team_id, session_date, start_time, end_time, venue_id, "
        "allows_share, is_draft, is_manual, created_at) "
        "VALUES (?, ?, ?, '10:00:00', '11:00:00', ?, 0, 0, 0, ?)",
        (sid, team_ids["TEST_A"], day, vid, now),
    )
    cur.execute(
        "INSERT INTO matches (season_id, team_id, opponent, is_home, match_date, start_time, end_time, "
        "locked, source, created_at) "
        "VALUES (?, ?, 'RIVAL_C', 0, ?, '10:15:00', '11:15:00', 0, 'manual', ?)",
        (sid, team_ids["TEST_C"], day, now),
    )
    cur.execute(
        "INSERT INTO matches (season_id, team_id, opponent, is_home, match_date, start_time, end_time, "
        "locked, source, created_at) "
        "VALUES (?, ?, 'RIVAL_X', 0, ?, '10:30:00', '11:30:00', 0, 'manual', ?)",
        (sid, team_ids["TEST_B"], day, now),
    )
    con.commit()
    con.close()


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="atempo_conf_"))
    shutil.copy(SRC_DB, tmp / "atempo.db")
    for extra in SRC_DB.parent.glob(".*"):
        if extra.is_file():
            shutil.copy(extra, tmp / extra.name)

    con = sqlite3.connect(tmp / "atempo.db")
    sid, club_id = con.execute(
        "SELECT id, club_id FROM seasons ORDER BY id LIMIT 1"
    ).fetchone()
    con.close()
    fixture(tmp / "atempo.db", sid, club_id)

    port = free_port()
    env = dict(**__import__("os").environ, ATEMPO_DATA_DIR=str(tmp))
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', "
         f"port={port})"],
        cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    s = requests.Session()
    ok = True
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

        r = s.get(f"{base}/season/{sid}/conflicts")
        html = r.text
        print("1) GET conflicts:", r.status_code)
        ok &= r.status_code == 200

        collapse_ok = "TEST_B tamb" in html and "TEST_A" in html
        print("2) Col·lapse 'tot l'equip':", collapse_ok)
        ok &= collapse_ok
        for p in ("TEST P1", "TEST P2", "TEST P3", "TEST P4", "TEST P5"):
            if f"{p} est" in html:
                print(f"   !! {p} segueix com a conflicte individual")
                ok = False
        grp = "TEST_A ⇄ TEST_C — 2 persones" in html
        print("3) Solapament parcial A<->C agrupat (2 persones):", grp)
        ok &= grp

        # Detall del grup: per persona + per dia, amb severitat per rol
        gkeys = re.findall(r'/conflict-group/([^"\']+)', html)
        gkey = next((k for k in gkeys if k.startswith("overlap:")), None)
        print("3b) Enllaç a detall de grup trobat:", bool(gkey))
        ok &= gkey is not None
        if gkey:
            r = s.get(f"{base}/season/{sid}/conflict-group/{gkey}")
            det = r.text
            print("3c) Detall grup:", r.status_code,
                  "| P4:", "TEST P4" in det, "| P5:", "TEST P5" in det,
                  "| per persona:", "Per persona" in det, "| per dia:", "Per dia" in det)
            ok &= r.status_code == 200
            ok &= "TEST P4" in det and "TEST P5" in det
            ok &= "Per persona" in det and "Per dia" in det
            # P5 és reforç a C -> soft (badge warn); P4 jugador als dos -> hard
            ok &= "badge warn" in det and "badge danger" in det
            print("3d) Severitat per rol (warn+danger):", "badge warn" in det and "badge danger" in det)

        keys = re.findall(r'name="conflict_keys" value="([^"]+)"', html)
        keys = list(dict.fromkeys(keys))
        # els valors de grup porten claus de membres separades per '|'
        flat_keys = [k for v in keys for k in v.split("|")]
        flat_keys = list(dict.fromkeys(flat_keys))
        print(f"4) Checkboxes trobats: {len(keys)} (claus reals: {len(flat_keys)})")
        ok &= len(keys) >= 3

        r = s.post(
            f"{base}/season/{sid}/conflicts/ignore-bulk",
            data=[("conflict_keys", k) for k in keys] + [("conflict_keys", keys[0])],
            allow_redirects=False,
        )
        print("5) POST ignore-bulk:", r.status_code)
        ok &= r.status_code == 303

        con = sqlite3.connect(tmp / "atempo.db")
        rows = con.execute(
            "SELECT conflict_key, ignored FROM conflicts WHERE season_id=? AND ignored=1",
            (sid,),
        ).fetchall()
        con.close()
        n_ignored = len(rows)
        print(f"6) Files ignorades a BD: {n_ignored} (esperades {len(flat_keys)}, duplicat deduplicat)")
        ok &= n_ignored == len(flat_keys)

        r = s.get(f"{base}/season/{sid}/conflicts")
        gone = "TEST_B tamb" not in r.text.split("ignored-conflicts")[0]
        print("7) El conflicte ja no surt a la llista activa:", gone)
        ok &= gone
        print("8) Apareix a la secció d'ignorats:", "Tot l" in r.text and "ignorats" in r.text.lower() or "ignored" in r.text.lower())

        # Unignore de la primera clau -> torna
        r = s.post(
            f"{base}/season/{sid}/conflict/{rows[0][0]}/unignore",
            data={"scope": "series"},
            allow_redirects=False,
        )
        con = sqlite3.connect(tmp / "atempo.db")
        back = con.execute(
            "SELECT ignored FROM conflicts WHERE season_id=? AND conflict_key=?",
            (sid, rows[0][0]),
        ).fetchone()[0]
        con.close()
        print("9) Unignore scope=series restaura:", r.status_code == 303 and back == 0)
        ok &= r.status_code == 303 and back == 0

        # Vista ?unique=1 també funciona
        r = s.get(f"{base}/season/{sid}/conflicts?unique=1")
        print("10) GET ?unique=1:", r.status_code, "| checkboxs:", r.text.count('conflict_keys'))
        ok &= r.status_code == 200

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
