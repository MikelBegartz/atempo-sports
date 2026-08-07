"""Solapes probables entre equipos (mismo día / fin de semana) y horizonte temporal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session, joinedload

from app.conflicts import Conflict
from app.db import Match, TeamMembership, Training


HORIZON_ORDER = ("m1", "m2", "later", "undated")


@dataclass
class TeamOverlap:
    """Dos partidos de equipos distintos el mismo día o fin de semana."""

    match_a: Match
    match_b: Match
    day: date
    same_day: bool
    shared_people: list[str] = field(default_factory=list)
    reinforce_people: list[str] = field(default_factory=list)

    @property
    def severity(self) -> str:
        if self.shared_people or self.reinforce_people:
            return "hard"
        return "soft"

    @property
    def kind(self) -> str:
        if self.reinforce_people:
            return "reinforce"
        if self.shared_people:
            return "shared"
        return "probable"


def _weekend_key(d: date) -> date:
    """Domingo del finde (vie–dom) que contiene d; otros días → ellos mismos."""
    wd = d.weekday()
    if wd >= 4:
        return d + timedelta(days=(6 - wd))
    return d


def _people_by_team(db: Session, team_ids: list[int]) -> dict[int, list[tuple[int, str, str]]]:
    """team_id → [(person_id, full_name, role), ...]"""
    rows = (
        db.query(TeamMembership)
        .options(joinedload(TeamMembership.person))
        .filter(TeamMembership.team_id.in_(team_ids))
        .all()
    )
    out: dict[int, list[tuple[int, str, str]]] = {tid: [] for tid in team_ids}
    for r in rows:
        out.setdefault(r.team_id, []).append(
            (r.person_id, r.person.full_name, r.role)
        )
    return out


def find_team_overlaps(
    db: Session,
    season_id: int,
    team_ids: list[int],
) -> list[TeamOverlap]:
    ids = sorted({int(x) for x in team_ids if x})
    if len(ids) < 2:
        return []

    matches = (
        db.query(Match)
        .options(joinedload(Match.team), joinedload(Match.venue))
        .filter(
            Match.season_id == season_id,
            Match.team_id.in_(ids),
            Match.match_date.isnot(None),
        )
        .order_by(Match.match_date, Match.start_time.nulls_last())
        .all()
    )
    people = _people_by_team(db, ids)

    # Index by day and by weekend
    by_day: dict[date, list[Match]] = {}
    by_weekend: dict[date, list[Match]] = {}
    for m in matches:
        assert m.match_date
        by_day.setdefault(m.match_date, []).append(m)
        by_weekend.setdefault(_weekend_key(m.match_date), []).append(m)

    seen: set[tuple[int, int]] = set()
    out: list[TeamOverlap] = []

    def _pair(a: Match, b: Match, same_day: bool) -> None:
        if a.team_id == b.team_id:
            return
        key = (min(a.id, b.id), max(a.id, b.id))
        if key in seen:
            return
        # Only pairs where both teams are in the selection
        if a.team_id not in ids or b.team_id not in ids:
            return
        seen.add(key)

        pa = {pid: (name, role) for pid, name, role in people.get(a.team_id, [])}
        pb = {pid: (name, role) for pid, name, role in people.get(b.team_id, [])}
        shared: list[str] = []
        reinforce: list[str] = []
        for pid, (name, ra) in pa.items():
            if pid not in pb:
                continue
            rb = pb[pid][1]
            if ra == "reinforce" or rb == "reinforce":
                reinforce.append(name)
            else:
                shared.append(name)

        day = a.match_date if a.match_date <= (b.match_date or a.match_date) else b.match_date
        out.append(
            TeamOverlap(
                match_a=a,
                match_b=b,
                day=day or date.today(),
                same_day=same_day,
                shared_people=sorted(set(shared)),
                reinforce_people=sorted(set(reinforce)),
            )
        )

    for day, group in by_day.items():
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                _pair(a, b, same_day=True)

    for _wk, group in by_weekend.items():
        # Solo sáb–dom: partidos del mismo fin de semana en días distintos
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                if a.match_date == b.match_date:
                    continue
                # Ambos en finde (vie/sáb/dom) — típico jornada
                if a.match_date and b.match_date:
                    if a.match_date.weekday() >= 4 and b.match_date.weekday() >= 4:
                        _pair(a, b, same_day=False)

    out.sort(key=lambda o: (o.day, o.severity != "hard", o.match_a.id))
    return out


def conflict_event_date(
    conflict: Conflict,
    matches_by_id: dict[int, Match],
    trainings_by_id: dict[int, Training],
) -> date | None:
    dates: list[date] = []
    for mid in conflict.match_ids:
        m = matches_by_id.get(mid)
        if m and m.match_date:
            dates.append(m.match_date)
    for tid in conflict.training_ids:
        t = trainings_by_id.get(tid)
        if t and t.session_date:
            dates.append(t.session_date)
    return min(dates) if dates else None


def horizon_bucket(event_date: date | None, today: date | None = None) -> str | None:
    today = today or date.today()
    if event_date is None:
        return "undated"
    delta = (event_date - today).days
    if delta < 0:
        return None  # ya pasado → se ignora
    if delta <= 30:
        return "m1"
    if delta <= 60:
        return "m2"
    return "later"


def group_conflicts_by_horizon(
    conflicts: list[Conflict],
    matches: list[Match],
    trainings: list[Training] | None = None,
    today: date | None = None,
) -> dict[str, list[Conflict]]:
    by_id = {m.id: m for m in matches}
    tby_id = {t.id: t for t in (trainings or [])}
    groups = {k: [] for k in HORIZON_ORDER}
    for c in conflicts:
        bucket = horizon_bucket(conflict_event_date(c, by_id, tby_id), today)
        if bucket is None:
            continue
        groups[bucket].append(c)
    return groups


def group_overlaps_by_horizon(
    overlaps: list[TeamOverlap],
    today: date | None = None,
) -> dict[str, list[TeamOverlap]]:
    groups = {k: [] for k in HORIZON_ORDER}
    for o in overlaps:
        bucket = horizon_bucket(o.day, today)
        if bucket is None:
            continue
        groups[bucket].append(o)
    return groups
