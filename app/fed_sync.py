"""Sincronització automàtica de partits federatius per a un club.

Responsabilitats:
- Recórrer les `CompetitionSource` enllaçades de cada temporada del club.
- Reimportar cada competició (crea, actualitza i elimina partits).
- Recalcular conflictes (ho fa `import_competition` → `persist_conflicts`).
- Registrar el resultat al `Club` (last_fed_sync_at / last_fed_sync_summary)
  perquè l'error sigui visible i diagnosticable, mai silenciat.
- `background_sync` s'executa com a FastAPI BackgroundTask (login, /app).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db import Club, CompetitionSource, Season, SessionLocal
from app.import_fed import ImportReport, import_competition
from app.sidgad import FEDERATIONS

logger = logging.getLogger("atempo.fed_sync")

# Interval mínim entre sincronitzacions automàtiques per club (evita
# martellejar Sidgad si l'usuari navega molt per l'app).
SYNC_MIN_INTERVAL_MIN = 30

# Guard en memòria per no llançar dues syncs del mateix club a la vegada.
_IN_FLIGHT: set[int] = set()
_IN_FLIGHT_LOCK = threading.Lock()


def _competition_idc(external_id: str) -> int:
    try:
        return int(external_id)
    except ValueError:
        return 0


def club_sync_due(
    db: Session, club_id: int, *, min_minutes: int = SYNC_MIN_INTERVAL_MIN
) -> bool:
    """True si el club no s'ha sincronitzat mai o fa més de `min_minutes`."""
    club = db.get(Club, club_id)
    if not club:
        return False
    last = club.last_fed_sync_at
    if last is None:
        return True
    return datetime.utcnow() - last >= timedelta(minutes=min_minutes)


def _summarize(reports: list[ImportReport]) -> str:
    errs = [
        f"{r.source}:{r.idc}: {r.error}" for r in reports if r.error
    ]
    if errs:
        return ("ERROR " + " | ".join(errs))[:190]
    created = sum(r.created for r in reports)
    updated = sum(r.updated for r in reports)
    removed = sum(getattr(r, "removed", 0) for r in reports)
    skipped = sum(r.skipped for r in reports)
    return (
        f"OK {len(reports)} fonts: +{created} nous, "
        f"~{updated} actualitzats, -{removed} eliminats, {skipped} sense canvi"
    )[:190]


def sync_club_federation_matches(
    db: Session | None,
    club_id: int,
    *,
    season_ids: list[int] | None = None,
    force: bool = False,
) -> list[ImportReport]:
    """
    Sincronitza totes les fonts federatives (RFEP/FECAPA/…) d’un club.

    - `force=False`: es salta si la darrera sync és recent (<30 min).
    - `force=True`: sempre s'executa (login, botó "Sincronitza ara").
    - Els errors es registren al log i al `Club.last_fed_sync_summary`.
      Mai es mengen en silenci.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        club = db.get(Club, club_id)
        if not club:
            return []

        if (
            not force
            and club.last_fed_sync_at is not None
            and datetime.utcnow() - club.last_fed_sync_at
            < timedelta(minutes=SYNC_MIN_INTERVAL_MIN)
        ):
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
                if src.source not in FEDERATIONS:
                    # Fonts no-Sidgad (p. ex. fvp) no tenen resync encara
                    continue
                idc = _competition_idc(src.external_id)
                if not idc:
                    continue
                try:
                    report = import_competition(
                        db,
                        season.id,
                        src.source,
                        idc,
                        apply=True,
                        label=src.label,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "fed_sync aixecat: club=%s season=%s source=%s idc=%s",
                        club_id,
                        season.id,
                        src.source,
                        idc,
                    )
                    report = ImportReport(
                        0, 0, 0, 0, 0, [],
                        error=str(exc), source=src.source, idc=idc,
                    )
                reports.append(report)
                if report.error:
                    logger.error(
                        "fed_sync error club=%s season=%s %s idc=%s: %s",
                        club_id, season.id, src.source, idc, report.error,
                    )
                else:
                    logger.info(
                        "fed_sync ok club=%s season=%s %s idc=%s: "
                        "fetched=%s matched=%s created=%s updated=%s "
                        "removed=%s skipped=%s",
                        club_id, season.id, src.source, idc,
                        report.fetched, report.matched, report.created,
                        report.updated, getattr(report, "removed", 0),
                        report.skipped,
                    )

        club.last_fed_sync_at = datetime.utcnow()
        club.last_fed_sync_summary = (
            _summarize(reports) if reports else "Sense fonts enllaçades"
        )
        db.commit()
        return reports
    finally:
        if owns_session:
            db.close()


def background_sync(club_id: int) -> None:
    """Wrapper per a FastAPI BackgroundTasks: mai trenca la petició."""
    with _IN_FLIGHT_LOCK:
        if club_id in _IN_FLIGHT:
            return
        _IN_FLIGHT.add(club_id)
    try:
        sync_club_federation_matches(None, club_id, force=True)
    except Exception:  # noqa: BLE001
        logger.exception("fed_sync background ha fallat: club=%s", club_id)
    finally:
        with _IN_FLIGHT_LOCK:
            _IN_FLIGHT.discard(club_id)
