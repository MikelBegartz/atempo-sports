"""Entrega de correo: bandeja local + SMTP opcional."""

from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from app.db import DATA_DIR

OUTBOX = DATA_DIR / "mail_outbox.jsonl"
log = logging.getLogger("atempo.mail")


def _smtp_config() -> dict[str, str] | None:
    host = (os.environ.get("ATEMPO_SMTP_HOST") or "").strip()
    if not host:
        return None
    return {
        "host": host,
        "port": (os.environ.get("ATEMPO_SMTP_PORT") or "587").strip(),
        "user": (os.environ.get("ATEMPO_SMTP_USER") or "").strip(),
        "password": (os.environ.get("ATEMPO_SMTP_PASSWORD") or "").strip(),
        "from_addr": (
            os.environ.get("ATEMPO_SMTP_FROM")
            or os.environ.get("ATEMPO_SMTP_USER")
            or "atempo@localhost"
        ).strip(),
    }


def smtp_configured() -> bool:
    return _smtp_config() is not None


def deliver_email(*, to: str, subject: str, body: str) -> str:
    """
    Guarda siempre en data/mail_outbox.jsonl.
    Si hay SMTP configurado, intenta enviarlo.
    Devuelve: "smtp" | "outbox".
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "to": to,
        "subject": subject,
        "body": body,
    }
    with OUTBOX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    cfg = _smtp_config()
    if not cfg:
        return "outbox"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = to
    msg.set_content(body)

    try:
        port = int(cfg["port"])
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                cfg["host"], port, timeout=20, context=context
            ) as smtp:
                if cfg["user"]:
                    smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], port, timeout=20) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if cfg["user"]:
                    smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)
        return "smtp"
    except Exception as exc:
        log.warning("SMTP falló (%s); el mensaje queda en outbox.", exc)
        return "outbox"
