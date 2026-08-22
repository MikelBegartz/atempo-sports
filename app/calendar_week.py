"""Datos para la vista de calendario (4 semanas)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session, joinedload

from app.conflicts import find_conflicts
from app.db import Match, Training
from app.names import match_away_name, match_local_name, match_place_label


WEEKDAYS = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
]

# Estado visual del partido en el calendario
STATUS_HARD = "hard"  # conflicto grave → rojo
STATUS_SOFT = "soft"  # aviso → granate
STATUS_CHANGED = "changed"  # cambiado vs oficial y limpio → verde
STATUS_OK = "ok"  # sin conflicto → gris
STATUS_TRAINING = "training"


@dataclass
class CalEvent:
    kind: str  # match|training
    id: int
    team: str
    title: str
    d: date
    start: time | None
    end: time | None
    venue: str | None
    href: str
    status: str = STATUS_OK  # hard|soft|changed|ok|training
    competition: str | None = None
    home: str | None = None
    away: str | None = None


@dataclass
class WeekBlock:
    """Una fila del calendario: días + nº ISO + etiqueta relativa a hoy."""

    days: list[date]
    iso_week: int
    iso_year: int
    # Desplazamiento respecto a la semana de hoy: 0=esta, 1=siguiente, 2=en 2…
    weeks_from_today: int
    relative: str = ""
    show_year: bool = False

    @property
    def monday(self) -> date:
        return self.days[0]

    @property
    def sunday(self) -> date:
        return self.days[6]


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_dates(monday: date) -> list[date]:
    return [monday + timedelta(days=i) for i in range(7)]


def relative_week_offset(week_monday: date, today: date | None = None) -> int:
    """Cuántas semanas de calendario hay entre el lunes de esa semana y el de hoy."""
    ref = monday_of(today or date.today())
    return (week_monday - ref).days // 7


def relative_week_key(offset: int) -> tuple[str, int | None]:
    """Clave i18n (+ n opcional) para la etiqueta relativa."""
    if offset == 0:
        return "calendar_rel_this", None
    if offset == 1:
        return "calendar_rel_next", None
    if offset == -1:
        return "calendar_rel_last", None
    if offset > 1:
        return "calendar_rel_in", offset
    return "calendar_rel_ago", abs(offset)


def build_week_block(monday: date, today: date | None = None) -> WeekBlock:
    today = today or date.today()
    days = week_dates(monday)
    iso_year, iso_week, _ = monday.isocalendar()
    offset = relative_week_offset(monday, today)
    return WeekBlock(
        days=days,
        iso_week=iso_week,
        iso_year=iso_year,
        weeks_from_today=offset,
        show_year=iso_year != today.isocalendar()[0],
    )


def _end_default(d: date, start: time, end: time | None, minutes: int = 90) -> time:
    if end:
        return end
    return (datetime.combine(d, start) + timedelta(minutes=minutes)).time()


def _match_status(
    match: Match,
    hard_ids: set[int],
    soft_ids: set[int],
) -> str:
    if match.id in hard_ids:
        return STATUS_HARD
    if match.id in soft_ids:
        return STATUS_SOFT
    if match.is_changed_from_official:
        return STATUS_CHANGED
    return STATUS_OK


def build_four_weeks(
    db: Session, season_id: int, any_day: date, today: date | None = None
) -> tuple[date, list[WeekBlock], dict[date, list[CalEvent]]]:
    """Cuatro semanas a partir del lunes de la semana de `any_day`."""
    today = today or date.today()
    monday = monday_of(any_day)
    week_blocks = [build_week_block(monday + timedelta(days=7 * i), today) for i in range(4)]
    days = [d for w in week_blocks for d in w.days]
    start, end = days[0], days[-1]

    conflicts = find_conflicts(db, season_id)
    hard_ids: set[int] = set()
    soft_ids: set[int] = set()
    for c in conflicts:
        target = hard_ids if c.severity == "hard" else soft_ids
        for mid in c.match_ids:
            target.add(mid)
    # Un partido con soft y hard solo cuenta como hard
    soft_ids -= hard_ids

    matches = (
        db.query(Match)
        .options(joinedload(Match.team), joinedload(Match.venue))
        .filter(
            Match.season_id == season_id,
            Match.match_date >= start,
            Match.match_date <= end,
        )
        .all()
    )
    trainings = (
        db.query(Training)
        .options(joinedload(Training.team), joinedload(Training.venue))
        .filter(
            Training.season_id == season_id,
            Training.session_date >= start,
            Training.session_date <= end,
            Training.is_draft.is_(False),
        )
        .all()
    )

    by_day: dict[date, list[CalEvent]] = {d: [] for d in days}

    for m in matches:
        assert m.match_date
        st = m.start_time
        et = _end_default(m.match_date, st, m.end_time) if st else None
        local = match_local_name(m)
        visit = match_away_name(m)
        by_day.setdefault(m.match_date, []).append(
            CalEvent(
                kind="match",
                id=m.id,
                team=local,
                title=f"{local} – {visit}",
                d=m.match_date,
                start=st,
                end=et,
                venue=match_place_label(m),
                href=f"/season/{season_id}/matches?m={m.id}#fitxa",
                status=_match_status(m, hard_ids, soft_ids),
                competition=m.team.category,
                home=local,
                away=visit,
            )
        )

    for t in trainings:
        by_day.setdefault(t.session_date, []).append(
            CalEvent(
                kind="training",
                id=t.id,
                team=t.team.name,
                title="entreno",
                d=t.session_date,
                start=t.start_time,
                end=t.end_time,
                venue=t.venue.name if t.venue else None,
                href=f"/season/{season_id}/trainings",
                status=STATUS_TRAINING,
                competition=t.team.category,
            )
        )

    for d in by_day:
        by_day[d].sort(
            key=lambda e: (
                e.start or time(23, 59),
                e.end or time(23, 59),
                e.team,
            )
        )

    return monday, week_blocks, by_day


def build_week(
    db: Session, season_id: int, any_day: date
) -> tuple[date, list[date], dict[date, list[CalEvent]]]:
    """Compatibilidad: una semana (usa la primera de las cuatro)."""
    monday, week_blocks, by_day = build_four_weeks(db, season_id, any_day)
    days = week_blocks[0].days
    return monday, days, {d: by_day.get(d, []) for d in days}


def build_match_draft(
    db: Session,
    season_id: int,
    any_day: date,
    today: date | None = None,
    horizon: str | None = None,
) -> tuple[list[date], list[time], dict[date, dict[time, list[dict]]], date, date]:
    """Vista de borrador de partits: dies files, hores columnes."""
    today = today or date.today()
    if horizon == "m1":
        start, end = today, today + timedelta(days=30)
    elif horizon == "m2":
        start, end = today + timedelta(days=31), today + timedelta(days=60)
    elif horizon == "later":
        start, end = today + timedelta(days=61), today + timedelta(days=120)
    else:
        monday = monday_of(any_day)
        week_blocks = [build_week_block(monday + timedelta(days=7 * i), today) for i in range(4)]
        days = [d for w in week_blocks for d in w.days]
        start, end = days[0], days[-1]

    matches = (
        db.query(Match)
        .options(joinedload(Match.team), joinedload(Match.venue))
        .filter(
            Match.season_id == season_id,
            Match.match_date >= start,
            Match.match_date <= end,
        )
        .all()
    )

    conflicts = find_conflicts(db, season_id)
    hard_ids: set[int] = set()
    soft_ids: set[int] = set()
    for c in conflicts:
        target = hard_ids if c.severity == "hard" else soft_ids
        for mid in c.match_ids:
            target.add(mid)
    soft_ids -= hard_ids

    all_hours: set[time] = set()
    match_days: set[date] = set()
    by_day_hour: dict[tuple[date, time], list[dict]] = {}

    for m in matches:
        if not m.match_date or not m.start_time:
            continue
        end_t = _end_default(m.match_date, m.start_time, m.end_time)
        status = _match_status(m, hard_ids, soft_ids)
        slot = {
            "id": m.id,
            "home": match_local_name(m),
            "away": match_away_name(m),
            "competition": m.team.category or "",
            "venue": match_place_label(m) or "",
            "start": m.start_time,
            "end": end_t,
            "status": status,
            "weekday": m.match_date.weekday(),
            "is_home": bool(m.is_home),
        }
        by_day_hour.setdefault((m.match_date, m.start_time), []).append(slot)
        all_hours.add(m.start_time)
        match_days.add(m.match_date)

    sorted_days = sorted(match_days)
    sorted_hours = sorted(all_hours)
    grid: dict[date, dict[time, list[dict]]] = {d: {h: by_day_hour.get((d, h), []) for h in sorted_hours} for d in sorted_days}
    return sorted_days, sorted_hours, grid, start, end


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def build_global_draft(
    db: Session,
    season_id: int,
    any_day: date,
    today: date | None = None,
) -> tuple[list[date], list[time], dict[date, list[dict]], date, date, time, time, int, dict[date, int]]:
    """Vista de calendario combinada: partits + entrenaments."""
    today = today or date.today()
    monday = monday_of(any_day)
    week_blocks = [build_week_block(monday + timedelta(days=7 * i), today) for i in range(4)]
    days = [d for w in week_blocks for d in w.days]
    start, end = days[0], days[-1]

    conflicts = find_conflicts(db, season_id)
    hard_ids: set[int] = set()
    soft_ids: set[int] = set()
    for c in conflicts:
        target = hard_ids if c.severity == "hard" else soft_ids
        for mid in c.match_ids:
            target.add(mid)
        for tid in c.training_ids:
            target.add(tid)
    soft_ids -= hard_ids

    matches = (
        db.query(Match)
        .options(joinedload(Match.team), joinedload(Match.venue))
        .filter(
            Match.season_id == season_id,
            Match.match_date >= start,
            Match.match_date <= end,
        )
        .all()
    )
    trainings = (
        db.query(Training)
        .options(joinedload(Training.team), joinedload(Training.venue))
        .filter(
            Training.season_id == season_id,
            Training.session_date >= start,
            Training.session_date <= end,
            Training.is_draft.is_(False),
        )
        .all()
    )

    day_slots: dict[date, list[dict]] = {}
    all_minutes: list[int] = []

    for m in matches:
        if not m.match_date or not m.start_time:
            continue
        end_t = _end_default(m.match_date, m.start_time, m.end_time)
        status = _match_status(m, hard_ids, soft_ids)
        slot = {
            "id": m.id,
            "kind": "match",
            "home": match_local_name(m),
            "away": match_away_name(m),
            "team": m.team.name if m.team else "",
            "competition": m.team.category or "",
            "venue": match_place_label(m) or "",
            "date": m.match_date,
            "start": m.start_time,
            "end": end_t,
            "status": status,
            "href": f"/season/{season_id}/matches?m={m.id}#fitxa",
            "is_home": bool(m.is_home),
        }
        day_slots.setdefault(m.match_date, []).append(slot)
        all_minutes.extend([_minutes(m.start_time), _minutes(end_t)])

    group_slots: dict[tuple, dict] = {}
    for t in trainings:
        if not t.session_date or not t.start_time:
            continue
        monday = t.session_date - timedelta(days=t.session_date.weekday())
        key = (
            t.session_date,
            t.start_time,
            t.end_time,
            t.venue_id,
            t.training_group_id or 0,
        )
        if key not in group_slots:
            group_slots[key] = {
                "id": t.id,
                "kind": "training",
                "home": None,
                "away": None,
                "teams": [],
                "competition": t.team.category or "" if t.team else "",
                "venue": t.venue.name if t.venue else "",
                "date": t.session_date,
                "start": t.start_time,
                "end": t.end_time,
                "status": STATUS_TRAINING,
                "href": f"/season/{season_id}/trainings?draft_week={monday.isoformat()}#draft",
            }
        if t.team:
            group_slots[key]["teams"].append(t.team.name)
        if t.id in hard_ids:
            group_slots[key]["status"] = STATUS_HARD
        elif t.id in soft_ids and group_slots[key]["status"] != STATUS_HARD:
            group_slots[key]["status"] = STATUS_SOFT
        all_minutes.extend([_minutes(t.start_time), _minutes(t.end_time)])

    for slot in group_slots.values():
        day_slots.setdefault(slot["date"], []).append(slot)

    sorted_days = sorted(day_slots.keys())
    if not sorted_days:
        sorted_days = days

    if all_minutes:
        min_min = min(all_minutes)
        max_min = max(all_minutes)
    else:
        min_min = _minutes(time(17, 0))
        max_min = _minutes(time(22, 0))
    day_start_min = (min_min // 15) * 15 - 15
    day_end_min = ((max_min + 14) // 15) * 15 + 15
    day_range = max(day_end_min - day_start_min, 1)
    start_hour = max(0, day_start_min // 60)
    end_hour = day_end_min // 60
    sorted_hours = [time(h, 0) for h in range(start_hour, end_hour + 1)]

    day_max_lanes: dict[date, int] = {}
    for d, slots in day_slots.items():
        slots.sort(key=lambda s: (_minutes(s["start"]), _minutes(s["end"])))
        for i, slot in enumerate(slots):
            s = _minutes(slot["start"])
            e = _minutes(slot["end"])
            slot["lane"] = i
            slot["left_pct"] = round((s - day_start_min) / day_range * 100, 2)
            slot["width_pct"] = round((e - s) / day_range * 100, 2)
        day_max_lanes[d] = len(slots)

    return sorted_days, sorted_hours, day_slots, start, end, day_start_min, day_range, day_max_lanes
