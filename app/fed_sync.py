"""Sincronització automàtica de partits federatius per a un club."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import Club, CompetitionSource, Season, SessionLocal
from app.import_fed import ImportReport, import_competition


def _competition_idc(external_id: str) -> int:
    try:
        return int(external_id)
    except ValueError:
        return 0


def sync_club_federation_matches(
    db: Session | None,
    club_id: int,
    *,
    season_ids: list[int] | None = None,
) -> list[ImportReport]:
    """
    Sincronitza totes les fonts federatives (RFEP/FECAPA) d’un club.
    Pot rebre una sessió oberta o crear-ne una de nova.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        club = db.get(Club, club_id)
        if not club:
            return []

        query = db.query(Season).filter(Season.club_id == club_id)
        if season_ids:
            query = query.filter(Season.id.in_(season_ids))
        seasons = query.all()

        reports: list[ImportReport] = []
        for season in seasons:
            sources = (
                db.query(CompetitionSource)
                .filter(CompetitionSource.season_id == season.id)
                .all()
            )
            for src in sources:
                idc = _competition_idc(src.external_id)
                if not idc:
                    continue
                report = import_competition(
                    db,
                    season.id,
                    src.source,
                    idc,
                    apply=True,
                    label=src.label,
                )
                reports.append(report)
        return reports
    finally:
        if owns_session:
            db.close()
