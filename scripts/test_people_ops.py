"""Test real del gestor de persones: arrenca uvicorn amb CÒPIA de la BD i prova

1. GET /people -> checkboxes "sel" amb valor team:person.
2. Bulk move: treu de TEST_A i posa a TEST_B (conserva rol).
3. Bulk remove: treu del equip però la persona segueix al club.
4. Bulk delete: esborra la persona del club sencer.
5. Export CSV: capçalera + files.
6. Replace equip: preview no escriu; apply crea/vincula/treu segons el fitxer.
7. Replace club: apply esborra les persones que no són al fitxer.
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
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SRC_DB = ROOT / "data" / "atempo.db"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fixture(db_path: Path, sid: int) -> dict[str, int]:
    """TEST_A: TPA, TPB, TPBOTH. TEST_B: TPC, TPBOTH. TPFREE: sense equip."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    ids: dict[str, int] = {}
    for name in ("TEST_A", "TEST_B"):
        cur.execute(
            "INSERT INTO teams (season_id, name, immovable) VALUES (?, ?, 0)",
            (sid, name),
        )
        ids[name] = cur.lastrowid
    for name in ("TPA", "TPB", "TPC", "TPBOTH", "TPFREE"):
        cur.execute(
            "INSERT INTO people (season_id, full_name, is_player, is_coach) "
            "VALUES (?, ?, 1, 0)",
            (sid, name),
        )
        ids[name] = cur.lastrowid
    for pname, tname in (
        ("TPA", "TEST_A"), ("TPB", "TEST_A"), ("TPBOTH", "TEST_A"),
        ("TPC", "TEST_B"), ("TPBOTH", "TEST_B"),
    ):
        cur.execute(
            "INSERT INTO team_memberships (team_id, person_id, role) "
            "VALUES (?, ?, 'player')",
            (ids[tname], ids[pname]),
        )
    con.commit()
    con.close()
    return ids


def q(db_path: Path, sql: str, args=()):
    con = sqlite3.connect(db_path)
    rows = con.execute(sql, args).fetchall()
    con.close()
    return rows


def memberships_of(db_path: Path, person_id: int) -> list[int]:
    return [
        r[0]
        for r in q(
            db_path,
            "SELECT team_id FROM team_memberships WHERE person_id=?",
            (person_id,),
        )
    ]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="atempo_pops_"))
    shutil.copy(SRC_DB, tmp / "atempo.db")
    for extra in SRC_DB.parent.glob(".*"):
        if extra.is_file():
            shutil.copy(extra, tmp / extra.name)

    sid = q(tmp / "atempo.db", "SELECT id FROM seasons ORDER BY id LIMIT 1")[0][0]
    ids = fixture(tmp / "atempo.db", sid)

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

        db = tmp / "atempo.db"

        r = s.get(f"{base}/season/{sid}/people")
        print("1) GET people:", r.status_code)
        ok &= r.status_code == 200
        sels = re.findall(r'name="sel"\s+value="(\d+:\d+)"', r.text)
        print("   checkboxes sel:", len(sels))
        ok &= f"{ids['TEST_A']}:{ids['TPBOTH']}" in sels

        # 1b) Avís "jugador a més d'un equip": TPBOTH és player a A i B
        both_ms = q(
            db,
            "SELECT id FROM team_memberships WHERE person_id=? AND role='player'",
            (ids["TPBOTH"],),
        )
        multi_shown = all(
            f"memberships/{m[0]}/role" in r.text for m in both_ms
        ) and len(both_ms) == 2
        print("   avís jugador multi-equip:", multi_shown)
        ok &= multi_shown

        # 1c) Canvi de rol amb back=people torna a /people
        tpc_m = q(
            db,
            "SELECT id FROM team_memberships WHERE person_id=? AND team_id=?",
            (ids["TPC"], ids["TEST_B"]),
        )[0][0]
        r2 = s.post(
            f"{base}/season/{sid}/teams/memberships/{tpc_m}/role",
            data={"role": "coach", "back": "people"},
            allow_redirects=False,
        )
        cond = r2.status_code == 303 and "/people" in (r2.headers.get("location") or "")
        print("   role amb back=people:", cond)
        ok &= cond

        # 2) Bulk move TPBOTH de TEST_A a TEST_B
        r = s.post(
            f"{base}/season/{sid}/people/bulk",
            data={
                "action": "move",
                "sel": f"{ids['TEST_A']}:{ids['TPBOTH']}",
                "target_team_id": str(ids["TEST_B"]),
            },
            allow_redirects=False,
        )
        m = memberships_of(db, ids["TPBOTH"])
        cond = r.status_code == 303 and m == [ids["TEST_B"]]
        print("2) bulk move A->B:", r.status_code, "| ara a:", m)
        ok &= cond

        # 3) Bulk remove TPC de TEST_B -> persona viva, sense víncul
        r = s.post(
            f"{base}/season/{sid}/people/bulk",
            data={"action": "remove", "sel": f"{ids['TEST_B']}:{ids['TPC']}"},
            allow_redirects=False,
        )
        alive = q(db, "SELECT id FROM people WHERE id=?", (ids["TPC"],))
        cond = (
            r.status_code == 303
            and memberships_of(db, ids["TPC"]) == []
            and len(alive) == 1
        )
        print("3) bulk remove:", cond)
        ok &= cond

        # 4) Bulk delete TPFREE
        r = s.post(
            f"{base}/season/{sid}/people/bulk",
            data={"action": "delete", "sel": f"0:{ids['TPFREE']}"},
            allow_redirects=False,
        )
        gone = q(db, "SELECT id FROM people WHERE id=?", (ids["TPFREE"],)) == []
        print("4) bulk delete:", r.status_code == 303 and gone)
        ok &= r.status_code == 303 and gone

        # 5) Export CSV club
        r = s.get(f"{base}/season/{sid}/people/export?scope=club")
        has_hdr = "equipo;categoria;nombre;rol" in r.text
        has_rows = "TPA" in r.text and "TEST_A" in r.text
        print("5) export club:", r.status_code, "| hdr:", has_hdr, "| files:", has_rows)
        ok &= r.status_code == 200 and has_hdr and has_rows
        r = s.get(f"{base}/season/{sid}/people/export?scope=team&team_id={ids['TEST_A']}")
        only_a = "TPA" in r.text and "TPC" not in r.text
        print("   export team:", r.status_code, "| només A:", only_a)
        ok &= r.status_code == 200 and only_a

        # 6) Replace TEST_B: fitxer {TPBOTH jugador, TPNEW jugador}
        people_before = q(db, "SELECT COUNT(*) FROM people WHERE season_id=?", (sid,))[0][0]
        paste = f"TEST_B;;TPBOTH;jugador\nTEST_B;;TPNEW;jugador\n"
        r = s.post(
            f"{base}/season/{sid}/people/replace",
            data={
                "scope": "team",
                "scope_team_id": str(ids["TEST_B"]),
                "paste": paste,
            },
        )
        people_after_preview = q(
            db, "SELECT COUNT(*) FROM people WHERE season_id=?", (sid,)
        )[0][0]
        cond = (
            r.status_code == 200
            and people_after_preview == people_before
            and "TPNEW" in r.text
        )
        print("6) preview team (no escriu):", cond)
        ok &= cond

        rows_text = re.search(
            r'name="rows_text"[^>]*>([^<]*)</textarea>', r.text
        )
        rows_text = rows_text.group(1).strip() if rows_text else ""
        r = s.post(
            f"{base}/season/{sid}/people/replace/apply",
            data={
                "rows_text": rows_text,
                "scope": "team",
                "scope_team_id": str(ids["TEST_B"]),
            },
            allow_redirects=False,
        )
        newb = q(db, "SELECT id FROM people WHERE full_name='TPNEW' AND season_id=?", (sid,))
        b_members = q(
            db,
            "SELECT person_id FROM team_memberships WHERE team_id=?",
            (ids["TEST_B"],),
        )
        b_ids = {r[0] for r in b_members}
        cond = (
            r.status_code == 303
            and len(newb) == 1
            and b_ids == {ids["TPBOTH"], newb[0][0]}
        )
        print("7) apply team:", r.status_code, "| membres B:", sorted(b_ids))
        ok &= cond
        # TPBOTH segueix a TEST_A? No: el move anterior l'havia tret. TPA/TPB intactes
        a_ids = {r[0] for r in q(db, "SELECT person_id FROM team_memberships WHERE team_id=?", (ids["TEST_A"],))}
        cond = a_ids == {ids["TPA"], ids["TPB"]}
        print("   TEST_A intacta:", cond)
        ok &= cond

        # 8) Replace club: fitxer només TEST_A amb TPA+TPB -> tota la resta
        #    de persones del club s'esborren
        paste = "TEST_A;;TPA;jugador\nTEST_A;;TPB;jugador\n"
        r = s.post(
            f"{base}/season/{sid}/people/replace",
            data={"scope": "club", "paste": paste},
        )
        cond = r.status_code == 200 and "s'esborraran" in r.text or "borrar" in r.text.lower()
        print("8) preview club:", r.status_code)
        ok &= r.status_code == 200
        rows_text = re.search(
            r'name="rows_text"[^>]*>([^<]*)</textarea>', r.text
        )
        rows_text = rows_text.group(1).strip() if rows_text else ""
        n_before = q(db, "SELECT COUNT(*) FROM people WHERE season_id=?", (sid,))[0][0]
        r = s.post(
            f"{base}/season/{sid}/people/replace/apply",
            data={"rows_text": rows_text, "scope": "club"},
            allow_redirects=False,
        )
        left = q(
            db,
            "SELECT full_name FROM people WHERE season_id=? ORDER BY full_name",
            (sid,),
        )
        names = [r[0] for r in left]
        cond = r.status_code == 303 and set(names) == {"TPA", "TPB"}
        print(f"9) apply club: {r.status_code} | queden {len(names)}/{n_before}: {names[:6]}")
        ok &= cond

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
