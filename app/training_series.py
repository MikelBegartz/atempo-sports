"""Generación de entrenos recurrentes."""

from __future__ import annotations

import uuid
from datetime import date, timedelta, time

from sqlalchemy.orm import Session

from app.db import Training


def iter_weekdays(start: date, end: date, weekday: int) -> list[date]:
    """Fechas entre start y end (incluidos) que caen en weekday (0=lun…6=dom)."""
    if end < start:
        return []
    d = start
    # avanzar al primer weekday
    while d.weekday() != weekday:
        d += timedelta(days=1)
        if d > end:
            return []
    out: list[date] = []
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


def create_weekly_series(
    db: Session,
    *,
    season_id: int,
    team_id: int,
    weekday: int,
    start_date: date,
    end_date: date,
    start_time: time,
    end_time: time,
    venue_id: int | None,
    allows_share: bool = False,
    notes: str | None = None,
    is_draft: bool = False,
    is_manual: bool = False,
) -> tuple[str, int]:
    """Crea una sesión por cada semana. Devuelve (series_id, creadas)."""
    series_id = uuid.uuid4().hex[:12]
    dates = iter_weekdays(start_date, end_date, weekday)
    created = 0
    for d in dates:
        # evitar duplicado exacto mismo equipo/día/hora/pista
        exists = (
            db.query(Training)
            .filter(
                Training.season_id == season_id,
                Training.team_id == team_id,
                Training.session_date == d,
                Training.start_time == start_time,
                Training.end_time == end_time,
                Training.venue_id == venue_id,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            Training(
                season_id=season_id,
                team_id=team_id,
                session_date=d,
                start_time=start_time,
                end_time=end_time,
                venue_id=venue_id,
                allows_share=allows_share,
                series_id=series_id,
                notes=notes,
                is_draft=is_draft,
                is_manual=is_manual,
            )
        )
        created += 1
    db.commit()
    return series_id, created
