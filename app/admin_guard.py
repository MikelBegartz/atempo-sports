"""Protecció i registre d’accessos a /admin (operador)."""

from __future__ import annotations

import hmac
import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.db import DATA_DIR

LOG_FILE = DATA_DIR / "admin_access.jsonl"
STATE_FILE = DATA_DIR / "admin_guard.json"
RECOVERY_FILE = DATA_DIR / ".admin_recovery"

LOCK_MINUTES = 30
RECENT_LIMIT = 40
MIN_RECOVERY_LEN = 6


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds") + "Z"


def client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:80]
    if request.client and request.client.host:
        return request.client.host[:80]
    return "desconegut"


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"lockouts": {}, "diverted": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"lockouts": {}, "diverted": {}}


def _save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ip_allowed(ip: str) -> bool:
    raw = (os.environ.get("ATEMPO_ADMIN_ALLOW_IPS") or "").strip()
    if not raw:
        return True
    allowed = {p.strip() for p in raw.split(",") if p.strip()}
    return ip in allowed or ip in {"127.0.0.1", "::1"}


def recovery_word() -> str:
    env = (os.environ.get("ATEMPO_ADMIN_RECOVERY") or "").strip()
    if env:
        return " ".join(env.replace("\r", "\n").split())
    if RECOVERY_FILE.exists():
        raw = RECOVERY_FILE.read_text(encoding="utf-8").lstrip("\ufeff")
        return " ".join(raw.replace("\r", "\n").split())
    return ""


def recovery_configured() -> bool:
    return len(recovery_word()) >= MIN_RECOVERY_LEN


def set_recovery_word(word: str) -> str | None:
    """Desa la paraula de recuperació. Retorna error o None."""
    w = " ".join((word or "").split())
    if len(w) < MIN_RECOVERY_LEN:
        return "short"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RECOVERY_FILE.write_text(w + "\n", encoding="utf-8")
    return None


def check_recovery(raw: str | None) -> bool:
    # Sense distingir majúscules/minúscules (més fàcil de recordar)
    expected = " ".join(recovery_word().split()).casefold().encode("utf-8")
    got = " ".join((raw or "").split()).casefold().encode("utf-8")
    if not expected or not got or len(got) != len(expected):
        return False
    return hmac.compare_digest(got, expected)


def clear_lockout(ip: str) -> None:
    state = _load_state()
    changed = False
    if ip in (state.get("lockouts") or {}):
        state["lockouts"].pop(ip, None)
        changed = True
    if ip in (state.get("diverted") or {}):
        state["diverted"].pop(ip, None)
        changed = True
    if changed:
        _save_state(state)


def mark_diverted(ip: str) -> None:
    state = _load_state()
    state.setdefault("diverted", {})[ip] = _iso(
        _now() + timedelta(minutes=LOCK_MINUTES)
    )
    _save_state(state)


def is_diverted(ip: str) -> bool:
    state = _load_state()
    until_s = (state.get("diverted") or {}).get(ip)
    if not until_s:
        return False
    try:
        until = datetime.fromisoformat(until_s.replace("Z", ""))
    except ValueError:
        return False
    if until <= _now():
        state.get("diverted", {}).pop(ip, None)
        _save_state(state)
        return False
    return True


def is_locked(ip: str) -> tuple[bool, int]:
    state = _load_state()
    until_s = (state.get("lockouts") or {}).get(ip)
    if not until_s:
        return False, 0
    try:
        until = datetime.fromisoformat(until_s.replace("Z", ""))
    except ValueError:
        return False, 0
    now = _now()
    if until <= now:
        state["lockouts"].pop(ip, None)
        _save_state(state)
        return False, 0
    mins = max(1, int((until - now).total_seconds() // 60) + 1)
    return True, mins


def _append_log(row: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def record_attempt(request: Request, *, ok: bool, reason: str = "") -> None:
    ip = client_ip(request)
    ua = (request.headers.get("user-agent") or "")[:160]
    _append_log(
        {
            "at": _iso(_now()),
            "ip": ip,
            "ok": ok,
            "reason": reason,
            "ua": ua,
        }
    )
    if ok:
        clear_lockout(ip)


def recent_attempts(limit: int = RECENT_LIMIT) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    out: list[dict] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    out.reverse()
    return out


def attempt_summary() -> list[dict]:
    rows = recent_attempts(200)
    by_ip: dict[str, dict] = {}
    for row in rows:
        ip = row.get("ip") or "?"
        slot = by_ip.setdefault(
            ip,
            {"ip": ip, "fails": 0, "oks": 0, "last_at": row.get("at"), "last_ok": None},
        )
        if row.get("ok"):
            slot["oks"] += 1
            if slot["last_ok"] is None:
                slot["last_ok"] = row.get("at")
        else:
            slot["fails"] += 1
        if not slot.get("last_at"):
            slot["last_at"] = row.get("at")
    return sorted(by_ip.values(), key=lambda x: (-x["fails"], x["ip"]))
