"""Configuració per variables d’entorn (beta / producció)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def load_dotenv_file() -> None:
    """Carrega `.env` de l’arrel d’atempo si hi ha python-dotenv."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = ROOT_DIR / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def _flag(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().casefold()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def is_production() -> bool:
    env = (os.environ.get("ATEMPO_ENV") or "").strip().casefold()
    return env in {"production", "prod", "beta"}


def https_cookies() -> bool:
    if _flag("ATEMPO_HTTPS", default=False):
        return True
    return is_production()


def public_register_open() -> bool:
    """Registre públic tancat per defecte (beta)."""
    return _flag("ATEMPO_PUBLIC_REGISTER", default=False)


def demo_password() -> str | None:
    """
    Contrasenya del club demo Mataró.
    - Producció: només si ATEMPO_DEMO_PASSWORD (clau forta).
    - Local: ATEMPO_DEMO_PASSWORD o, si no hi ha, «mataro» (només desenvolupament).
    Retorna None si el demo no ha de rebre / mantenir clau automàtica.
    """
    explicit = (os.environ.get("ATEMPO_DEMO_PASSWORD") or "").strip()
    if explicit:
        return explicit
    if is_production():
        return None
    if _flag("ATEMPO_ALLOW_DEMO", default=True):
        return "mataro"
    return None


def smtp_configured() -> bool:
    return bool((os.environ.get("ATEMPO_SMTP_HOST") or "").strip())
