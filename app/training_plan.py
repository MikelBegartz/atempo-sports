"""Generador de borrador d'entrenaments (fase B)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, time, timedelta

from sqlalchemy.orm import Session, joinedload

from app.db import Match, Team, TeamMembership, Training, TrainingGroup, Venue
from app.training_groups import (
    group_label_for_teams,
    labels_by_team_ids,
    load_groups,
    parse_weekdays,
    team_display_label,
)
from app.training_hours import effective_hours
from app.training_solapes import (
    build_chains,
    load_solapes,
    solape_weekdays_for_group,
    solape_weekdays_for_team,
)


DEFAULT_WINDOW_START = time(16, 0)
DEFAULT_WINDOW_END = time(21, 0)
MIN_SESSION_MINUTES = 45
SLOT_STEP_MINUTES = 15
PREFERRED_SESSIONS = 3

# Dies preferits (0=dl … 6=dg) segons nombre de sessions
_WEEKDAYS_BY_COUNT: dict[int, list[int]] = {
    1: [2],
    2: [1, 3],
    3: [0, 2, 4],
    4: [0, 1, 3, 4],
    5: [0, 1, 2, 3, 4],
}


@dataclass
class Occupancy:
    d: date
    venue_id: int
    start: time
    end: time


@dataclass
class DraftWarning:
    code: str
    params: dict = field(default_factory=dict)


@dataclass
class DraftGenerateResult:
    created: int = 0
    discarded: int = 0
    warnings: list[DraftWarning] = field(default_factory=list)
    batch_id: str | None = None


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _time_from_minutes(m: int) -> time:
    m = max(0, min(m, 23 * 60 + 59))
    return time(m // 60, m % 60)


def _overlaps(a0: time, a1: time, b0: time, b1: time) -> bool:
    return _minutes(a0) < _minutes(b1) and _minutes(b0) < _minutes(a1)


def split_session_minutes(hours: float, prefer: int = PREFERRED_SESSIONS) -> list[int]:
    """Reparte hores setmanals en sessions (minuts, múltiples de 15). Preferència: 3."""
    total = int(round(float(hours) * 60 / SLOT_STEP_MINUTES) * SLOT_STEP_MINUTES)
    if total <= 0:
        return []
    n = prefer
    while n > 1 and total // n < MIN_SESSION_MINUTES:
        n -= 1
    if total < MIN_SESSION_MINUTES:
        return [total]
    base = (total // n // SLOT_STEP_MINUTES) * SLOT_STEP_MINUTES
    rem = total - base * n
    sessions = [base] * n
    i = 0
    while rem >= SLOT_STEP_MINUTES:
        sessions[i % n] += SLOT_STEP_MINUTES
        rem -= SLOT_STEP_MINUTES
        i += 1
    return [s for s in sessions if s > 0]


def preferred_weekdays(n_sessions: int) -> list[int]:
    return list(_WEEKDAYS_BY_COUNT.get(n_sessions, _WEEKDAYS_BY_COUNT[3][:n_sessions]))


def _team_window(team: Team) -> tuple[time, time]:
    start = team.not_before or DEFAULT_WINDOW_START
    end = team.not_after or DEFAULT_WINDOW_END
    if _minutes(end) <= _minutes(start):
        return DEFAULT_WINDOW_START, DEFAULT_WINDOW_END
    return start, end


def _venue_windows(
    venue: Venue, weekday: int, team_start: time, team_end: time
) -> list[tuple[time, time]]:
    """Intersecció disponibilitat pista ∩ franja equip. Sense franges → cap opció."""
    avails = [a for a in venue.availabilities if a.weekday == weekday]
    if not avails:
        return []
    out: list[tuple[time, time]] = []
    for a in avails:
        s = _time_from_minutes(max(_minutes(a.start_time), _minutes(team_start)))
        e = _time_from_minutes(min(_minutes(a.end_time), _minutes(team_end)))
        if _minutes(e) - _minutes(s) >= MIN_SESSION_MINUTES:
            out.append((s, e))
    return out


def _busy_at(
    occs: list[Occupancy], d: date, venue_id: int, start: time, end: time
) -> bool:
    for o in occs:
        if o.d != d or o.venue_id != venue_id:
            continue
        if _overlaps(start, end, o.start, o.end):
            return True
    return False


def _find_slot(
    *,
    d: date,
    duration_min: int,
    venues: list[Venue],
    team: Team,
    occs: list[Occupancy],
    allow_busy: bool = False,
) -> tuple[Venue, time, time] | None:
    team_start, team_end = _team_window(team)
    candidates = venues
    if team.only_venue_id:
        candidates = [v for v in venues if v.id == team.only_venue_id]
        if not candidates:
            return None

    weekday = d.weekday()
    for venue in candidates:
        for win_start, win_end in _venue_windows(venue, weekday, team_start, team_end):
            cursor = _minutes(win_start)
            end_limit = _minutes(win_end)
            while cursor + duration_min <= end_limit:
                st = _time_from_minutes(cursor)
                et = _time_from_minutes(cursor + duration_min)
                if allow_busy or not _busy_at(occs, d, venue.id, st, et):
                    return venue, st, et
                cursor += SLOT_STEP_MINUTES
    return None


@dataclass
class SoloPackResult:
    """Resultat d’encaixar tots els equips en solitari (sense escriure a la BD)."""

    sessions_needed: int = 0
    sessions_clean: int = 0
    clashes: int = 0  # xocs de pista (doble ús no autoritzat)
    unplaced: int = 0

    @property
    def fits_solo(self) -> bool:
        return self.sessions_needed > 0 and self.clashes == 0 and self.unplaced == 0


def simulate_solo_pack(
    db: Session,
    *,
    season,
    start: date | None = None,
    end: date | None = None,
) -> SoloPackResult:
    """Intenta col·locar totes les sessions en solitari (1 setmana tipica)."""
    from sqlalchemy.orm import joinedload

    from app.training_hours import effective_hours

    if start is None or end is None:
        start, _end_full = default_plan_range()
        # Una setmana: prou per veure si el patró setmanal encaixa
        end = start + timedelta(days=6)

    venues = (
        db.query(Venue)
        .options(joinedload(Venue.availabilities))
        .filter(Venue.club_id == season.club_id)
        .order_by(Venue.name)
        .all()
    )
    teams = (
        db.query(Team)
        .filter(Team.season_id == season.id)
        .order_by(Team.name)
        .all()
    )
    result = SoloPackResult()
    if not venues or not teams:
        return result

    occs = _load_base_occupancy(db, season.id, start, end)

    def sort_key(tm: Team) -> tuple:
        hours = effective_hours(tm, season) or 0.0
        return (0 if tm.only_venue_id else 1, -hours, tm.name)

    for team in sorted(teams, key=sort_key):
        hours = effective_hours(team, season)
        if hours is None or hours <= 0:
            continue
        durations = split_session_minutes(hours)
        weekdays = preferred_weekdays(len(durations))
        while len(weekdays) < len(durations):
            weekdays.append(weekdays[-1] if weekdays else 2)
        weekdays = weekdays[: len(durations)]
        for dur, wd in zip(durations, weekdays):
            for d in _dates_for_weekday(start, end, wd):
                result.sessions_needed += 1
                found = _find_slot(
                    d=d,
                    duration_min=dur,
                    venues=venues,
                    team=team,
                    occs=occs,
                    allow_busy=False,
                )
                if found:
                    venue, st, et = found
                    occs.append(
                        Occupancy(d=d, venue_id=venue.id, start=st, end=et)
                    )
                    result.sessions_clean += 1
                    continue
                # Sense huec lliure: forçar sobre una franja (xoc de pista)
                forced = _find_slot(
                    d=d,
                    duration_min=dur,
                    venues=venues,
                    team=team,
                    occs=occs,
                    allow_busy=True,
                )
                if forced:
                    venue, st, et = forced
                    occs.append(
                        Occupancy(d=d, venue_id=venue.id, start=st, end=et)
                    )
                    result.clashes += 1
                else:
                    result.unplaced += 1
    return result


def _load_base_occupancy(
    db: Session, season_id: int, start: date, end: date
) -> list[Occupancy]:
    occs: list[Occupancy] = []
    matches = (
        db.query(Match)
        .filter(
            Match.season_id == season_id,
            Match.is_home.is_(True),
            Match.match_date >= start,
            Match.match_date <= end,
            Match.venue_id.isnot(None),
            Match.start_time.isnot(None),
        )
        .all()
    )
    for m in matches:
        assert m.match_date and m.start_time and m.venue_id
        et = m.end_time or _time_from_minutes(_minutes(m.start_time) + 90)
        occs.append(
            Occupancy(d=m.match_date, venue_id=m.venue_id, start=m.start_time, end=et)
        )

    confirmed = (
        db.query(Training)
        .filter(
            Training.season_id == season_id,
            Training.session_date >= start,
            Training.session_date <= end,
            Training.venue_id.isnot(None),
            Training.is_draft.is_(False),
        )
        .all()
    )
    for t in confirmed:
        assert t.venue_id
        occs.append(
            Occupancy(
                d=t.session_date,
                venue_id=t.venue_id,
                start=t.start_time,
                end=t.end_time,
            )
        )
    return occs


def _dates_for_weekday(start: date, end: date, weekday: int) -> list[date]:
    d = start
    while d.weekday() != weekday:
        d += timedelta(days=1)
        if d > end:
            return []
    out: list[date] = []
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


def discard_drafts(db: Session, season_id: int, *, only_auto: bool = False) -> int:
    """Esborra borradors. Si only_auto, conserva les altes manuals."""
    q = db.query(Training).filter(
        Training.season_id == season_id, Training.is_draft.is_(True)
    )
    if only_auto:
        q = q.filter(Training.is_manual.is_(False))
    rows = q.all()
    n = len(rows)
    for t in rows:
        db.delete(t)
    if n:
        db.commit()
    return n


def _load_manual_draft_occupancy(
    db: Session, season_id: int, start: date, end: date
) -> list[Occupancy]:
    rows = (
        db.query(Training)
        .filter(
            Training.season_id == season_id,
            Training.is_draft.is_(True),
            Training.is_manual.is_(True),
            Training.session_date >= start,
            Training.session_date <= end,
            Training.venue_id.isnot(None),
        )
        .all()
    )
    out: list[Occupancy] = []
    for t in rows:
        assert t.venue_id
        out.append(
            Occupancy(
                d=t.session_date,
                venue_id=t.venue_id,
                start=t.start_time,
                end=t.end_time,
            )
        )
    return out


def apply_drafts(db: Session, season_id: int, until: date | None = None) -> tuple[int, str | None]:
    """Passa el patró del borrador al calendari, repetint-lo fins a la data indicada."""
    from app.db import Season, Training, default_end_date_for_season

    season = db.get(Season, season_id)
    drafts = (
        db.query(Training)
        .filter(Training.season_id == season_id, Training.is_draft.is_(True))
        .all()
    )
    if not drafts:
        return 0, None
    pattern_start = min(t.session_date for t in drafts)
    pattern_end = max(t.session_date for t in drafts)
    pattern_weeks = ((pattern_end - pattern_start).days // 7) + 1
    period = timedelta(days=pattern_weeks * 7)
    limit = until or season.end_date or default_end_date_for_season(season.name)

    batch = uuid.uuid4().hex[:12]
    created = 0
    for t in drafts:
        offset = t.session_date - pattern_start
        d = pattern_start
        while d <= limit:
            real_date = d + offset
            if real_date <= limit:
                exists = (
                    db.query(Training.id)
                    .filter(
                        Training.season_id == season_id,
                        Training.team_id == t.team_id,
                        Training.session_date == real_date,
                        Training.start_time == t.start_time,
                        Training.end_time == t.end_time,
                        Training.venue_id == t.venue_id,
                        Training.is_draft.is_(False),
                    )
                    .first()
                )
                if not exists:
                    db.add(
                        Training(
                            season_id=season_id,
                            team_id=t.team_id,
                            session_date=real_date,
                            start_time=t.start_time,
                            end_time=t.end_time,
                            venue_id=t.venue_id,
                            allows_share=t.allows_share,
                            is_draft=False,
                            apply_batch=batch,
                            training_group_id=t.training_group_id,
                            training_solape_id=t.training_solape_id,
                            notes=t.notes,
                        )
                    )
                    created += 1
            d += period
    if season is not None:
        season.last_training_apply_batch = batch
    db.commit()
    return created, batch


def revert_last_apply(db: Session, season_id: int) -> int:
    """Desfà la darrera aplicació: torna les sessions generades al borrador."""
    from app.db import Season

    season = db.get(Season, season_id)
    if not season or not season.last_training_apply_batch:
        return 0
    batch = season.last_training_apply_batch
    rows = (
        db.query(Training)
        .filter(
            Training.season_id == season_id,
            Training.apply_batch == batch,
            Training.is_draft.is_(False),
        )
        .all()
    )
    for t in rows:
        t.is_draft = True
        t.apply_batch = None
    season.last_training_apply_batch = None
    db.commit()
    return len(rows)


def can_revert_last_apply(db: Session, season_id: int) -> bool:
    from app.db import Season

    season = db.get(Season, season_id)
    if not season or not season.last_training_apply_batch:
        return False
    exists = (
        db.query(Training.id)
        .filter(
            Training.season_id == season_id,
            Training.apply_batch == season.last_training_apply_batch,
            Training.is_draft.is_(False),
        )
        .first()
    )
    return exists is not None


def _place_training(
    db: Session,
    *,
    season_id: int,
    team_id: int,
    d: date,
    st: time,
    et: time,
    venue_id: int,
    allows_share: bool,
    series_id: str,
    group_id: int | None,
    occs: list[Occupancy],
    occupy: bool = True,
    solape_id: int | None = None,
) -> bool:
    existing = (
        db.query(Training.id)
        .filter(
            Training.season_id == season_id,
            Training.team_id == team_id,
            Training.session_date == d,
            Training.start_time == st,
            Training.end_time == et,
            Training.venue_id == venue_id,
            Training.is_draft.is_(True),
        )
        .first()
    )
    if existing:
        return False
    db.add(
        Training(
            season_id=season_id,
            team_id=team_id,
            session_date=d,
            start_time=st,
            end_time=et,
            venue_id=venue_id,
            allows_share=allows_share,
            series_id=series_id,
            training_group_id=group_id,
            training_solape_id=solape_id,
            notes=None,
            is_draft=True,
        )
    )
    if occupy:
        occs.append(Occupancy(d=d, venue_id=venue_id, start=st, end=et))
    return True


def _find_span_slot(
    *,
    d: date,
    span_min: int,
    venues: list[Venue],
    win_start: time,
    win_end: time,
    occs: list[Occupancy],
    only_venue_id: int | None = None,
) -> tuple[Venue, time, time] | None:
    """Busca una franja contínua de span_min minuts (cascada de solapes)."""
    candidates = venues
    if only_venue_id:
        candidates = [v for v in venues if v.id == only_venue_id]
        if not candidates:
            return None
    weekday = d.weekday()
    for venue in candidates:
        for vs, ve in _venue_windows(venue, weekday, win_start, win_end):
            cursor = _minutes(vs)
            end_limit = _minutes(ve)
            while cursor + span_min <= end_limit:
                st = _time_from_minutes(cursor)
                et = _time_from_minutes(cursor + span_min)
                if not _busy_at(occs, d, venue.id, st, et):
                    return venue, st, et
                cursor += SLOT_STEP_MINUTES
    return None


def _force_weekdays_into_plan(
    weekdays: list[int], forced: list[int], n_sessions: int
) -> list[int]:
    """Assegura que els dies forçats (grup/solape) són al pla de sessions."""
    if n_sessions <= 0:
        return []
    new_wd = list(weekdays)
    forced = [d for d in forced if 0 <= d <= 6]
    for gd in forced:
        if gd not in new_wd and new_wd:
            new_wd[-1] = gd
        elif gd not in new_wd:
            new_wd.append(gd)
    while len(new_wd) > n_sessions:
        for i, w in enumerate(new_wd):
            if w not in forced:
                new_wd.pop(i)
                break
        else:
            new_wd.pop()
    while len(new_wd) < n_sessions:
        new_wd.append(new_wd[-1] if new_wd else 2)
    return new_wd[:n_sessions]


def _side_duration(
    side_team_ids: list[int],
    wd: int,
    plans: dict[int, list[tuple[int, int]]],
) -> int:
    durs: list[int] = []
    for tid in side_team_ids:
        for dur, w in plans.get(tid, []):
            if w == wd:
                durs.append(dur)
        if not durs and plans.get(tid):
            durs.append(plans[tid][0][0])
    return max(durs) if durs else MIN_SESSION_MINUTES


def _place_solape_chain(
    db: Session,
    *,
    season,
    chain,
    d: date,
    plans: dict[int, list[tuple[int, int]]],
    teams_by_id: dict[int, Team],
    venues: list[Venue],
    occs: list[Occupancy],
    series_prefix: str,
    result: DraftGenerateResult,
) -> int:
    """Col·loca una cascada A→B(→C…) el mateix dia/pista. Retorna sessions creades."""
    wd = d.weekday()
    durations = [
        _side_duration(side.team_ids, wd, plans) for side in chain.sides
    ]
    overlaps = [e.overlap_minutes for e in chain.edges]
    span = sum(durations) - sum(overlaps)
    if span < MIN_SESSION_MINUTES:
        return 0

    # Finestra: intersecció de tots els equips de la cadena
    all_teams = [
        teams_by_id[tid]
        for side in chain.sides
        for tid in side.team_ids
        if tid in teams_by_id
    ]
    if not all_teams:
        return 0
    starts = [_team_window(t)[0] for t in all_teams]
    ends = [_team_window(t)[1] for t in all_teams]
    win_start = max(starts, key=lambda t: _minutes(t))
    win_end = min(ends, key=lambda t: _minutes(t))
    if _minutes(win_end) - _minutes(win_start) < span:
        win_start, win_end = DEFAULT_WINDOW_START, DEFAULT_WINDOW_END

    only_venue = None
    venue_ids = {t.only_venue_id for t in all_teams if t.only_venue_id}
    if len(venue_ids) == 1:
        only_venue = next(iter(venue_ids))
    elif len(venue_ids) > 1:
        # Incompatibilitat de pista preferida
        for side in chain.sides:
            for tid in side.team_ids:
                tm = teams_by_id.get(tid)
                if tm:
                    result.warnings.append(
                        DraftWarning(
                            "unplaced",
                            {
                                "team": tm.name,
                                "date": d.isoformat(),
                                "mins": span,
                            },
                        )
                    )
        return 0

    found = _find_span_slot(
        d=d,
        span_min=span,
        venues=venues,
        win_start=win_start,
        win_end=win_end,
        occs=occs,
        only_venue_id=only_venue,
    )
    if not found:
        for side in chain.sides:
            for tid in side.team_ids:
                tm = teams_by_id.get(tid)
                if tm:
                    result.warnings.append(
                        DraftWarning(
                            "unplaced",
                            {
                                "team": tm.name,
                                "date": d.isoformat(),
                                "mins": durations[0],
                            },
                        )
                    )
        return 0

    venue, cascade_start, _cascade_end = found
    cursor = _minutes(cascade_start)
    created = 0
    # Temps d’inici de cada costat
    side_starts: list[int] = []
    for i, dur in enumerate(durations):
        if i == 0:
            side_starts.append(cursor)
        else:
            # B comença overlap minuts abans que acabi A
            prev_end = side_starts[i - 1] + durations[i - 1]
            side_starts.append(prev_end - overlaps[i - 1])

    for i, side in enumerate(chain.sides):
        st = _time_from_minutes(side_starts[i])
        et = _time_from_minutes(side_starts[i] + durations[i])
        # solape_id: edge que “defineix” aquest costat com a B, o el primer edge si és A
        if i == 0:
            solape_id = chain.edges[0].id
        else:
            solape_id = chain.edges[i - 1].id
        for tid in side.team_ids:
            if _place_training(
                db,
                season_id=season.id,
                team_id=tid,
                d=d,
                st=st,
                et=et,
                venue_id=venue.id,
                allows_share=True,
                series_id=f"{series_prefix}s{solape_id}t{tid}"[:12],
                group_id=side.group_id,
                occs=occs,
                occupy=False,
                solape_id=solape_id,
            ):
                created += 1

    cascade_end = _time_from_minutes(side_starts[-1] + durations[-1])
    occs.append(
        Occupancy(
            d=d,
            venue_id=venue.id,
            start=cascade_start,
            end=cascade_end,
        )
    )
    return created


def _place_group_block(
    db: Session,
    *,
    season,
    group: TrainingGroup,
    members: list[Team],
    d: date,
    duration_min: int,
    venues: list[Venue],
    occs: list[Occupancy],
    series_prefix: str,
    result: DraftGenerateResult,
) -> int:
    """Col·loca un bloc shared/overlap. Retorna sessions creades."""
    if len(members) < 2:
        return 0
    mode = "shared"
    # Grups = unitat (superequip). El solape és un concepte a part.
    # Finestra: intersecció d’equips del grup
    starts = []
    ends = []
    for tm in members:
        s, e = _team_window(tm)
        starts.append(s)
        ends.append(e)
    anchor = members[0]
    saved_before, saved_after = anchor.not_before, anchor.not_after
    inter_start = max(starts, key=lambda t: _minutes(t))
    inter_end = min(ends, key=lambda t: _minutes(t))
    if _minutes(inter_end) - _minutes(inter_start) < MIN_SESSION_MINUTES:
        inter_start, inter_end = DEFAULT_WINDOW_START, DEFAULT_WINDOW_END
    anchor.not_before = inter_start
    anchor.not_after = inter_end

    created = 0
    try:
        found = _find_slot(
            d=d,
            duration_min=duration_min,
            venues=venues,
            team=anchor,
            occs=occs,
        )
        if not found:
            for tm in members:
                result.warnings.append(
                    DraftWarning(
                        "unplaced",
                        {
                            "team": tm.name,
                            "date": d.isoformat(),
                            "mins": duration_min,
                        },
                    )
                )
            return 0
        venue, st, et = found
        for tm in members:
            if _place_training(
                db,
                season_id=season.id,
                team_id=tm.id,
                d=d,
                st=st,
                et=et,
                venue_id=venue.id,
                allows_share=True,
                series_id=f"{series_prefix}g{group.id}t{tm.id}"[:12],
                group_id=group.id,
                occs=occs,
                occupy=False,
            ):
                created += 1
        occs.append(Occupancy(d=d, venue_id=venue.id, start=st, end=et))
        return created
    finally:
        anchor.not_before = saved_before
        anchor.not_after = saved_after


@dataclass
class _PackUnit:
    team_ids: list[int]
    group_id: int | None
    minutes_needed: int
    minutes_placed: int = 0
    label: str = ""
    session_plan: list[int] = field(default_factory=list)


def _venue_day_windows(venue: Venue, weekday: int) -> list[tuple[time, time]]:
    """Franges d’hockey disponibles aquell dia."""
    avails = [a for a in venue.availabilities if a.weekday == weekday]
    if not avails:
        return []
    out: list[tuple[time, time]] = []
    for a in avails:
        if _minutes(a.end_time) - _minutes(a.start_time) >= MIN_SESSION_MINUTES:
            out.append((a.start_time, a.end_time))
    return out


def _free_segments(
    d: date,
    venue_id: int,
    win_start: time,
    win_end: time,
    occs: list[Occupancy],
) -> list[tuple[time, time]]:
    """Talla la finestra pels ocupats (partits / manuals)."""
    blocks = sorted(
        [
            (o.start, o.end)
            for o in occs
            if o.d == d
            and o.venue_id == venue_id
            and _overlaps(win_start, win_end, o.start, o.end)
        ],
        key=lambda x: _minutes(x[0]),
    )
    free: list[tuple[time, time]] = []
    cursor = _minutes(win_start)
    end_m = _minutes(win_end)
    for b0, b1 in blocks:
        b0m, b1m = _minutes(b0), _minutes(b1)
        if b0m > cursor and b0m - cursor >= MIN_SESSION_MINUTES:
            free.append(
                (_time_from_minutes(cursor), _time_from_minutes(min(b0m, end_m)))
            )
        cursor = max(cursor, b1m)
    if end_m - cursor >= MIN_SESSION_MINUTES:
        free.append((_time_from_minutes(cursor), _time_from_minutes(end_m)))
    return free


def _find_free_slot(
    *,
    d: date,
    duration_min: int,
    venues: list[Venue],
    occs: list[Occupancy],
) -> tuple[Venue, time, time] | None:
    """Primer huec lliure del dia (esquerra → dreta) a qualsevol pista."""
    for venue in venues:
        for win_start, win_end in _venue_day_windows(venue, d.weekday()):
            for seg_start, seg_end in _free_segments(
                d, venue.id, win_start, win_end, occs
            ):
                cursor = _minutes(seg_start)
                end_m = _minutes(seg_end)
                while cursor + duration_min <= end_m:
                    st = _time_from_minutes(cursor)
                    et = _time_from_minutes(cursor + duration_min)
                    if not _busy_at(occs, d, venue.id, st, et):
                        return venue, st, et
                    cursor += SLOT_STEP_MINUTES
    return None


def _weekday_priority(session_index: int, n_sessions: int) -> list[int]:
    """Dies preferits per a la sessió i (dl/dc/dv…), després la resta laborables."""
    preferred = preferred_weekdays(n_sessions)
    if session_index < len(preferred):
        first = preferred[session_index]
    else:
        first = preferred[-1] if preferred else 2
    rest = [d for d in (0, 1, 2, 3, 4) if d != first]
    # Preferir altres dies del patró abans que dimarts/dijous «extra»
    pref_set = set(preferred)
    rest.sort(key=lambda d: (0 if d in pref_set else 1, d))
    return [first] + rest


def _dense_pack_units(
    db: Session,
    *,
    season,
    units: list[_PackUnit],
    venues: list[Venue],
    start: date,
    end: date,
    occs: list[Occupancy],
    series_prefix: str,
    fill_all: bool = False,
) -> int:
    """Col·loca només les sessions setmanals degudes (p. ex. 3 × 90′), sense omplir forats sobrers.

    fill_all s’ignora (compat): mai es creen blocs «extra» sense nom/quota.
    """
    del fill_all  # no omplir l’horari més enllà de la quota
    if not units or not venues:
        return 0
    created = 0
    for u in units:
        hours = u.minutes_needed / 60.0
        u.session_plan = split_session_minutes(hours) or [
            max(MIN_SESSION_MINUTES, u.minutes_needed)
        ]

    week = start - timedelta(days=start.weekday())
    while week <= end:
        for u in units:
            u.minutes_placed = 0
        max_sessions = max((len(u.session_plan) for u in units), default=0)
        for si in range(max_sessions):
            for unit in units:
                if si >= len(unit.session_plan):
                    continue
                dur = unit.session_plan[si]
                if unit.minutes_placed + dur > unit.minutes_needed + SLOT_STEP_MINUTES:
                    dur = max(
                        MIN_SESSION_MINUTES,
                        unit.minutes_needed - unit.minutes_placed,
                    )
                    dur = (dur // SLOT_STEP_MINUTES) * SLOT_STEP_MINUTES
                    if dur < MIN_SESSION_MINUTES:
                        continue
                placed = False
                for wd in _weekday_priority(si, len(unit.session_plan)):
                    for d in _dates_for_weekday(week, week + timedelta(days=6), wd):
                        if d < start or d > end:
                            continue
                        found = _find_free_slot(
                            d=d, duration_min=dur, venues=venues, occs=occs
                        )
                        if not found:
                            continue
                        venue, st, et = found
                        for tid in unit.team_ids:
                            if _place_training(
                                db,
                                season_id=season.id,
                                team_id=tid,
                                d=d,
                                st=st,
                                et=et,
                                venue_id=venue.id,
                                allows_share=len(unit.team_ids) > 1
                                or bool(venue.allows_share_default),
                                series_id=f"{series_prefix}u{unit.group_id or tid}"[:12],
                                group_id=unit.group_id,
                                occs=occs,
                                occupy=False,
                            ):
                                created += 1
                        occs.append(
                            Occupancy(d=d, venue_id=venue.id, start=st, end=et)
                        )
                        unit.minutes_placed += dur
                        placed = True
                        break
                    if placed:
                        break
        week += timedelta(days=7)
    return created


def generate_draft_plan(
    db: Session,
    *,
    season,
    start: date,
    end: date,
) -> DraftGenerateResult:
    """Genera borrador amb el puzle setmanal (3×1,5 h, compartit variable per dia)."""
    from app.training_puzzle import write_puzzle_drafts

    result = DraftGenerateResult()
    if end < start:
        result.warnings.append(DraftWarning("bad_range"))
        return result

    teams = (
        db.query(Team)
        .filter(Team.season_id == season.id)
        .order_by(Team.name)
        .all()
    )
    people_missing = 0
    for tm in teams:
        has = (
            db.query(TeamMembership.id)
            .filter(TeamMembership.team_id == tm.id)
            .first()
        )
        if not has:
            people_missing += 1
    if people_missing:
        result.warnings.append(
            DraftWarning("people_missing", {"n": people_missing})
        )

    puzzle = write_puzzle_drafts(db, season=season, start=start, end=end)
    # Combinar avisos (people_missing primer)
    result.created = puzzle.created
    result.discarded = puzzle.discarded
    result.batch_id = puzzle.batch_id
    result.warnings.extend(puzzle.warnings)
    return result


def time_from_input(raw: str | None) -> time | None:
    """Converteix una cadena HH:MM. Permet 24:00 -> 23:59."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s == "24:00":
        return time(23, 59)
    try:
        return time.fromisoformat(s)
    except ValueError:
        return None


def format_time_input(t: time | None) -> str:
    """Mostra 24:00 quan l'hora emmagatzemada és 23:59 (representa mitjanit)."""
    if not t:
        return ""
    if t.hour == 23 and t.minute == 59:
        return "24:00"
    return t.strftime("%H:%M")


def default_plan_range(today: date | None = None, weeks: int = 1) -> tuple[date, date]:
    """Proper dilluns + N setmanes."""
    today = today or date.today()
    # proper dilluns (si avui és dl, avui)
    days_ahead = (0 - today.weekday()) % 7
    start = today + timedelta(days=days_ahead)
    end = start + timedelta(days=7 * weeks - 1)
    return start, end


_PLAN_COLORS = (
    "#2a7a5c",
    "#1f5f8b",
    "#8b5a1f",
    "#6b3d7a",
    "#b33b3b",
    "#3d6b4f",
    "#4a5f8a",
    "#9a6b2e",
)


def draft_team_colors(drafts) -> dict[int, str]:
    """Color estable per equip (mateix a gràfica i llista)."""
    teams: dict[int, str] = {}
    for t in drafts:
        if t.team_id not in teams:
            name = t.team.name if t.team else ""
            teams[t.team_id] = name
    ordered = sorted(teams.keys(), key=lambda tid: (teams[tid].casefold(), tid))
    return {
        tid: _PLAN_COLORS[i % len(_PLAN_COLORS)] for i, tid in enumerate(ordered)
    }


@dataclass
class DraftWeekChart:
    """Gràfica setmanal multi-pista: dia → carrils (pista) → barres."""

    monday: date
    sunday: date
    iso_week: int
    iso_year: int
    prev_monday: date | None
    next_monday: date | None
    day_start_h: int
    day_end_h: int
    hour_marks: list[int]
    days: list[dict]  # date, weekday, lanes[{venue, avail, bars}]
    venues: list[dict]  # {id, name}
    rink_count: int
    team_colors: dict[int, str]
    source: str = "empty"  # draft|live|empty
    empty: bool = True


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def draft_week_bounds(sessions) -> tuple[date, date] | None:
    if not sessions:
        return None
    dates = [t.session_date for t in sessions]
    return monday_of(min(dates)), monday_of(max(dates))


def _pct_span(
    start_m: int, end_m: int, window_start: int, span: int
) -> tuple[float, float] | None:
    a = max(start_m, window_start)
    b = min(end_m, window_start + span)
    if b <= a:
        return None
    return round((a - window_start) / span * 100, 2), round((b - a) / span * 100, 2)


def _venue_avail_segments(
    venue: Venue | None, weekday: int, window_start: int, span: int
) -> list[dict]:
    """Franges d’hockey disponibles aquell dia (no hores «civils»)."""
    if venue is None:
        return []
    avails = [a for a in (venue.availabilities or []) if a.weekday == weekday]
    if not avails:
        return []
    out: list[dict] = []
    for a in sorted(avails, key=lambda x: _minutes(x.start_time)):
        pct = _pct_span(
            _minutes(a.start_time), _minutes(a.end_time), window_start, span
        )
        if pct:
            out.append({"left": pct[0], "width": pct[1]})
    return out


@dataclass
class TeamWeekSlot:
    weekday: int
    day_label: str
    time_label: str
    venue: str
    share_note: str | None = None
    group_label: str | None = None
    is_solape: bool = False


@dataclass
class TeamWeekRow:
    team_id: int
    team_name: str
    category: str
    color: str
    slots: list[TeamWeekSlot] = field(default_factory=list)


def _share_units_from_week(week_sessions: list) -> list[list[Team]]:
    """Unitats compartides úniques d’una setmana (per etiquetar amb categoria)."""
    clusters: dict[tuple, list] = {}
    for s in week_sessions:
        key = (
            getattr(s, "session_date", None),
            getattr(s, "venue_id", None),
            s.start_time,
            s.end_time,
        )
        clusters.setdefault(key, []).append(s)
    units: list[list[Team]] = []
    seen: set[frozenset[int]] = set()
    for peers in clusters.values():
        teams = [p.team for p in peers if p.team]
        ids = frozenset(t.id for t in teams)
        if len(ids) < 2 or ids in seen:
            continue
        seen.add(ids)
        by_id = {t.id: t for t in teams}
        units.append([by_id[i] for i in sorted(ids)])
    units.sort(key=lambda ts: (len(ts), sorted(t.id for t in ts)))
    return units


def build_team_week_list(
    sessions,
    *,
    teams: list[Team],
    monday: date,
    colors: dict[int, str] | None = None,
    weekday_names: list[str] | None = None,
) -> list[TeamWeekRow]:
    """Llistat per equip (una setmana): dies/hores; grups desglossats amb nota."""
    from app.i18n import weekdays as i18n_weekdays

    colors = colors or {}
    day_names = weekday_names or i18n_weekdays("ca")
    sunday = monday + timedelta(days=6)
    week = [
        s
        for s in sessions
        if monday <= getattr(s, "session_date", monday) <= sunday
    ]
    unit_labels = labels_by_team_ids(_share_units_from_week(week))
    by_team: dict[int, list] = {}
    for s in week:
        by_team.setdefault(s.team_id, []).append(s)

    def _slot_peers(s) -> list:
        return [
            x
            for x in week
            if x.team_id != s.team_id
            and x.session_date == s.session_date
            and x.start_time == s.start_time
            and x.end_time == s.end_time
            and getattr(x, "venue_id", None) == getattr(s, "venue_id", None)
        ]

    # Ordre d’equips de la temporada (amb sessions o amb hores)
    order = list(teams)
    seen = {t.id for t in order}
    for tid in by_team:
        if tid not in seen and by_team[tid]:
            t0 = by_team[tid][0].team
            if t0:
                order.append(t0)
                seen.add(tid)

    rows: list[TeamWeekRow] = []
    for team in order:
        slots_src = sorted(
            by_team.get(team.id, []),
            key=lambda x: (x.session_date, x.start_time),
        )
        if not slots_src:
            continue
        slots: list[TeamWeekSlot] = []
        for s in slots_src:
            peers = _slot_peers(s)
            g_obj = getattr(s, "training_group", None)
            g_label = (g_obj.label if g_obj and g_obj.label else None) or None
            if peers and not g_label:
                peer_teams = [p.team for p in peers if p.team]
                all_teams = ([s.team] if s.team else []) + peer_teams
                ids = frozenset(t.id for t in all_teams if t)
                g_label = unit_labels.get(ids) or group_label_for_teams(all_teams)
            partners = " + ".join(
                sorted(
                    {
                        _team_full_name(p.team)
                        for p in peers
                        if p.team
                    }
                )
            )
            share_note = None
            if partners:
                share_note = partners
            wd = s.session_date.weekday()
            day_name = day_names[wd] if 0 <= wd < len(day_names) else str(wd)
            slots.append(
                TeamWeekSlot(
                    weekday=wd,
                    day_label=f"{day_name} {s.session_date.strftime('%d/%m')}",
                    time_label=f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}",
                    venue=(s.venue.name if s.venue else ""),
                    share_note=share_note,
                    group_label=g_label if partners else None,
                    is_solape=bool(getattr(s, "training_solape_id", None)),
                )
            )
        rows.append(
            TeamWeekRow(
                team_id=team.id,
                team_name=(team.name or "?").strip() or "?",
                category=(team.category or "").strip(),
                color=colors.get(team.id, _PLAN_COLORS[0]),
                slots=slots,
            )
        )
    return rows


def _team_full_name(team) -> str:
    """Nom complet per al tooltip (no l’etiqueta curta de la barra)."""
    if not team:
        return "?"
    name = (team.name or "").strip() or "?"
    cat = (team.category or "").strip()
    if cat and cat.casefold() != name.casefold() and cat.casefold() not in name.casefold():
        return f"{name} ({cat})"
    return name


def _tip_day_label(session, weekday_names: list[str]) -> str:
    """Dia concret de l’entreno (p. ex. «dilluns 27/07»)."""
    d = getattr(session, "session_date", None)
    if not d:
        return ""
    wd = d.weekday()
    name = weekday_names[wd] if 0 <= wd < len(weekday_names) else str(wd)
    return f"{name} {d.strftime('%d/%m')}"


def _session_bars_for_rows(
    day_rows: list,
    *,
    colors: dict[int, str],
    window_start: int,
    span: int,
    unit_labels: dict[frozenset[int], str] | None = None,
    weekday_names: list[str] | None = None,
    tip_solape: str = "solape",
) -> list[dict]:
    """Fusiona grups/compartits; en solape apila A/B al tram d’overlap."""
    from app.i18n import weekdays as i18n_weekdays

    units: list[dict] = []
    seen_groups: set[int] = set()
    seen_slots: set[tuple] = set()
    unit_labels = unit_labels or {}
    day_names = weekday_names or i18n_weekdays("ca")

    def _add_unit(
        peers: list,
        *,
        is_group: bool,
        label: str | None = None,
        member_teams: list | None = None,
    ) -> None:
        if not peers:
            return
        st = min(x.start_time for x in peers)
        et = max(x.end_time for x in peers)
        teams = list(member_teams) if member_teams else [x.team for x in peers if x.team]
        seen_ids: set[int] = set()
        ordered: list = []
        for team in sorted(teams, key=lambda t: (t.name or "").casefold() if t else ""):
            if not team or team.id in seen_ids:
                continue
            seen_ids.add(team.id)
            ordered.append(team)
        members_s = " + ".join(_team_full_name(t) for t in ordered)
        show = label or members_s or "?"
        venue = peers[0].venue.name if peers[0].venue else ""
        day_s = _tip_day_label(peers[0], day_names)
        time_s = f"{st.strftime('%H:%M')}–{et.strftime('%H:%M')}"
        solape_id = next(
            (
                getattr(x, "training_solape_id", None)
                for x in peers
                if getattr(x, "training_solape_id", None)
            ),
            None,
        )
        title_bits: list[str] = []
        if label:
            title_bits.append(label)
        if members_s and members_s != label:
            title_bits.append(members_s)
        elif not label and members_s:
            title_bits.append(members_s)
        if day_s:
            title_bits.append(day_s)
        title_bits.append(time_s)
        if venue:
            title_bits.append(venue)
        if solape_id:
            title_bits.append(tip_solape)
        units.append(
            {
                "start_m": _minutes(st),
                "end_m": _minutes(et),
                "color": colors.get(peers[0].team_id, _PLAN_COLORS[0]),
                "team": show,
                "label": show,
                "time": time_s,
                "venue": venue,
                "is_group": is_group or len(peers) > 1,
                "is_solape": bool(solape_id),
                "solape_id": solape_id,
                "title": " · ".join(title_bits),
            }
        )

    for t in day_rows:
        gid = getattr(t, "training_group_id", None)
        if gid:
            if gid in seen_groups:
                continue
            seen_groups.add(gid)
            peers = [x for x in day_rows if x.training_group_id == gid]
            g_obj = getattr(peers[0], "training_group", None)
            peer_teams = [x.team for x in peers if x.team]
            group_teams = peer_teams
            if g_obj and getattr(g_obj, "members", None):
                group_teams = [m.team for m in g_obj.members if m.team] or peer_teams
            label = (
                (g_obj.label if g_obj and g_obj.label else None)
                or group_label_for_teams(group_teams)
                or f"Grup {gid}"
            )
            _add_unit(
                peers,
                is_group=True,
                label=label,
                member_teams=group_teams,
            )
            continue

        slot_key = (
            getattr(t, "venue_id", None),
            t.start_time,
            t.end_time,
        )
        if slot_key in seen_slots:
            continue
        peers = [
            x
            for x in day_rows
            if not getattr(x, "training_group_id", None)
            and getattr(x, "venue_id", None) == slot_key[0]
            and x.start_time == slot_key[1]
            and x.end_time == slot_key[2]
        ]
        if len(peers) > 1:
            seen_slots.add(slot_key)
            peer_teams = [x.team for x in peers if x.team]
            ids = frozenset(t.id for t in peer_teams)
            share_label = unit_labels.get(ids) or group_label_for_teams(peer_teams)
            _add_unit(
                peers,
                is_group=True,
                label=share_label,
                member_teams=peer_teams,
            )
            continue

        seen_slots.add(slot_key)
        full = _team_full_name(t.team)
        short = team_display_label(t.team) if t.team else "?"
        venue = t.venue.name if t.venue else ""
        day_s = _tip_day_label(t, day_names)
        time_s = f"{t.start_time.strftime('%H:%M')}–{t.end_time.strftime('%H:%M')}"
        solape_id = getattr(t, "training_solape_id", None)
        title = " · ".join(
            p
            for p in (full, day_s, time_s, venue, tip_solape if solape_id else "")
            if p
        )
        units.append(
            {
                "start_m": _minutes(t.start_time),
                "end_m": _minutes(t.end_time),
                "color": colors.get(t.team_id, _PLAN_COLORS[0]),
                "team": short,
                "label": full,
                "time": time_s,
                "venue": venue,
                "is_group": False,
                "is_solape": bool(solape_id),
                "solape_id": solape_id,
                "title": title,
            }
        )

    return _bars_with_solape_stack(units, window_start=window_start, span=span)


def _bars_with_solape_stack(
    units: list[dict],
    *,
    window_start: int,
    span: int,
) -> list[dict]:
    """Solape: barra sencera d’A a dalt i de B a baix (es solapen al tram comú)."""

    def _plain(u: dict, *, stack: str = "full") -> dict | None:
        pct = _pct_span(u["start_m"], u["end_m"], window_start, span)
        if not pct:
            return None
        return {
            "left": pct[0],
            "width": pct[1],
            "color": u["color"],
            "team": u["team"],
            "label": u["label"],
            "time": u["time"],
            "venue": u["venue"],
            "is_group": u["is_group"],
            "is_solape": u["is_solape"],
            "stack": stack,
            "title": u["title"],
        }

    # Parelles amb el mateix solape_id que es solapen en el temps
    stack_of: dict[int, str] = {}
    used: set[int] = set()
    for i, a in enumerate(units):
        if i in used or not a.get("solape_id"):
            continue
        for j in range(i + 1, len(units)):
            if j in used:
                continue
            b = units[j]
            if b.get("solape_id") != a["solape_id"]:
                continue
            if not (a["start_m"] < b["end_m"] and b["start_m"] < a["end_m"]):
                continue
            first_i, second_i = (i, j) if a["start_m"] <= b["start_m"] else (j, i)
            stack_of[first_i] = "top"
            stack_of[second_i] = "bottom"
            used.add(i)
            used.add(j)
            break

    bars: list[dict] = []
    for i, u in enumerate(units):
        bar = _plain(u, stack=stack_of.get(i, "full"))
        if bar:
            bars.append(bar)
    bars.sort(key=lambda b: (b["left"], 0 if b.get("stack") == "top" else 1))
    return bars


def build_draft_week_chart(
    sessions,
    *,
    venues: list[Venue] | None = None,
    focus_monday: date | None = None,
    day_start_h: int = 15,
    day_end_h: int = 22,
    team_colors: dict[int, str] | None = None,
    source: str = "draft",
    nav_first: date | None = None,
    nav_last: date | None = None,
    weekday_names: list[str] | None = None,
    tip_solape: str | None = None,
) -> DraftWeekChart:
    """Gràfica multi-pista: cada dia té un carril per pista (horari d’hockey)."""
    from app.i18n import translate, weekdays as i18n_weekdays

    day_names = weekday_names or i18n_weekdays("ca")
    solape_word = tip_solape or translate("ca", "tr_chart_tip_solape")
    bounds = draft_week_bounds(sessions)
    if bounds:
        first_mon, last_mon = bounds
    else:
        base = focus_monday or monday_of(date.today())
        first_mon = last_mon = monday_of(base)
    if nav_first is not None:
        first_mon = monday_of(nav_first)
    if nav_last is not None:
        last_mon = monday_of(nav_last)

    monday = monday_of(focus_monday) if focus_monday else first_mon
    if monday < first_mon:
        monday = first_mon
    if monday > last_mon:
        monday = last_mon

    sunday = monday + timedelta(days=6)
    window_start = day_start_h * 60
    window_end = day_end_h * 60

    week_sessions = [t for t in sessions if monday <= t.session_date <= sunday]
    unit_labels = labels_by_team_ids(_share_units_from_week(week_sessions))

    venue_list: list[Venue] = list(venues or [])
    # Incloure pistes que surten a les sessions però no a la llista
    seen_vids = {v.id for v in venue_list}
    for t in week_sessions:
        if t.venue and t.venue_id not in seen_vids:
            venue_list.append(t.venue)
            seen_vids.add(t.venue_id)
    if not venue_list:
        # Carril sintètic perquè la plantilla es vegi igual
        venue_list = []

    for t in week_sessions:
        window_start = min(window_start, _minutes(t.start_time))
        window_end = max(window_end, _minutes(t.end_time))
    for v in venue_list:
        for a in v.availabilities or []:
            if 0 <= a.weekday <= 6:
                window_start = min(window_start, _minutes(a.start_time))
                window_end = max(window_end, _minutes(a.end_time))

    day_start_h = max(0, window_start // 60)
    day_end_h = min(24, (window_end + 59) // 60)
    if day_end_h <= day_start_h:
        day_start_h, day_end_h = 15, 22
    window_start = day_start_h * 60
    window_end = day_end_h * 60
    span = max(window_end - window_start, 1)

    colors = team_colors if team_colors is not None else draft_team_colors(sessions)
    venues_meta = (
        [{"id": v.id, "name": v.name} for v in venue_list]
        if venue_list
        else [{"id": 0, "name": "—"}]
    )
    rink_count = max(1, len(venues_meta))

    days_out: list[dict] = []
    for i in range(7):
        d = monday + timedelta(days=i)
        day_rows = [t for t in week_sessions if t.session_date == d]
        lanes: list[dict] = []
        if venue_list:
            for v in venue_list:
                v_rows = [t for t in day_rows if t.venue_id == v.id]
                lanes.append(
                    {
                        "venue_id": v.id,
                        "venue": v.name,
                        "avail": _venue_avail_segments(v, i, window_start, span),
                        "bars": _session_bars_for_rows(
                            v_rows,
                            colors=colors,
                            window_start=window_start,
                            span=span,
                            unit_labels=unit_labels,
                            weekday_names=day_names,
                            tip_solape=solape_word,
                        ),
                    }
                )
        else:
            lanes.append(
                {
                    "venue_id": 0,
                    "venue": "—",
                    "avail": _venue_avail_segments(None, i, window_start, span),
                    "bars": _session_bars_for_rows(
                        day_rows,
                        colors=colors,
                        window_start=window_start,
                        span=span,
                        unit_labels=unit_labels,
                        weekday_names=day_names,
                        tip_solape=solape_word,
                    ),
                }
            )
        days_out.append({"date": d, "weekday": i, "lanes": lanes})

    prev_m = monday - timedelta(days=7)
    next_m = monday + timedelta(days=7)
    if not sessions:
        today_mon = monday_of(date.today())
        first_mon = today_mon - timedelta(days=28)
        last_mon = today_mon + timedelta(days=28)

    hour_marks = list(range(day_start_h, day_end_h + 1))
    src = source if sessions else "empty"

    return DraftWeekChart(
        monday=monday,
        sunday=sunday,
        iso_week=monday.isocalendar()[1],
        iso_year=monday.isocalendar()[0],
        prev_monday=prev_m if prev_m >= first_mon else None,
        next_monday=next_m if next_m <= last_mon else None,
        day_start_h=day_start_h,
        day_end_h=day_end_h,
        hour_marks=hour_marks,
        days=days_out,
        venues=venues_meta,
        rink_count=rink_count,
        team_colors=colors,
        source=src,
        empty=not bool(week_sessions),
    )
