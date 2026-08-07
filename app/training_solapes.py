"""Plantilles de solape / relevo (A→B, mateixa pista)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy.orm import Session, joinedload

from app.db import Team, Training, TrainingGroup, TrainingSolape
from app.training_groups import (
    DEFAULT_GROUP_WEEKDAYS,
    assign_unit_labels,
    ensure_unit_group,
    format_weekdays,
    load_groups,
    parse_weekdays,
    team_display_label,
    teams_in_groups,
)


OVERLAP_CHOICES = (0, 15, 30, 45, 60)
DEFAULT_SOLAPE_WEEKDAYS = list(DEFAULT_GROUP_WEEKDAYS)


@dataclass(frozen=True)
class SideKey:
    kind: str  # team | group | unit
    id: int
    team_ids: tuple[int, ...] = field(default_factory=tuple)

    def code(self) -> str:
        if self.kind == "unit":
            return "u:" + "-".join(str(i) for i in self.team_ids)
        return f"{self.kind[0]}:{self.id}"

    @staticmethod
    def parse(raw: str | None) -> SideKey | None:
        if not raw or ":" not in str(raw):
            return None
        kind_c, _, rest = str(raw).partition(":")
        if kind_c == "u":
            ids = tuple(
                sorted({int(x) for x in rest.split("-") if x.isdigit()})
            )
            if len(ids) < 2:
                return None
            return SideKey("unit", 0, ids)
        if kind_c not in ("t", "g") or not rest.isdigit():
            return None
        return SideKey("team" if kind_c == "t" else "group", int(rest))

@dataclass
class SolapeSide:
    key: SideKey
    team_ids: list[int]
    label: str
    group_id: int | None = None


@dataclass
class SolapeChain:
    """Cadena ordenada de costats amb solapes entre consecutius."""

    sides: list[SolapeSide]
    edges: list[TrainingSolape]  # len = len(sides) - 1
    weekdays: list[int]


def load_solapes(db: Session, season_id: int) -> list[TrainingSolape]:
    return (
        db.query(TrainingSolape)
        .options(
            joinedload(TrainingSolape.team_a),
            joinedload(TrainingSolape.team_b),
            joinedload(TrainingSolape.group_a).joinedload(TrainingGroup.members),
            joinedload(TrainingSolape.group_b).joinedload(TrainingGroup.members),
        )
        .filter(TrainingSolape.season_id == season_id)
        .order_by(TrainingSolape.id)
        .all()
    )


def side_key_from_solape_a(s: TrainingSolape) -> SideKey | None:
    if s.team_a_id:
        return SideKey("team", s.team_a_id)
    if s.group_a_id:
        return SideKey("group", s.group_a_id)
    return None


def side_key_from_solape_b(s: TrainingSolape) -> SideKey | None:
    if s.team_b_id:
        return SideKey("team", s.team_b_id)
    if s.group_b_id:
        return SideKey("group", s.group_b_id)
    return None


def resolve_side(
    db: Session,
    season_id: int,
    key: SideKey,
    *,
    club_name: str | None = None,
    groups: list[TrainingGroup] | None = None,
) -> SolapeSide | None:
    groups = groups if groups is not None else load_groups(db, season_id)
    if key.kind == "unit":
        g = ensure_unit_group(db, season_id, list(key.team_ids))
        if not g:
            return None
        key = SideKey("group", g.id)
        groups = load_groups(db, season_id)
    if key.kind == "team":
        team = db.get(Team, key.id)
        if not team or team.season_id != season_id:
            return None
        # Un equip pot ser unitat sola al puzle i també membre d’un grup
        # un altre dia: no bloquejar per plantilla de grup.
        return SolapeSide(
            key=key,
            team_ids=[team.id],
            label=team_display_label(team, club_name),
        )
    g = next((x for x in groups if x.id == key.id), None)
    if not g or g.season_id != season_id:
        return None
    tids = [m.team_id for m in sorted(g.members, key=lambda m: m.sort_order)]
    if len(tids) < 2:
        return None
    label = g.label or " + ".join(
        team_display_label(m.team, club_name) for m in g.members if m.team
    )
    return SolapeSide(
        key=SideKey("group", g.id),
        team_ids=tids,
        label=label[:120],
        group_id=g.id,
    )


def _materialize_key(db: Session, season_id: int, key: SideKey) -> SideKey | None:
    """Converteix unitats del puzle (u:…) en grups persistents per al solape."""
    if key.kind != "unit":
        return key
    g = ensure_unit_group(db, season_id, list(key.team_ids))
    if not g:
        return None
    return SideKey("group", g.id)


def _options_from_puzzle_week(
    sessions: list[Training],
    club_name: str | None = None,
) -> list[dict]:
    """Unitats del puzle: grups compartits + equips que entrenen sols."""
    from app.training_plan import monday_of

    if not sessions:
        return []
    monday = monday_of(min(s.session_date for s in sessions))
    sunday = monday + timedelta(days=6)
    week = [s for s in sessions if monday <= s.session_date <= sunday]
    if not week:
        week = sessions

    clusters: dict[tuple, list[Training]] = defaultdict(list)
    for s in week:
        clusters[
            (s.session_date, s.venue_id, s.start_time, s.end_time)
        ].append(s)

    solo_ids: set[int] = set()
    share_sets: dict[frozenset[int], list[Team]] = {}
    for peers in clusters.values():
        teams = [p.team for p in peers if p.team]
        ids = frozenset(t.id for t in teams)
        if len(ids) == 1:
            solo_ids.add(next(iter(ids)))
        elif len(ids) >= 2:
            by_id = {t.id: t for t in teams}
            share_sets[ids] = [by_id[i] for i in sorted(ids)]

    ordered_ids = sorted(share_sets.keys(), key=lambda s: (len(s), sorted(s)))
    units = [share_sets[ids] for ids in ordered_ids]
    unit_names = assign_unit_labels(units)
    out: list[dict] = []
    for ids, ordered, label in zip(ordered_ids, units, unit_names):
        members = " + ".join(
            team_display_label(t, club_name) for t in ordered
        )
        out.append(
            {
                "code": SideKey("unit", 0, tuple(sorted(ids))).code(),
                "label": f"{label} · {members}",
                "kind": "group",
            }
        )

    team_by_id = {
        s.team_id: s.team
        for s in week
        if s.team_id in solo_ids and s.team
    }
    for tid in sorted(solo_ids, key=lambda i: (team_by_id.get(i).name or "") if team_by_id.get(i) else ""):
        t = team_by_id.get(tid)
        if not t:
            continue
        out.append(
            {
                "code": SideKey("team", t.id).code(),
                "label": team_display_label(t, club_name),
                "kind": "team",
            }
        )
    return out


def participant_options(
    db: Session, season_id: int, club_name: str | None = None
) -> list[dict]:
    """Unitats del puzle (borrador) o, si no n’hi ha, grups + equips lliures."""
    drafts = (
        db.query(Training)
        .options(joinedload(Training.team), joinedload(Training.venue))
        .filter(
            Training.season_id == season_id,
            Training.is_draft.is_(True),
        )
        .order_by(Training.session_date, Training.start_time)
        .all()
    )
    if drafts:
        out = _options_from_puzzle_week(drafts, club_name)
        # Assegurar que els costats ja usats en solapes segueixen seleccionables
        seen = {o["code"] for o in out}
        for s in load_solapes(db, season_id):
            for key in (side_key_from_solape_a(s), side_key_from_solape_b(s)):
                if not key or key.code() in seen:
                    continue
                side = resolve_side(db, season_id, key, club_name=club_name)
                if not side:
                    continue
                out.append(
                    {
                        "code": key.code(),
                        "label": side.label,
                        "kind": key.kind,
                    }
                )
                seen.add(key.code())
        return out

    groups = load_groups(db, season_id)
    taken = teams_in_groups(groups)
    teams = (
        db.query(Team)
        .filter(Team.season_id == season_id)
        .order_by(Team.category.nulls_last(), Team.name)
        .all()
    )
    out = []
    for g in groups:
        label = g.label or " + ".join(
            team_display_label(m.team, club_name) for m in g.members if m.team
        )
        out.append(
            {
                "code": SideKey("group", g.id).code(),
                "label": f"{label} · "
                + " + ".join(
                    team_display_label(m.team, club_name)
                    for m in g.members
                    if m.team
                ),
                "kind": "group",
            }
        )
    for t in teams:
        if t.id in taken:
            continue
        out.append(
            {
                "code": SideKey("team", t.id).code(),
                "label": team_display_label(t, club_name),
                "kind": "team",
            }
        )
    return out


def _usage_maps(
    solapes: list[TrainingSolape], *, exclude_id: int | None = None
) -> tuple[dict[SideKey, int], dict[SideKey, int]]:
    as_a: dict[SideKey, int] = {}
    as_b: dict[SideKey, int] = {}
    for s in solapes:
        if exclude_id is not None and s.id == exclude_id:
            continue
        ka, kb = side_key_from_solape_a(s), side_key_from_solape_b(s)
        if ka:
            as_a[ka] = s.id
        if kb:
            as_b[kb] = s.id
    return as_a, as_b


def _normalize_overlap(minutes: int) -> int | None:
    if minutes in OVERLAP_CHOICES:
        return minutes
    return None


def create_solape(
    db: Session,
    *,
    season_id: int,
    side_a: SideKey,
    side_b: SideKey,
    overlap_minutes: int,
    weekdays: list[int],
    label: str | None = None,
) -> TrainingSolape | None:
    ov = _normalize_overlap(overlap_minutes)
    if ov is None or side_a == side_b:
        return None

    club_name = None
    from app.db import Season, Club

    season = db.get(Season, season_id)
    if season:
        club = db.get(Club, season.club_id)
        club_name = club.name if club else None

    side_a = _materialize_key(db, season_id, side_a)
    side_b = _materialize_key(db, season_id, side_b)
    if not side_a or not side_b:
        return None

    groups = load_groups(db, season_id)
    a = resolve_side(db, season_id, side_a, club_name=club_name, groups=groups)
    b = resolve_side(db, season_id, side_b, club_name=club_name, groups=groups)
    if not a or not b:
        return None

    existing = load_solapes(db, season_id)
    as_a, as_b = _usage_maps(existing)
    # Un participant: com a molt un cop com a A i un com a B (permet A→B→C)
    if side_a in as_a or side_b in as_b:
        return None
    # Evitar cicle directe B→A
    for s in existing:
        if side_key_from_solape_a(s) == side_b and side_key_from_solape_b(s) == side_a:
            return None

    auto_label = label or f"{a.label} → {b.label}"
    row = TrainingSolape(
        season_id=season_id,
        team_a_id=side_a.id if side_a.kind == "team" else None,
        group_a_id=side_a.id if side_a.kind == "group" else None,
        team_b_id=side_b.id if side_b.kind == "team" else None,
        group_b_id=side_b.id if side_b.kind == "group" else None,
        overlap_minutes=ov,
        weekdays=format_weekdays(weekdays or list(DEFAULT_SOLAPE_WEEKDAYS)),
        label=auto_label[:120],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_solape(
    db: Session,
    *,
    season_id: int,
    solape_id: int,
    side_a: SideKey,
    side_b: SideKey,
    overlap_minutes: int,
    weekdays: list[int],
) -> TrainingSolape | None:
    row = db.get(TrainingSolape, solape_id)
    if not row or row.season_id != season_id:
        return None
    ov = _normalize_overlap(overlap_minutes)
    if ov is None or side_a == side_b:
        return None

    from app.db import Season, Club

    season = db.get(Season, season_id)
    club_name = None
    if season:
        club = db.get(Club, season.club_id)
        club_name = club.name if club else None

    side_a = _materialize_key(db, season_id, side_a)
    side_b = _materialize_key(db, season_id, side_b)
    if not side_a or not side_b:
        return None

    groups = load_groups(db, season_id)
    a = resolve_side(db, season_id, side_a, club_name=club_name, groups=groups)
    b = resolve_side(db, season_id, side_b, club_name=club_name, groups=groups)
    if not a or not b:
        return None

    existing = load_solapes(db, season_id)
    as_a, as_b = _usage_maps(existing, exclude_id=solape_id)
    if side_a in as_a or side_b in as_b:
        return None
    for s in existing:
        if s.id == solape_id:
            continue
        if side_key_from_solape_a(s) == side_b and side_key_from_solape_b(s) == side_a:
            return None

    row.team_a_id = side_a.id if side_a.kind == "team" else None
    row.group_a_id = side_a.id if side_a.kind == "group" else None
    row.team_b_id = side_b.id if side_b.kind == "team" else None
    row.group_b_id = side_b.id if side_b.kind == "group" else None
    row.overlap_minutes = ov
    row.weekdays = format_weekdays(weekdays or list(DEFAULT_SOLAPE_WEEKDAYS))
    row.label = f"{a.label} → {b.label}"[:120]
    db.commit()
    db.refresh(row)
    return row


def delete_solape(db: Session, season_id: int, solape_id: int) -> bool:
    from app.db import Training

    row = db.get(TrainingSolape, solape_id)
    if not row or row.season_id != season_id:
        return False
    db.query(Training).filter(Training.training_solape_id == solape_id).update(
        {Training.training_solape_id: None}, synchronize_session=False
    )
    db.delete(row)
    db.commit()
    return True


def clear_solapes(db: Session, season_id: int) -> int:
    """Esborra totes les plantilles de solape de la temporada."""
    rows = load_solapes(db, season_id)
    n = 0
    for row in rows:
        if delete_solape(db, season_id, row.id):
            n += 1
    return n


def build_chains(
    db: Session,
    season_id: int,
    solapes: list[TrainingSolape] | None = None,
) -> list[SolapeChain]:
    """Construeix cadenes A→B→C a partir de les plantilles."""
    solapes = solapes if solapes is not None else load_solapes(db, season_id)
    if not solapes:
        return []

    from app.db import Season, Club

    season = db.get(Season, season_id)
    club_name = None
    if season:
        club = db.get(Club, season.club_id)
        club_name = club.name if club else None
    groups = load_groups(db, season_id)

    # edge: A → (B, solape)
    out_edge: dict[SideKey, tuple[SideKey, TrainingSolape]] = {}
    in_degree: dict[SideKey, int] = {}
    all_keys: set[SideKey] = set()
    for s in solapes:
        ka, kb = side_key_from_solape_a(s), side_key_from_solape_b(s)
        if not ka or not kb:
            continue
        out_edge[ka] = (kb, s)
        in_degree[kb] = in_degree.get(kb, 0) + 1
        in_degree.setdefault(ka, 0)
        all_keys.add(ka)
        all_keys.add(kb)

    starts = [k for k in all_keys if in_degree.get(k, 0) == 0]
    # Si hi ha cicle (sense start), agafar qualsevol no visitat
    if not starts and all_keys:
        starts = [next(iter(all_keys))]

    chains: list[SolapeChain] = []
    visited_edges: set[int] = set()

    def side_for(key: SideKey) -> SolapeSide | None:
        return resolve_side(db, season_id, key, club_name=club_name, groups=groups)

    for start in starts:
        sides: list[SolapeSide] = []
        edges: list[TrainingSolape] = []
        cur = start
        seen_nodes: set[SideKey] = set()
        while cur not in seen_nodes:
            seen_nodes.add(cur)
            side = side_for(cur)
            if not side:
                break
            sides.append(side)
            nxt = out_edge.get(cur)
            if not nxt:
                break
            kb, edge = nxt
            if edge.id in visited_edges:
                break
            visited_edges.add(edge.id)
            edges.append(edge)
            cur = kb
        # darrer node de la cadena (si hi ha edge)
        if edges:
            last_key = side_key_from_solape_b(edges[-1])
            if last_key and (not sides or sides[-1].key != last_key):
                last_side = side_for(last_key)
                if last_side:
                    sides.append(last_side)
        if len(sides) >= 2 and edges:
            # intersecció de weekdays
            wsets = [set(parse_weekdays(e.weekdays)) for e in edges]
            common = set.intersection(*wsets) if wsets else set()
            if not common:
                common = set(parse_weekdays(edges[0].weekdays))
            chains.append(
                SolapeChain(
                    sides=sides,
                    edges=edges,
                    weekdays=sorted(common),
                )
            )

    # Solapes aïllats no visitats (no haurien de passar amb starts correctes)
    for s in solapes:
        if s.id in visited_edges:
            continue
        ka, kb = side_key_from_solape_a(s), side_key_from_solape_b(s)
        if not ka or not kb:
            continue
        a, b = side_for(ka), side_for(kb)
        if not a or not b:
            continue
        chains.append(
            SolapeChain(
                sides=[a, b],
                edges=[s],
                weekdays=parse_weekdays(s.weekdays),
            )
        )
        visited_edges.add(s.id)

    return chains


def group_ids_in_solapes(solapes: list[TrainingSolape]) -> set[int]:
    out: set[int] = set()
    for s in solapes:
        if s.group_a_id:
            out.add(s.group_a_id)
        if s.group_b_id:
            out.add(s.group_b_id)
    return out


def solape_weekdays_for_group(
    solapes: list[TrainingSolape], group_id: int
) -> set[int]:
    days: set[int] = set()
    for s in solapes:
        if s.group_a_id == group_id or s.group_b_id == group_id:
            days.update(parse_weekdays(s.weekdays))
    return days


def solape_weekdays_for_team(
    solapes: list[TrainingSolape],
    team_id: int,
    *,
    group_id: int | None = None,
) -> set[int]:
    """Dies on l’equip participa en un solape (directe o via grup)."""
    days: set[int] = set()
    for s in solapes:
        if s.team_a_id == team_id or s.team_b_id == team_id:
            days.update(parse_weekdays(s.weekdays))
        elif group_id and (
            s.group_a_id == group_id or s.group_b_id == group_id
        ):
            days.update(parse_weekdays(s.weekdays))
    return days


def solape_display(s: TrainingSolape, club_name: str | None = None) -> dict:
    def _lab_team(t: Team | None) -> str:
        return team_display_label(t, club_name) if t else "?"

    def _lab_group(g: TrainingGroup | None) -> str:
        if not g:
            return "?"
        return g.label or " + ".join(
            team_display_label(m.team, club_name) for m in g.members if m.team
        )

    a = _lab_team(s.team_a) if s.team_a_id else _lab_group(s.group_a)
    b = _lab_team(s.team_b) if s.team_b_id else _lab_group(s.group_b)
    return {
        "id": s.id,
        "label": s.label or f"{a} → {b}",
        "side_a": a,
        "side_b": b,
        "overlap_minutes": s.overlap_minutes,
        "weekdays": parse_weekdays(s.weekdays),
        "code_a": SideKey(
            "team" if s.team_a_id else "group",
            s.team_a_id or s.group_a_id or 0,
        ).code(),
        "code_b": SideKey(
            "team" if s.team_b_id else "group",
            s.team_b_id or s.group_b_id or 0,
        ).code(),
    }
