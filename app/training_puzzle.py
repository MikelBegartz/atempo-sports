"""Puzle setmanal d’entrenaments: omplir franges de pista amb 3×1,5 h per equip.

La unitat que es repeteix és la setmana. El dilluns poden compartir A+B i el
dimarts C+D: el compartit pot canviar cada dia, però el patró setmanal és estable.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date, time, timedelta

from sqlalchemy.orm import Session, joinedload

from app.db import Team, Training, Venue
from app.training_hours import effective_hours
from app.training_plan import (
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    DraftGenerateResult,
    DraftWarning,
    Occupancy,
    SLOT_STEP_MINUTES,
    _busy_at,
    _find_span_slot,
    _load_base_occupancy,
    _load_manual_draft_occupancy,
    _minutes,
    _place_training,
    _time_from_minutes,
    discard_drafts,
)
from app.training_groups import load_groups, parse_weekdays
from app.training_solapes import build_chains


SESSION_MINUTES = 90
SESSIONS_PER_TEAM = 3
MAX_TEAMS_PER_SLOT = 2


@dataclass(frozen=True)
class SlotHole:
    """Huec de 90′ a la plantilla setmanal (pista + dia + hora)."""

    weekday: int
    venue_id: int
    start: time
    end: time


@dataclass
class SeatAssignment:
    """Una sessió d’un equip en un huec (índex a la llista de holes)."""

    team_id: int
    hole_index: int


@dataclass
class PuzzleSolution:
    holes: list[SlotHole]
    seats: list[SeatAssignment]
    solo_sessions: int
    shared_slots: int
    impossible: bool = False
    message: str = ""


def _category_key(team: Team) -> str:
    import re

    cat = (team.category or "").strip().casefold()
    return re.sub(r"\s+[ab]$", "", cat) or cat or (team.name or "").casefold()


def _is_a_line(team: Team) -> bool:
    import re

    blob = f"{team.name} {team.category or ''}".casefold()
    return bool(re.search(r"\ba\b", blob)) or blob.rstrip().endswith(" a")


def _affinity(a: Team, b: Team) -> tuple:
    """Menor = més afí (mateixa categoria, línies A juntes)."""
    same_cat = 0 if _category_key(a) == _category_key(b) else 1
    both_a = 0 if (_is_a_line(a) and _is_a_line(b)) else 1
    return (same_cat, both_a, a.name or "", b.name or "")


def _consecutive_triple(days: tuple[int, ...]) -> bool:
    s = tuple(sorted(days))
    if len(s) != 3:
        return False
    return s[2] == s[0] + 2 and s[1] == s[0] + 1


def preferred_day_patterns() -> list[tuple[int, int, int]]:
    """Totes les ternes dl–dv amb dia de descans entre sessions (no 3 dies seguits)."""
    out: list[tuple[int, int, int]] = []
    for combo in itertools.combinations(range(5), 3):
        if _consecutive_triple(combo):
            continue
        out.append(tuple(sorted(combo)))
    # Preferir L-X-V i patrons amb més separació
    def score(p: tuple[int, int, int]) -> tuple:
        span = p[2] - p[0]
        mid_gap = min(p[1] - p[0], p[2] - p[1])
        classic = 0 if p == (0, 2, 4) else 1
        return (classic, -span, -mid_gap, p)

    out.sort(key=score)
    return out


def _venue_windows(venue: Venue, weekday: int) -> list[tuple[time, time]]:
    avails = [a for a in (venue.availabilities or []) if a.weekday == weekday]
    if not avails:
        if 0 <= weekday <= 4:
            return [(DEFAULT_WINDOW_START, DEFAULT_WINDOW_END)]
        return []
    out: list[tuple[time, time]] = []
    for a in avails:
        if _minutes(a.end_time) - _minutes(a.start_time) >= SESSION_MINUTES:
            out.append((a.start_time, a.end_time))
    return out


def tile_week_holes(venues: list[Venue]) -> list[SlotHole]:
    """Particiona la disponibilitat dl–dv en huecs de 90′ (esquerra → dreta)."""
    holes: list[SlotHole] = []
    for venue in venues:
        for wd in range(5):
            for win_start, win_end in _venue_windows(venue, wd):
                cursor = _minutes(win_start)
                end_m = _minutes(win_end)
                while cursor + SESSION_MINUTES <= end_m:
                    holes.append(
                        SlotHole(
                            weekday=wd,
                            venue_id=venue.id,
                            start=_time_from_minutes(cursor),
                            end=_time_from_minutes(cursor + SESSION_MINUTES),
                        )
                    )
                    cursor += SESSION_MINUTES
                # residu < 90′: huec petit acceptable (ex. 15–30′)
    holes.sort(key=lambda h: (h.weekday, h.start, h.venue_id))
    return holes


def _hole_free_for_solo(occupancy: list[list[int]], hi: int) -> bool:
    return len(occupancy[hi]) == 0


def _can_sit(occupancy: list[list[int]], hi: int) -> bool:
    return len(occupancy[hi]) < MAX_TEAMS_PER_SLOT


def _try_assign_solo(
    teams: list[Team], holes: list[SlotHole]
) -> list[SeatAssignment] | None:
    """Intenta 3 sessions individuals per equip (dies distints, patró amb descans)."""
    if 3 * len(teams) > len(holes):
        return None
    occupancy: list[list[int]] = [[] for _ in holes]
    by_day: dict[int, list[int]] = {d: [] for d in range(5)}
    for i, h in enumerate(holes):
        by_day[h.weekday].append(i)
    patterns = preferred_day_patterns()
    seats: list[SeatAssignment] = []

    ordered = sorted(
        teams, key=lambda t: (_category_key(t), 0 if _is_a_line(t) else 1, t.name or "")
    )
    for team in ordered:
        placed = False
        for pattern in patterns:
            picks: list[int] = []
            ok = True
            for wd in pattern:
                found = None
                for hi in by_day[wd]:
                    if _hole_free_for_solo(occupancy, hi):
                        found = hi
                        break
                if found is None:
                    ok = False
                    break
                picks.append(found)
            if not ok:
                continue
            for hi in picks:
                occupancy[hi].append(team.id)
                seats.append(SeatAssignment(team_id=team.id, hole_index=hi))
            placed = True
            break
        if not placed:
            return None
    return seats


def _pair_partners(teams: list[Team]) -> list[tuple[Team, Team]]:
    """Emparella per afinitat (categoria / línia A)."""
    remaining = sorted(
        teams, key=lambda t: (_category_key(t), 0 if _is_a_line(t) else 1, t.name or "")
    )
    pairs: list[tuple[Team, Team]] = []
    used: set[int] = set()
    for i, a in enumerate(remaining):
        if a.id in used:
            continue
        best = None
        best_key = None
        for b in remaining[i + 1 :]:
            if b.id in used:
                continue
            key = _affinity(a, b)
            if best_key is None or key < best_key:
                best_key = key
                best = b
        if best:
            pairs.append((a, best))
            used.add(a.id)
            used.add(best.id)
    return pairs


def _try_assign_with_shares(
    teams: list[Team], holes: list[SlotHole]
) -> list[SeatAssignment] | None:
    """Omple tots els huecos; el mínim de dobles perquè 3N sessions càpiguen.

    Compartit per dia: dos equips al mateix huec; un altre dia poden anar sols
    o amb una altra parella.
    """
    n = len(teams)
    h = len(holes)
    need = SESSIONS_PER_TEAM * n
    if need > h * MAX_TEAMS_PER_SLOT:
        return None

    # Seients: cal need; amb h huecos → dobles = max(0, need - h)
    doubles_needed = max(0, need - h)
    # Marcar els primers `doubles_needed` huecos de cada dia de forma repartida
    double_flags = [False] * h
    if doubles_needed:
        # Repartir dobles entre dies per no saturar un sol dia
        by_day: dict[int, list[int]] = {d: [] for d in range(5)}
        for i, hole in enumerate(holes):
            by_day[hole.weekday].append(i)
        marked = 0
        day_cycle = itertools.cycle(range(5))
        cursors = {d: 0 for d in range(5)}
        guard = 0
        while marked < doubles_needed and guard < h * 3:
            guard += 1
            d = next(day_cycle)
            idx = cursors[d]
            day_holes = by_day[d]
            if idx >= len(day_holes):
                continue
            hi = day_holes[idx]
            cursors[d] = idx + 1
            if not double_flags[hi]:
                double_flags[hi] = True
                marked += 1

    occupancy: list[list[int]] = [[] for _ in holes]
    seats: list[SeatAssignment] = []
    # Quota de sessions per equip
    remaining = {t.id: SESSIONS_PER_TEAM for t in teams}
    team_days: dict[int, set[int]] = {t.id: set() for t in teams}
    by_id = {t.id: t for t in teams}

    # 1) Omplir huecos dobles amb parelles afins (una sessió compartida)
    pairs = _pair_partners(teams)
    pair_i = 0
    for hi, is_double in enumerate(double_flags):
        if not is_double:
            continue
        # Buscar parella amb sessions i dies lliures aquest dia
        wd = holes[hi].weekday
        placed_pair = False
        for _ in range(len(pairs)):
            if pair_i >= len(pairs):
                pair_i = 0
            a, b = pairs[pair_i]
            pair_i += 1
            if remaining[a.id] <= 0 or remaining[b.id] <= 0:
                continue
            if wd in team_days[a.id] or wd in team_days[b.id]:
                continue
            occupancy[hi] = [a.id, b.id]
            seats.append(SeatAssignment(team_id=a.id, hole_index=hi))
            seats.append(SeatAssignment(team_id=b.id, hole_index=hi))
            remaining[a.id] -= 1
            remaining[b.id] -= 1
            team_days[a.id].add(wd)
            team_days[b.id].add(wd)
            placed_pair = True
            break
        if not placed_pair:
            # Doble sense parella perfecta: deixar per a fase 2
            pass

    # 2) Sessions restants en solitari (huecos buits o seient lliure en dobles)
    patterns = preferred_day_patterns()
    ordered = sorted(
        teams,
        key=lambda t: (-remaining[t.id], _category_key(t), t.name or ""),
    )
    for team in ordered:
        while remaining[team.id] > 0:
            placed = False
            for pattern in patterns:
                for wd in pattern:
                    if wd in team_days[team.id]:
                        continue
                    # Preferir huec buit (sol); si no, seient lliure en doble
                    candidates = [
                        i
                        for i, hole in enumerate(holes)
                        if hole.weekday == wd and _can_sit(occupancy, i)
                    ]
                    candidates.sort(
                        key=lambda i: (len(occupancy[i]) > 0, holes[i].start)
                    )
                    for hi in candidates:
                        if len(occupancy[hi]) == 0 or (
                            len(occupancy[hi]) == 1 and double_flags[hi]
                        ):
                            # En huecos no marcats doble només 1 equip
                            if len(occupancy[hi]) == 1 and not double_flags[hi]:
                                continue
                            occupancy[hi].append(team.id)
                            seats.append(
                                SeatAssignment(team_id=team.id, hole_index=hi)
                            )
                            remaining[team.id] -= 1
                            team_days[team.id].add(wd)
                            placed = True
                            break
                    if placed:
                        break
                if placed:
                    break
            if not placed:
                # Qualsevol dia / huec viable
                for wd in range(5):
                    if wd in team_days[team.id]:
                        continue
                    for hi, hole in enumerate(holes):
                        if hole.weekday != wd or not _can_sit(occupancy, hi):
                            continue
                        if len(occupancy[hi]) >= 1 and not double_flags[hi]:
                            # Permetre doble improvisat si encara cal
                            if remaining[team.id] > 0 and len(occupancy[hi]) < 2:
                                pass
                            else:
                                continue
                        occupancy[hi].append(team.id)
                        seats.append(SeatAssignment(team_id=team.id, hole_index=hi))
                        remaining[team.id] -= 1
                        team_days[team.id].add(wd)
                        placed = True
                        break
                    if placed:
                        break
            if not placed:
                return None

    # 3) Si hi ha huecos buits i més dobles dels mínims, moure un equip
    #    d’un compartit a un buit (mateix nombre de sessions, menys shares).
    def _shared_count() -> int:
        return sum(1 for o in occupancy if len(o) >= 2)

    for _ in range(h):
        if _shared_count() <= doubles_needed:
            break
        empty = [i for i, o in enumerate(occupancy) if not o]
        if not empty:
            break
        moved = False
        for hi, occ in enumerate(occupancy):
            if len(occ) < 2:
                continue
            for tid in list(occ):
                cur_wd = holes[hi].weekday
                for ei in empty:
                    new_wd = holes[ei].weekday
                    if new_wd == cur_wd or new_wd in team_days[tid]:
                        continue
                    # Moure tid: hi → ei
                    occ.remove(tid)
                    occupancy[ei].append(tid)
                    team_days[tid].discard(cur_wd)
                    team_days[tid].add(new_wd)
                    for s in seats:
                        if s.team_id == tid and s.hole_index == hi:
                            s.hole_index = ei
                            break
                    moved = True
                    break
                if moved:
                    break
            if moved:
                break
        if not moved:
            break

    if any(v > 0 for v in remaining.values()):
        return None
    return seats


def solve_week_puzzle(teams: list[Team], venues: list[Venue]) -> PuzzleSolution:
    holes = tile_week_holes(venues)
    if not venues:
        return PuzzleSolution(
            holes=[], seats=[], solo_sessions=0, shared_slots=0,
            impossible=True, message="no_venues",
        )
    if not teams:
        return PuzzleSolution(
            holes=holes, seats=[], solo_sessions=0, shared_slots=0,
            impossible=True, message="no_teams",
        )
    need = SESSIONS_PER_TEAM * len(teams)
    if not holes:
        return PuzzleSolution(
            holes=[], seats=[], solo_sessions=0, shared_slots=0,
            impossible=True, message="no_holes",
        )
    if need > len(holes) * MAX_TEAMS_PER_SLOT:
        return PuzzleSolution(
            holes=holes, seats=[], solo_sessions=0, shared_slots=0,
            impossible=True, message="capacity",
        )

    seats = _try_assign_solo(teams, holes)
    if seats is None:
        seats = _try_assign_with_shares(teams, holes)
    if seats is None:
        return PuzzleSolution(
            holes=holes, seats=[], solo_sessions=0, shared_slots=0,
            impossible=True, message="unsat",
        )

    # Estadístiques
    occ: dict[int, list[int]] = {}
    for s in seats:
        occ.setdefault(s.hole_index, []).append(s.team_id)
    shared = sum(1 for v in occ.values() if len(v) >= 2)
    solo = sum(1 for v in occ.values() if len(v) == 1)
    return PuzzleSolution(
        holes=holes,
        seats=seats,
        solo_sessions=solo,
        shared_slots=shared,
        impossible=False,
    )


def puzzle_fits_solo(teams: list[Team], venues: list[Venue]) -> bool:
    holes = tile_week_holes(venues)
    if 3 * len(teams) > len(holes):
        return False
    return _try_assign_solo(teams, holes) is not None


def write_puzzle_drafts(
    db: Session,
    *,
    season,
    start: date,
    end: date,
) -> DraftGenerateResult:
    """Genera borrador a partir del puzle setmanal (esborra drafts automàtics)."""
    import uuid

    result = DraftGenerateResult()
    if end < start:
        result.warnings.append(DraftWarning("bad_range"))
        return result

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
        .order_by(Team.category.nulls_last(), Team.name)
        .all()
    )
    # Només equips amb hores (>0); l’exemple assumeix 4,5 h → 3×90′
    active: list[Team] = []
    for t in teams:
        h = effective_hours(t, season)
        if h and h > 0:
            active.append(t)
        else:
            result.warnings.append(DraftWarning("no_hours", {"team": t.name}))

    result.discarded = discard_drafts(db, season.id, only_auto=True)
    if not venues:
        result.warnings.append(DraftWarning("no_venues"))
        db.commit()
        return result
    if not active:
        result.warnings.append(DraftWarning("no_teams"))
        db.commit()
        return result

    solution = solve_week_puzzle(active, venues)
    if solution.impossible:
        result.warnings.append(
            DraftWarning(
                "puzzle_impossible",
                {"reason": solution.message or "unsat"},
            )
        )
        db.commit()
        return result

    batch_id = uuid.uuid4().hex[:10]
    result.batch_id = batch_id
    series_prefix = f"d{batch_id[:4]}"
    occs = _load_base_occupancy(db, season.id, start, end)
    occs.extend(_load_manual_draft_occupancy(db, season.id, start, end))

    # Per cada setmana del rang, materialitzar la plantilla
    week = start - timedelta(days=start.weekday())
    while week <= end:
        for seat in solution.seats:
            hole = solution.holes[seat.hole_index]
            d = week + timedelta(days=hole.weekday)
            if d < start or d > end:
                continue
            # Respectar ocupació de partits: si xoca, avís i salta
            if _busy_at(occs, d, hole.venue_id, hole.start, hole.end):
                result.warnings.append(
                    DraftWarning(
                        "unplaced",
                        {
                            "team": str(seat.team_id),
                            "date": d.isoformat(),
                            "mins": SESSION_MINUTES,
                        },
                    )
                )
                continue
            peers = [
                s.team_id
                for s in solution.seats
                if s.hole_index == seat.hole_index
            ]
            share = len(peers) > 1
            if _place_training(
                db,
                season_id=season.id,
                team_id=seat.team_id,
                d=d,
                st=hole.start,
                et=hole.end,
                venue_id=hole.venue_id,
                allows_share=share,
                series_id=f"{series_prefix}t{seat.team_id}"[:12],
                group_id=None,
                occs=occs,
                occupy=False,
            ):
                result.created += 1
        # Ocupar huecos de la plantilla a occs (un cop per huec)
        seen_holes: set[int] = set()
        for seat in solution.seats:
            if seat.hole_index in seen_holes:
                continue
            seen_holes.add(seat.hole_index)
            hole = solution.holes[seat.hole_index]
            d = week + timedelta(days=hole.weekday)
            if d < start or d > end:
                continue
            if not _busy_at(occs, d, hole.venue_id, hole.start, hole.end):
                occs.append(
                    Occupancy(
                        d=d,
                        venue_id=hole.venue_id,
                        start=hole.start,
                        end=hole.end,
                    )
                )
        week += timedelta(days=7)

    # Fallback: per a cada equip, completar sessions no col·locades pel puzle.
    # Màxim 1 sessió per dia i equip; es prioritzen patrons amb descans entre dies.
    team_days: dict[int, set[date]] = {}
    for t in active:
        hours = effective_hours(t, season)
        if hours:
            sessions_needed = max(1, int((hours * 60) / SESSION_MINUTES))
        else:
            sessions_needed = SESSIONS_PER_TEAM
        existing = (
            db.query(Training)
            .filter(
                Training.season_id == season.id,
                Training.team_id == t.id,
                Training.is_draft.is_(True),
                Training.session_date >= start,
                Training.session_date <= end,
            )
            .all()
        )
        sessions_placed = len(existing)
        team_days[t.id] = {tr.session_date for tr in existing}
        week = start - timedelta(days=start.weekday())
        while sessions_placed < sessions_needed and week <= end:
            placed = False
            # Preferir L, X, V; després M, J; finalment D, S.
            for w in (0, 2, 4, 1, 3, 6, 5):
                d = week + timedelta(days=w)
                if d < start or d > end:
                    continue
                if d in team_days[t.id]:
                    continue
                win_start = t.not_before or DEFAULT_WINDOW_START
                win_end = t.not_after or DEFAULT_WINDOW_END
                slot = _find_span_slot(
                    d=d,
                    span_min=SESSION_MINUTES,
                    venues=venues,
                    win_start=win_start,
                    win_end=win_end,
                    occs=occs,
                    only_venue_id=t.only_venue_id,
                )
                if slot:
                    v, st, et = slot
                    if _place_training(
                        db,
                        season_id=season.id,
                        team_id=t.id,
                        d=d,
                        st=st,
                        et=et,
                        venue_id=v.id,
                        allows_share=False,
                        series_id=f"solo{t.id}"[:12],
                        group_id=None,
                        occs=occs,
                        occupy=True,
                    ):
                        team_days[t.id].add(d)
                        result.created += 1
                        sessions_placed += 1
                        placed = True
                    if sessions_placed >= sessions_needed:
                        break
            if not placed:
                result.warnings.append(
                    DraftWarning(
                        "unplaced",
                        {"team": t.name, "date": week.isoformat(), "mins": SESSION_MINUTES},
                    )
                )
                break
            week += timedelta(days=7)

    if solution.shared_slots:
        result.warnings.append(
            DraftWarning(
                "puzzle_shares",
                {
                    "shared": solution.shared_slots,
                    "solo": solution.solo_sessions,
                },
            )
        )
    result.warnings.append(
        DraftWarning(
            "puzzle_ok",
            {
                "holes": len(solution.holes),
                "solo": solution.solo_sessions,
                "shared": solution.shared_slots,
            },
        )
    )

    db.flush()  # cal veure les sessions acabades de crear abans de reordenar
    n_groups = _apply_groups_to_puzzle_draft(
        db,
        season=season,
        start=start,
        end=end,
        result=result,
    )
    if n_groups:
        result.warnings.append(
            DraftWarning("using_groups", {"n": n_groups})
        )
    n_solape = _apply_solapes_to_puzzle_draft(
        db,
        season=season,
        start=start,
        end=end,
        venues=venues,
        result=result,
    )
    if n_solape:
        result.warnings.append(
            DraftWarning("using_solapes", {"n": n_solape})
        )

    db.commit()
    return result


def _apply_groups_to_puzzle_draft(
    db: Session,
    *,
    season,
    start: date,
    end: date,
    result: DraftGenerateResult,
) -> int:
    """Alinea al borrador els equips de cada grup a la mateixa franja els dies de plantilla."""
    groups = load_groups(db, season.id)
    if not groups:
        return 0

    drafts = (
        db.query(Training)
        .filter(
            Training.season_id == season.id,
            Training.is_draft.is_(True),
            Training.is_manual.is_(False),
            Training.session_date >= start,
            Training.session_date <= end,
        )
        .all()
    )
    if not drafts:
        return 0

    applied_days = 0
    week = start - timedelta(days=start.weekday())
    while week <= end:
        for group in groups:
            wds = parse_weekdays(group.weekdays)
            protect = set(wds)
            for wd in wds:
                d = week + timedelta(days=wd)
                if d < start or d > end:
                    continue
                if _relayout_group_day(
                    group=group,
                    d=d,
                    week_monday=week,
                    drafts=drafts,
                    protect_weekdays=protect - {wd},
                    result=result,
                ):
                    applied_days += 1
        week += timedelta(days=7)
    return applied_days


def _relayout_group_day(
    *,
    group,
    d: date,
    week_monday: date,
    drafts: list[Training],
    protect_weekdays: set[int],
    result: DraftGenerateResult,
) -> bool:
    """Posa tots els membres del grup a la mateixa franja el dia d.

    Només actua si algú del grup ja entrenava aquell dia (no inventa dimarts buits).
    """
    member_ids = [
        m.team_id
        for m in sorted(group.members, key=lambda x: (x.sort_order, x.team_id))
        if m.team_id
    ]
    if len(member_ids) < 2:
        return False

    already: list[Training] = []
    missing: list[int] = []
    for tid in member_ids:
        on_day = [
            t for t in drafts if t.team_id == tid and t.session_date == d
        ]
        if on_day:
            already.append(on_day[0])
        else:
            missing.append(tid)
    if not already:
        return False

    rows = list(already)
    for tid in missing:
        row = _move_team_session_to_day(
            team_id=tid,
            d=d,
            week_monday=week_monday,
            drafts=drafts,
            protect_weekdays=protect_weekdays,
            allow_move=True,
        )
        if not row:
            result.warnings.append(
                DraftWarning(
                    "group_incomplete",
                    {
                        "date": d.isoformat(),
                        "group": group.label or str(group.id),
                    },
                )
            )
            return False
        rows.append(row)

    anchor = min(rows, key=lambda t: (_minutes(t.start_time), t.team_id or 0))
    for t in rows:
        t.start_time = anchor.start_time
        t.end_time = anchor.end_time
        t.venue_id = anchor.venue_id
        t.allows_share = True
        t.training_group_id = group.id
    return True


def _apply_solapes_to_puzzle_draft(
    db: Session,
    *,
    season,
    start: date,
    end: date,
    venues: list[Venue],
    result: DraftGenerateResult,
) -> int:
    """Reordena sessions del puzle en cascada A→B amb overlap i marca solape_id."""
    chains = build_chains(db, season.id)
    if not chains:
        return 0

    drafts = (
        db.query(Training)
        .filter(
            Training.season_id == season.id,
            Training.is_draft.is_(True),
            Training.is_manual.is_(False),
            Training.session_date >= start,
            Training.session_date <= end,
        )
        .all()
    )
    if not drafts:
        return 0

    applied_days = 0
    week = start - timedelta(days=start.weekday())
    while week <= end:
        for chain in chains:
            for wd in chain.weekdays:
                d = week + timedelta(days=wd)
                if d < start or d > end:
                    continue
                if _relayout_solape_day(
                    db,
                    chain=chain,
                    d=d,
                    drafts=drafts,
                    venues=venues,
                    result=result,
                ):
                    applied_days += 1
        week += timedelta(days=7)
    return applied_days


@dataclass
class _RowSnap:
    row: Training
    session_date: date
    start_time: time
    end_time: time
    venue_id: int | None
    allows_share: bool
    training_solape_id: int | None
    training_group_id: int | None


def _snap_rows(rows: list[Training]) -> list[_RowSnap]:
    return [
        _RowSnap(
            row=r,
            session_date=r.session_date,
            start_time=r.start_time,
            end_time=r.end_time,
            venue_id=r.venue_id,
            allows_share=bool(r.allows_share),
            training_solape_id=r.training_solape_id,
            training_group_id=r.training_group_id,
        )
        for r in rows
    ]


def _restore_snaps(snaps: list[_RowSnap]) -> None:
    for s in snaps:
        s.row.session_date = s.session_date
        s.row.start_time = s.start_time
        s.row.end_time = s.end_time
        s.row.venue_id = s.venue_id
        s.row.allows_share = s.allows_share
        s.row.training_solape_id = s.training_solape_id
        s.row.training_group_id = s.training_group_id


def _times_overlap(a0: time, a1: time, b0: time, b1: time) -> bool:
    return _minutes(a0) < _minutes(b1) and _minutes(b0) < _minutes(a1)


def _slot_inside_avail(venue: Venue, weekday: int, st: time, et: time) -> bool:
    st_m, et_m = _minutes(st), _minutes(et)
    for vs, ve in _venue_windows(venue, weekday):
        if _minutes(vs) <= st_m and et_m <= _minutes(ve):
            return True
    return False


def _find_cascade_start_m(
    venue: Venue,
    weekday: int,
    span_min: int,
    prefer_start_m: int,
) -> int | None:
    """Primer minut d’una franja contínua dins avail que cap el span de cascada."""
    candidates: list[int] = []
    for vs, ve in _venue_windows(venue, weekday):
        cursor = _minutes(vs)
        end_limit = _minutes(ve)
        while cursor + span_min <= end_limit:
            candidates.append(cursor)
            cursor += SLOT_STEP_MINUTES
    if not candidates:
        return None
    return min(candidates, key=lambda c: (abs(c - prefer_start_m), c))


def _find_free_session_slot(
    venue: Venue,
    weekday: int,
    duration: int,
    *,
    hard_blocked: list[tuple[int, int]],
    occupants: list[tuple[int, int]],
    max_occupants: int = MAX_TEAMS_PER_SLOT,
) -> tuple[time, time] | None:
    """Busca un huec dins avail: buit o compartible (< max_occupants)."""
    for vs, ve in _venue_windows(venue, weekday):
        cursor = _minutes(vs)
        end_limit = _minutes(ve)
        while cursor + duration <= end_limit:
            st_m, et_m = cursor, cursor + duration
            if any(st_m < be and bs < et_m for bs, be in hard_blocked):
                cursor += SLOT_STEP_MINUTES
                continue
            occ = sum(1 for bs, be in occupants if st_m < be and bs < et_m)
            if occ < max_occupants:
                return _time_from_minutes(st_m), _time_from_minutes(et_m)
            cursor += SLOT_STEP_MINUTES
    return None


def _move_team_session_to_day(
    *,
    team_id: int,
    d: date,
    week_monday: date,
    drafts: list[Training],
    protect_weekdays: set[int],
    allow_move: bool = True,
) -> Training | None:
    """Assegura una sessió de l’equip el dia d (opcionalment mou una altra de la setmana)."""
    week_end = week_monday + timedelta(days=6)
    week_rows = [
        t
        for t in drafts
        if t.team_id == team_id and week_monday <= t.session_date <= week_end
    ]
    on_day = [t for t in week_rows if t.session_date == d]
    if on_day:
        return on_day[0]
    if not allow_move:
        return None
    # Preferir moure un dia que no sigui un altre dia de plantilla protegida
    candidates = [
        t
        for t in week_rows
        if t.session_date != d and t.session_date.weekday() not in protect_weekdays
    ]
    if not candidates:
        candidates = [t for t in week_rows if t.session_date != d]
    if not candidates:
        return None
    move = sorted(candidates, key=lambda t: t.session_date, reverse=True)[0]
    move.session_date = d
    return move


def _relayout_solape_day(
    db: Session,
    *,
    chain,
    d: date,
    drafts: list[Training],
    venues: list[Venue],
    result: DraftGenerateResult,
) -> bool:
    """Mou les unitats A→B del dia a franges consecutives amb solape, dins avail."""
    week_monday = d - timedelta(days=d.weekday())
    protect = set(chain.weekdays) - {d.weekday()}
    chain_label = " → ".join(s.label for s in chain.sides)

    # Snapshot de totes les sessions de la setmana dels equips de la cadena
    chain_team_ids: set[int] = set()
    for side in chain.sides:
        chain_team_ids.update(side.team_ids)
    week_end = week_monday + timedelta(days=6)
    chain_week_rows = [
        t
        for t in drafts
        if t.team_id in chain_team_ids and week_monday <= t.session_date <= week_end
    ]
    snaps = _snap_rows(chain_week_rows)

    side_rows: list[list[Training]] = []
    for side in chain.sides:
        rows: list[Training] = []
        for tid in set(side.team_ids):
            row = _move_team_session_to_day(
                team_id=tid,
                d=d,
                week_monday=week_monday,
                drafts=drafts,
                protect_weekdays=protect,
                # No inventar dies: només solapar on ja entrenen
                allow_move=False,
            )
            if not row:
                _restore_snaps(snaps)
                result.warnings.append(
                    DraftWarning(
                        "solape_incomplete",
                        {
                            "date": d.isoformat(),
                            "side": side.label,
                        },
                    )
                )
                return False
            rows.append(row)
        side_rows.append(rows)

    durations = []
    for rows in side_rows:
        dur = max(
            SESSION_MINUTES,
            _minutes(rows[0].end_time) - _minutes(rows[0].start_time),
        )
        durations.append(dur)
    overlaps = [e.overlap_minutes for e in chain.edges]
    span = sum(durations) - sum(overlaps)
    if span < SESSION_MINUTES:
        _restore_snaps(snaps)
        return False

    a_rows = side_rows[0]
    venue_id = a_rows[0].venue_id or (venues[0].id if venues else None)
    if not venue_id:
        _restore_snaps(snaps)
        return False
    venue = next((v for v in venues if v.id == venue_id), None)
    if not venue:
        _restore_snaps(snaps)
        return False

    prefer_start_m = min(_minutes(r.start_time) for r in a_rows)
    cascade_start_m = _find_cascade_start_m(
        venue, d.weekday(), span, prefer_start_m
    )
    if cascade_start_m is None:
        _restore_snaps(snaps)
        result.warnings.append(
            DraftWarning(
                "solape_unplaced",
                {"label": chain_label, "date": d.isoformat()},
            )
        )
        return False

    side_starts = [cascade_start_m]
    for i in range(1, len(durations)):
        prev_end = side_starts[i - 1] + durations[i - 1]
        side_starts.append(prev_end - overlaps[i - 1])

    targets: list[tuple[time, time]] = []
    for i, dur in enumerate(durations):
        st = _time_from_minutes(side_starts[i])
        et = _time_from_minutes(side_starts[i] + dur)
        targets.append((st, et))

    cascade_st = targets[0][0]
    cascade_et = max(t[1] for t in targets)
    cascade_st_m = _minutes(cascade_st)
    cascade_et_m = _minutes(cascade_et)

    # Franges originals de la cadena (abans de la cascada) reutilitzables dins avail
    chain_today = {r for rows in side_rows for r in rows}
    free_slots: list[tuple[time, time, int]] = []
    for s in snaps:
        if s.row not in chain_today or s.venue_id != venue_id:
            continue
        if not _slot_inside_avail(venue, d.weekday(), s.start_time, s.end_time):
            continue
        if _times_overlap(s.start_time, s.end_time, cascade_st, cascade_et):
            continue
        free_slots.append((s.start_time, s.end_time, s.venue_id))

    day_rows = [t for t in drafts if t.session_date == d]
    displaced = [
        t
        for t in day_rows
        if t.team_id not in chain_team_ids
        and t.venue_id == venue_id
        and _times_overlap(t.start_time, t.end_time, cascade_st, cascade_et)
    ]
    displaced_ids = {t.id for t in displaced}

    # Cascada = bloqueig dur; la resta pot compartir fins a MAX_TEAMS_PER_SLOT
    hard_blocked: list[tuple[int, int]] = [(cascade_st_m, cascade_et_m)]
    occupants: list[tuple[int, int]] = []
    for t in day_rows:
        if t.id in displaced_ids or t.team_id in chain_team_ids:
            continue
        if t.venue_id != venue_id:
            continue
        occupants.append((_minutes(t.start_time), _minutes(t.end_time)))

    for t in displaced:
        dur = max(
            SESSION_MINUTES,
            _minutes(t.end_time) - _minutes(t.start_time),
        )
        placed = False
        while free_slots:
            st, et, vid = free_slots.pop(0)
            st_m, et_m = _minutes(st), _minutes(et)
            if et_m - st_m < dur:
                continue
            if any(st_m < be and bs < et_m for bs, be in hard_blocked):
                continue
            occ = sum(1 for bs, be in occupants if st_m < be and bs < et_m)
            if occ >= MAX_TEAMS_PER_SLOT:
                continue
            et = _time_from_minutes(st_m + dur)
            if not _slot_inside_avail(venue, d.weekday(), st, et):
                continue
            t.start_time = st
            t.end_time = et
            t.venue_id = vid
            t.allows_share = True
            occupants.append((st_m, st_m + dur))
            placed = True
            break
        if placed:
            continue
        found = _find_free_session_slot(
            venue,
            d.weekday(),
            dur,
            hard_blocked=hard_blocked,
            occupants=occupants,
        )
        if found:
            st, et = found
            t.start_time = st
            t.end_time = et
            t.venue_id = venue_id
            t.allows_share = True
            occupants.append((_minutes(st), _minutes(et)))
            continue
        team_name = t.team.name if getattr(t, "team", None) else str(t.team_id)
        result.warnings.append(
            DraftWarning(
                "solape_displace",
                {"team": team_name, "date": d.isoformat()},
            )
        )
        # Deixar horari original (sense empènyer fora d’avail)

    for i, (side, rows) in enumerate(zip(chain.sides, side_rows)):
        st, et = targets[i]
        solape_id = chain.edges[0].id if i == 0 else chain.edges[i - 1].id
        for t in rows:
            t.start_time = st
            t.end_time = et
            t.venue_id = venue_id
            t.allows_share = True
            t.training_solape_id = solape_id
            if side.group_id:
                t.training_group_id = side.group_id
    return True
