"""Exportación CSV de partidos y entrenos."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.db import Match, Training


def export_matches_csv(db: Session, season_id: int) -> str:
    rows = (
        db.query(Match)
        .options(joinedload(Match.team), joinedload(Match.venue))
        .filter(Match.season_id == season_id)
        .order_by(Match.match_date.nulls_last(), Match.start_time.nulls_last())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        [
            "jornada",
            "fecha",
            "inicio",
            "fin",
            "equipo",
            "rival",
            "local_visitante",
            "pista",
            "origen",
            "bloqueado",
            "external_id",
        ]
    )
    for m in rows:
        w.writerow(
            [
                m.jornada or "",
                m.match_date.isoformat() if m.match_date else "",
                m.start_time.strftime("%H:%M") if m.start_time else "",
                m.end_time.strftime("%H:%M") if m.end_time else "",
                m.team.name,
                m.opponent,
                "L" if m.is_home else "V",
                m.venue.name if m.venue else "",
                m.source,
                "1" if m.locked else "0",
                m.external_id or "",
            ]
        )
    return buf.getvalue()


def export_trainings_csv(db: Session, season_id: int) -> str:
    rows = (
        db.query(Training)
        .options(joinedload(Training.team), joinedload(Training.venue))
        .filter(
            Training.season_id == season_id,
            Training.is_draft.is_(False),
        )
        .order_by(Training.session_date, Training.start_time)
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        [
            "fecha",
            "inicio",
            "fin",
            "equipo",
            "pista",
            "compartir",
            "serie_id",
            "notas",
        ]
    )
    for t in rows:
        w.writerow(
            [
                t.session_date.isoformat(),
                t.start_time.strftime("%H:%M"),
                t.end_time.strftime("%H:%M"),
                t.team.name,
                t.venue.name if t.venue else "",
                "1" if t.allows_share else "0",
                t.series_id or "",
                t.notes or "",
            ]
        )
    return buf.getvalue()


def export_filename(prefix: str, season_name: str) -> str:
    safe = season_name.replace("/", "-").replace(" ", "_")
    stamp = datetime.now().strftime("%Y%m%d")
    return f"atempo_{prefix}_{safe}_{stamp}.csv"
