"""Peticiones de cambio: marco del rival + alternativas con mínimo impacto."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session, joinedload

from app.conflicts import Conflict, find_conflicts, people_for_team
from app.db import Match, Training, Venue, VenueAvailability


WEEKDAY_LABELS = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
]


@dataclass
class ChangeFrame:
    """Caja de condiciones que debe cumplir el cambio."""

    window_start: date | None = None
    window_end: date | None = None
    allowed_weekdays: list[int] = field(default_factory=list)  # 0=lun … 6=dom
    time_from: time | None = None
    time_to: time | None = None
    must_end_before: time | None = None
    # Propuesta concreta (opcional)
    proposed_date: date | None = None
    proposed_start: time | None = None
    proposed_end: time | None = None
    proposed_venue_id: int | None = None


@dataclass
class SlotOption:
    match_date: date
    start_time: time
    end_time: time
    venue_id: int | None
    hard: list[Conflict]
    soft: list[Conflict]
    impact_score: float
    label: str


@dataclass
class TrainingMergeSlot:
    session_date: date
    start_time: time
    end_time: time
    venue_id: int | None
    venue_name: str
    label: str


def match_duration_minutes(m: Match) -> int:
    if m.match_date and m.start_time and m.end_time:
        a = datetime.combine(m.match_date, m.start_time)
        b = datetime.combine(m.match_date, m.end_time)
        mins = int((b - a).total_seconds() // 60)
        return mins if mins > 0 else 90
    return 90


def _training_duration_minutes(t: Training) -> int:
    if t.start_time and t.end_time and t.session_date:
        a = datetime.combine(t.session_date, t.start_time)
        b = datetime.combine(t.session_date, t.end_time)
        mins = int((b - a).total_seconds() // 60)
        return mins if mins > 0 else 90
    return 90


def _time_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _in_frame(slot_date: date, start: time, end: time, frame: ChangeFrame) -> bool:
    if frame.window_start and slot_date < frame.window_start:
        return False
    if frame.window_end and slot_date > frame.window_end:
        return False
    if frame.allowed_weekdays and slot_date.weekday() not in frame.allowed_weekdays:
        return False
    if frame.time_from and start < frame.time_from:
        return False
    if frame.time_to and start > frame.time_to:
        return False
    if frame.must_end_before and end > frame.must_end_before:
        return False
    return True


def _overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return a_start < b_end and b_start < a_end


def _impact_score(
    m: Match,
    slot_date: date,
    start: time,
    hard: list[Conflict],
    soft: list[Conflict],
) -> float:
    score = len(hard) * 1000 + len(soft) * 10
    if m.match_date:
        score += abs((slot_date - m.match_date).days) * 2
    if m.start_time:
        a = m.start_time.hour * 60 + m.start_time.minute
        b = start.hour * 60 + start.minute
        score += abs(a - b) / 30.0
    return score


def evaluate_slot(
    db: Session,
    match: Match,
    slot_date: date,
    start: time,
    end: time,
    venue_id: int | None,
) -> SlotOption:
    override = {
        match.id: {
            "match_date": slot_date,
            "start_time": start,
            "end_time": end,
            "venue_id": venue_id,
        }
    }
    all_c = find_conflicts(db, match.season_id, override)
    # Solo conflictos que involucran este partido (impacto del cambio)
    related = [c for c in all_c if match.id in c.match_ids]
    hard = [c for c in related if c.severity == "hard"]
    soft = [c for c in related if c.severity == "soft"]
    venue_name = ""
    if venue_id:
        v = db.get(Venue, venue_id)
        venue_name = f" · {v.name}" if v else f" · pista #{venue_id}"
    label = (
        f"{WEEKDAY_LABELS[slot_date.weekday()]} {slot_date.isoformat()} "
        f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}{venue_name}"
    )
    return SlotOption(
        match_date=slot_date,
        start_time=start,
        end_time=end,
        venue_id=venue_id,
        hard=hard,
        soft=soft,
        impact_score=_impact_score(match, slot_date, start, hard, soft),
        label=label,
    )


def _venue_open_for_training(
    db: Session,
    venue_id: int,
    weekday: int,
    start: time,
    end: time,
) -> bool:
    rows = (
        db.query(VenueAvailability)
        .filter(
            VenueAvailability.venue_id == venue_id,
            VenueAvailability.weekday == weekday,
        )
        .all()
    )
    if not rows:
        return True
    s = _time_minutes(start)
    e = _time_minutes(end)
    for r in rows:
        rs = _time_minutes(r.start_time)
        re = _time_minutes(r.end_time)
        if rs <= s and e <= re:
            return True
    return False


def suggest_alternatives(
    db: Session,
    match: Match,
    frame: ChangeFrame,
    limit: int = 5,
) -> list[SlotOption]:
    """Genera huecos dentro del marco, ordenados por mínimo impacto."""
    if match.locked or match.team.immovable:
        return []

    duration = match_duration_minutes(match)
    venues = (
        db.query(Venue)
        .filter(Venue.club_id == match.season.club_id)
        .order_by(Venue.name)
        .all()
    )
    if match.is_home:
        venue_candidates: list[int | None] = (
            [match.venue_id]
            if match.venue_id
            else [v.id for v in venues]
        )
        # Probar también otras pistas si la propia está pillada
        for v in venues:
            if v.id not in venue_candidates:
                venue_candidates.append(v.id)
        if match.team.only_venue_id:
            venue_candidates = [match.team.only_venue_id]
    else:
        venue_candidates = [None]

    # Rango de fechas
    if frame.window_start and frame.window_end:
        d0, d1 = frame.window_start, frame.window_end
    elif frame.proposed_date:
        d0 = d1 = frame.proposed_date
    elif match.match_date:
        d0 = match.match_date - timedelta(days=7)
        d1 = match.match_date + timedelta(days=14)
    else:
        d0 = date.today()
        d1 = d0 + timedelta(days=21)

    # Franja horaria de búsqueda
    t_from = frame.time_from or time(9, 0)
    t_to = frame.time_to or time(21, 0)
    if match.team.not_before and match.team.not_before > t_from:
        t_from = match.team.not_before

    options: list[SlotOption] = []
    seen: set[tuple] = set()

    day = d0
    while day <= d1:
        if frame.allowed_weekdays and day.weekday() not in frame.allowed_weekdays:
            day += timedelta(days=1)
            continue

        minutes = t_from.hour * 60 + t_from.minute
        end_limit = t_to.hour * 60 + t_to.minute
        while minutes <= end_limit:
            start = time(minutes // 60, minutes % 60)
            end_dt = datetime.combine(day, start) + timedelta(minutes=duration)
            end = end_dt.time()
            if end_dt.date() != day:
                break
            if not _in_frame(day, start, end, frame):
                minutes += 30
                continue
            if match.team.not_after and end > match.team.not_after:
                minutes += 30
                continue

            for vid in venue_candidates:
                key = (day, start, end, vid)
                if key in seen:
                    continue
                seen.add(key)
                opt = evaluate_slot(db, match, day, start, end, vid)
                options.append(opt)
            minutes += 30
        day += timedelta(days=1)

    # Preferir sin conflictos duros, luego menor impacto
    options.sort(key=lambda o: (len(o.hard), o.impact_score, len(o.soft)))
    # Devolver primero los limpios; si no hay, los de menor daño
    clean = [o for o in options if not o.hard]
    if clean:
        return clean[:limit]
    return options[:limit]


def analyze_change(
    db: Session, match_id: int, frame: ChangeFrame
) -> tuple[Match, SlotOption | None, list[SlotOption], str | None]:
    match = (
        db.query(Match)
        .options(
            joinedload(Match.team),
            joinedload(Match.venue),
            joinedload(Match.season),
        )
        .filter(Match.id == match_id)
        .first()
    )
    if not match:
        raise ValueError("Partido no encontrado")

    block_reason = None
    if match.locked:
        block_reason = "Este partido está bloqueado y no se puede mover."
    elif match.team.immovable:
        block_reason = f"El equipo {match.team.name} está marcado como no movible."

    concrete: SlotOption | None = None
    if frame.proposed_date and frame.proposed_start and not block_reason:
        duration = match_duration_minutes(match)
        end = frame.proposed_end
        if end is None:
            end = (
                datetime.combine(frame.proposed_date, frame.proposed_start)
                + timedelta(minutes=duration)
            ).time()
        vid = frame.proposed_venue_id
        if vid is None and match.is_home:
            vid = match.venue_id
        concrete = evaluate_slot(
            db, match, frame.proposed_date, frame.proposed_start, end, vid
        )

    alts: list[SlotOption] = []
    if not match.locked and not match.team.immovable:
        alts = suggest_alternatives(db, match, frame)

    return match, concrete, alts, block_reason


def default_auto_frame(match: Match) -> ChangeFrame:
    """Marco por defecto para resolución automática desde conflictos."""
    if match.match_date:
        d0 = match.match_date - timedelta(days=7)
        d1 = match.match_date + timedelta(days=14)
    else:
        d0 = date.today()
        d1 = d0 + timedelta(days=21)
    return ChangeFrame(
        window_start=d0,
        window_end=d1,
        allowed_weekdays=[],  # cualquier día
        time_from=time(17, 0),
        time_to=time(21, 0),
    )


def auto_fix_match(db: Session, match_id: int) -> tuple[bool, str]:
    """
    Aplica la mejor alternativa sin conflicto duro.
    Returns (applied, detail).
    """
    match = (
        db.query(Match)
        .options(
            joinedload(Match.team),
            joinedload(Match.venue),
            joinedload(Match.season),
        )
        .filter(Match.id == match_id)
        .first()
    )
    if not match:
        return False, "not_found"
    if match.locked:
        return False, "locked"
    if match.team and match.team.immovable:
        return False, "immovable"

    frame = default_auto_frame(match)
    alts = suggest_alternatives(db, match, frame, limit=20)
    clean = [o for o in alts if not o.hard]
    if not clean:
        return False, "no_clean"

    best = clean[0]
    # Revalidar
    opt = evaluate_slot(
        db, match, best.match_date, best.start_time, best.end_time, best.venue_id
    )
    if opt.hard:
        return False, "no_clean"

    match.snapshot_official_from_current()
    match.match_date = best.match_date
    match.start_time = best.start_time
    match.end_time = best.end_time
    if match.is_home:
        match.venue_id = best.venue_id
    db.commit()
    return True, best.label


def auto_fix_match_ids(
    db: Session, match_ids: list[int]
) -> tuple[int, int, list[int]]:
    """Aplica auto_fix a una lista. Returns (ok, failed, failed_ids)."""
    ok = 0
    failed_ids: list[int] = []
    # Deduplicar preservando orden
    seen: set[int] = set()
    ordered: list[int] = []
    for mid in match_ids:
        if mid in seen:
            continue
        seen.add(mid)
        ordered.append(mid)
    for mid in ordered:
        applied, _ = auto_fix_match(db, mid)
        if applied:
            ok += 1
        else:
            failed_ids.append(mid)
    return ok, len(failed_ids), failed_ids


def suggest_training_merge(
    db: Session,
    t_a: Training,
    t_b: Training,
    limit: int = 5,
) -> list[TrainingMergeSlot]:
    """Proposa franjes netes per entrenar junts dos equips."""
    season = t_a.season
    people_a = {p.id for p in people_for_team(db, t_a.team_id)}
    people_b = {p.id for p in people_for_team(db, t_b.team_id)}
    all_people = people_a | people_b

    duration = max(_training_duration_minutes(t_a), _training_duration_minutes(t_b))
    d0 = date.today()
    d1 = d0 + timedelta(days=21)

    t_from = time(17, 0)
    t_to = time(21, 0)
    for tm in [t_a.team, t_b.team]:
        if tm.not_before and tm.not_before > t_from:
            t_from = tm.not_before
        if tm.not_after and tm.not_after < t_to:
            t_to = tm.not_after

    venues = (
        db.query(Venue)
        .filter(Venue.club_id == season.club_id)
        .order_by(Venue.name)
        .all()
    )
    matches = db.query(Match).filter(Match.season_id == season.id).all()
    trainings = (
        db.query(Training)
        .options(joinedload(Training.team), joinedload(Training.venue))
        .filter(
            Training.season_id == season.id,
            Training.is_draft.is_(False),
            Training.id.notin_([t_a.id, t_b.id]),
        )
        .all()
    )

    people_cache: dict[int, set[int]] = {}

    def team_people(tid: int) -> set[int]:
        if tid not in people_cache:
            people_cache[tid] = {p.id for p in people_for_team(db, tid)}
        return people_cache[tid]

    other_events: list[tuple[date, time, time, int | None, set[int], bool, bool]] = []
    for m in matches:
        if m.match_date and m.start_time:
            et = m.end_time or (
                datetime.combine(m.match_date, m.start_time) + timedelta(minutes=90)
            ).time()
            share = bool(m.venue.allows_share_default) if m.venue else False
            other_events.append(
                (
                    m.match_date,
                    m.start_time,
                    et,
                    m.venue_id if m.is_home else None,
                    team_people(m.team_id),
                    share,
                    False,
                )
            )
    for t in trainings:
        share = t.allows_share or (
            bool(t.venue.allows_share_default) if t.venue else False
        )
        other_events.append(
            (
                t.session_date,
                t.start_time,
                t.end_time,
                t.venue_id,
                team_people(t.team_id),
                share,
                True,
            )
        )

    proposals: list[TrainingMergeSlot] = []
    seen: set[tuple[date, time, int | None]] = set()
    ref_date = t_a.session_date or t_b.session_date or d0
    ref_start = t_a.start_time or t_b.start_time or t_from

    d = d0
    while d <= d1:
        wd = d.weekday()
        minutes = _time_minutes(t_from)
        end_limit = _time_minutes(t_to)
        while minutes + duration <= end_limit:
            start = time(minutes // 60, minutes % 60)
            end_dt = datetime.combine(d, start) + timedelta(minutes=duration)
            end = end_dt.time()
            for v in venues:
                key = (d, start, v.id)
                if key in seen:
                    continue
                seen.add(key)
                if not _venue_open_for_training(db, v.id, wd, start, end):
                    continue
                clean = True
                for (ed, est, een, ev, ep, eshare, _) in other_events:
                    if ed != d:
                        continue
                    if not _overlaps(start, end, est, een):
                        continue
                    if ev == v.id and not eshare:
                        clean = False
                        break
                    if all_people & ep:
                        clean = False
                        break
                if not clean:
                    continue
                label = (
                    f"{WEEKDAY_LABELS[wd]} {d.isoformat()} "
                    f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')} · {v.name}"
                )
                proposals.append(
                    TrainingMergeSlot(d, start, end, v.id, v.name, label)
                )
            minutes += 30
        d += timedelta(days=1)

    proposals.sort(
        key=lambda s: (
            abs((s.session_date - ref_date).days),
            abs(_time_minutes(s.start_time) - _time_minutes(ref_start)),
        )
    )
    return proposals[:limit]
