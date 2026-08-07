"""Diagnòstic de capacitat i proposta (puzle setmanal → borrador)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session, joinedload

from app.db import Team, Venue
from app.training_groups import (
    clear_groups,
    estimate_capacity,
    load_groups,
    teams_in_groups,
)
from app.training_hours import effective_hours
from app.training_puzzle import puzzle_fits_solo, solve_week_puzzle, tile_week_holes
from app.training_solapes import (
    DEFAULT_SOLAPE_WEEKDAYS,
    SideKey,
    clear_solapes,
    create_solape,
    load_solapes,
    participant_options,
    _usage_maps,
)


@dataclass
class FitAdvice:
    demand_minutes: int
    supply_minutes: int
    team_count: int
    venue_count: int
    fits_solo: bool
    groups_count: int
    solapes_count: int
    deficit_minutes: int
    free_teams: int
    suggest_groups: int
    suggest_teams_grouped: int
    suggest_solapes: int
    needs_action: bool
    pack_sessions: int = 0
    pack_clean: int = 0
    pack_clashes: int = 0
    pack_unplaced: int = 0
    teams_in_groups_count: int = 0
    propose_units: int = 0
    hole_count: int = 0
    shared_slots_needed: int = 0


@dataclass
class ProposeFitResult:
    groups_created: int = 0
    solapes_created: int = 0
    teams_joined: int = 0
    group_labels: list[str] = field(default_factory=list)
    solape_labels: list[str] = field(default_factory=list)
    refreshed_only: bool = False
    puzzle_ok: bool = False
    solo_slots: int = 0
    shared_slots: int = 0


def _active_teams(db: Session, season) -> list[Team]:
    teams = (
        db.query(Team)
        .filter(Team.season_id == season.id)
        .order_by(Team.category.nulls_last(), Team.name)
        .all()
    )
    out: list[Team] = []
    for t in teams:
        h = effective_hours(t, season)
        if h and h > 0:
            out.append(t)
    return out


def _venues(db: Session, season) -> list[Venue]:
    return (
        db.query(Venue)
        .options(joinedload(Venue.availabilities))
        .filter(Venue.club_id == season.club_id)
        .order_by(Venue.name)
        .all()
    )


def build_fit_advice(db: Session, season) -> FitAdvice:
    base = estimate_capacity(db, season)
    solapes = load_solapes(db, season.id)
    groups = load_groups(db, season.id)
    taken = teams_in_groups(groups)
    free_n = max(0, base.team_count - len(taken))

    demand = base.demand_minutes
    supply = base.supply_minutes
    deficit = max(0, demand - supply) if base.venue_count else demand

    active = _active_teams(db, season)
    venues = _venues(db, season)
    holes = tile_week_holes(venues)
    fits_solo = puzzle_fits_solo(active, venues) if active and venues else False
    need_sessions = 3 * len(active)
    shared_needed = max(0, need_sessions - len(holes)) if holes else need_sessions

    return FitAdvice(
        demand_minutes=demand,
        supply_minutes=supply,
        team_count=base.team_count,
        venue_count=base.venue_count,
        fits_solo=fits_solo,
        groups_count=base.groups_count,
        solapes_count=len(solapes),
        deficit_minutes=deficit,
        free_teams=free_n,
        suggest_groups=shared_needed,  # huecos compartits mínims
        suggest_teams_grouped=min(base.team_count, shared_needed * 2),
        suggest_solapes=0,
        needs_action=not fits_solo,
        pack_sessions=need_sessions,
        pack_clean=max(0, need_sessions - shared_needed),
        pack_clashes=0,
        pack_unplaced=0,
        teams_in_groups_count=len(taken),
        propose_units=len(holes),
        hole_count=len(holes),
        shared_slots_needed=shared_needed,
    )


def _affinity_pairs(codes: list[str], labels: dict[str, str]) -> list[tuple[str, str]]:
    items = sorted(codes, key=lambda c: labels.get(c, c).casefold())
    pairs: list[tuple[str, str]] = []
    i = 0
    while i + 1 < len(items):
        pairs.append((items[i], items[i + 1]))
        i += 2
    return pairs


def propose_solapes(
    db: Session,
    season,
    *,
    max_solapes: int = 8,
    overlap_minutes: int = 30,
    weekdays: list[int] | None = None,
) -> list:
    if max_solapes <= 0:
        return []
    weekdays = weekdays or list(DEFAULT_SOLAPE_WEEKDAYS)
    club_name = season.club.name if season.club else None
    opts = participant_options(db, season.id, club_name)
    if len(opts) < 2:
        return []

    existing = load_solapes(db, season.id)
    as_a, _as_b = _usage_maps(existing)
    labels = {o["code"]: o["label"] for o in opts}
    free_codes: list[str] = []
    for o in opts:
        key = SideKey.parse(o["code"])
        if not key or key in as_a:
            continue
        free_codes.append(o["code"])

    created = []
    for code_a, code_b in _affinity_pairs(free_codes, labels):
        if len(created) >= max_solapes:
            break
        ka, kb = SideKey.parse(code_a), SideKey.parse(code_b)
        if not ka or not kb:
            continue
        row = create_solape(
            db,
            season_id=season.id,
            side_a=ka,
            side_b=kb,
            overlap_minutes=overlap_minutes,
            weekdays=weekdays,
        )
        if row:
            created.append(row)
            as_a[ka] = row.id
    return created


def propose_fit(db: Session, season, *, with_solapes: bool = False) -> ProposeFitResult:
    """Proposta = puzle setmanal al borrador (sense plantilles fixes de grup)."""
    result = ProposeFitResult()
    if with_solapes:
        want = 4
        solapes = propose_solapes(db, season, max_solapes=want)
        result.solapes_created = len(solapes)
        for s in solapes:
            result.solape_labels.append(s.label or f"Solape {s.id}")
        return result

    # Neteja plantilles antigues: el compartit ho decideix el puzle per dia
    clear_solapes(db, season.id)
    clear_groups(db, season.id)

    active = _active_teams(db, season)
    venues = _venues(db, season)
    solution = solve_week_puzzle(active, venues)
    result.puzzle_ok = not solution.impossible
    result.solo_slots = solution.solo_sessions
    result.shared_slots = solution.shared_slots
    if solution.impossible:
        return result

    result.refreshed_only = True
    result.teams_joined = (
        solution.shared_slots * 2 if solution.shared_slots else 0
    )
    return result
