"""Helpers d'hores d'entrenament per equip / temporada."""

from __future__ import annotations

from app.db import Season, Team


def parse_hours(raw: str | None) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip().replace(",", ".")
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if v < 0 or v > 40:
        return None
    return round(v, 2)


def effective_hours(team: Team, season: Season) -> float | None:
    if team.training_hours_week is not None:
        return float(team.training_hours_week)
    if season.default_training_hours is not None:
        return float(season.default_training_hours)
    return None


def hours_configured(season: Season) -> bool:
    return season.default_training_hours is not None
