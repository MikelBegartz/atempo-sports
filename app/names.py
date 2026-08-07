"""Etiquetas de lugar para partidos (pista / localidad federativa)."""

from __future__ import annotations

import re
import unicodedata


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").casefold()


_PREFIX_RE = re.compile(
    r"^(?:"
    r"c\.?\s*h\.?\s+|"
    r"c\.?\s*p\.?\s+|"
    r"h\.?\s*c\.?\s+|"
    r"c\.?\s*e\.?\s+|"
    r"club\s+d['']?\s*esports\s+|"
    r"club\s+hoquei\s+|"
    r"club\s+pat[ií]\s+|"
    r"club\s+patín\s+|"
    r"club\s+"
    r")",
    re.IGNORECASE,
)


def guess_locality(club_name: str) -> str:
    """Fallback si Sidgad no manda lugar: última palabra del club local."""
    s = " ".join((club_name or "").split())
    if not s:
        return ""
    s = _PREFIX_RE.sub("", s).strip() or s
    parts = s.split()
    if not parts:
        return s
    last = parts[-1]
    if last.isupper() or last.islower():
        return last.capitalize()
    return last


def match_local_name(match) -> str:
    return match.team.name if match.is_home else match.opponent


def match_away_name(match) -> str:
    return match.opponent if match.is_home else match.team.name


def match_place_label(match) -> str:
    """Local: pista del club si hay; si no, lugar Sidgad. Visitante: lugar Sidgad."""
    place = (getattr(match, "place_name", None) or "").strip()
    if match.is_home:
        if match.venue and match.venue.name:
            return match.venue.name
        if place:
            return place
        return "—"
    if place:
        return place
    # Sidgad a veces no rellena (p. ej. RFEP futura): aproximar
    return guess_locality(match.opponent) or "—"
