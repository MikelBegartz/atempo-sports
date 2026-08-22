"""Plantilles de grup d’entrenament (unitat / temporada estable)."""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from datetime import date, time, timedelta

from sqlalchemy.orm import Session, joinedload

from app.db import (
    Team,
    Training,
    TrainingGroup,
    TrainingGroupMember,
    Venue,
    VenueAvailability,
)
from app.training_hours import effective_hours


OVERLAP_CHOICES = (15, 30, 45, 60)  # reservat per a solapes (feature a part)
MODES = ("shared",)  # grup = unitat; solape ≠ grup
# Dies per defecte del puzle (3 sessions): dl / dx / dv
DEFAULT_GROUP_WEEKDAYS = (0, 2, 4)
MAX_GROUP_SIZE = 12
MIN_GROUP_SIZE = 2


def preferred_weekdays_from_drafts(db: Session, season_id: int) -> list[int]:
    """Dies on ja hi ha sessions al borrador; si no n’hi ha, dl/dx/dv."""
    rows = (
        db.query(Training.session_date)
        .filter(
            Training.season_id == season_id,
            Training.is_draft.is_(True),
        )
        .limit(400)
        .all()
    )
    days = sorted({r.session_date.weekday() for r in rows if r.session_date})
    return days if days else list(DEFAULT_GROUP_WEEKDAYS)


def parse_weekdays(raw: str | None) -> list[int]:
    if not raw or not str(raw).strip():
        return list(DEFAULT_GROUP_WEEKDAYS)
    out: list[int] = []
    for part in str(raw).replace(" ", "").split(","):
        if not part:
            continue
        try:
            w = int(part)
        except ValueError:
            continue
        if 0 <= w <= 6 and w not in out:
            out.append(w)
    return out or list(DEFAULT_GROUP_WEEKDAYS)


def format_weekdays(days: list[int]) -> str:
    return ",".join(str(d) for d in sorted(set(days)))


def load_groups(db: Session, season_id: int) -> list[TrainingGroup]:
    return (
        db.query(TrainingGroup)
        .options(
            joinedload(TrainingGroup.members).joinedload(TrainingGroupMember.team),
            joinedload(TrainingGroup.venue),
        )
        .filter(TrainingGroup.season_id == season_id)
        .order_by(TrainingGroup.id)
        .all()
    )


def teams_in_groups(groups: list[TrainingGroup]) -> set[int]:
    return {m.team_id for g in groups for m in g.members}


@dataclass
class CapacityReport:
    demand_minutes: int
    supply_minutes: int
    team_count: int
    venue_count: int
    fits_solo: bool
    groups_count: int


def _minutes(t) -> int:
    return t.hour * 60 + t.minute


def estimate_capacity(db: Session, season) -> CapacityReport:
    teams = db.query(Team).filter(Team.season_id == season.id).all()
    venues = (
        db.query(Venue)
        .options(joinedload(Venue.availabilities))
        .filter(Venue.club_id == season.club_id)
        .all()
    )
    demand = 0
    for tm in teams:
        h = effective_hours(tm, season)
        if h:
            demand += int(round(h * 60))

    supply = 0
    for v in venues:
        avails = [a for a in v.availabilities if 0 <= a.weekday <= 4]
        if avails:
            for a in avails:
                supply += max(0, _minutes(a.end_time) - _minutes(a.start_time))
        else:
            # 16:00–21:00 × 5 dies laborables
            supply += 5 * 5 * 60

    groups = load_groups(db, season.id)
    return CapacityReport(
        demand_minutes=demand,
        supply_minutes=supply,
        team_count=len(teams),
        venue_count=len(venues),
        fits_solo=demand <= supply if venues else False,
        groups_count=len(groups),
    )


def team_display_label(team: Team, club_name: str | None = None) -> str:
    """Etiqueta útil: nom · categoria (liga) per distingir equips amb el mateix nom."""
    cat = (team.category or "").strip()
    name = (team.name or "").strip()
    club = (club_name or "").strip()

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).casefold()

    club_aliases = set()
    if club:
        club_aliases = {
            _norm(club),
            _norm(club.replace("CH ", "").replace("CH", "")),
        }

    if cat:
        m = re.search(r"\b([AB])\b", name, re.I)
        if m and not re.search(rf"\b{m.group(1)}\b", cat, re.I):
            return f"{cat} {m.group(1).upper()}"
        if name and _norm(name) != _norm(cat):
            # Nom del club / federatiu: la categoria (lliga) és el distintiu
            if club and _norm(name) in club_aliases:
                return cat
            return f"{name} · {cat}"
        return cat

    if club and _norm(name) in club_aliases:
        return name or "?"
    return name or "?"


def _letter_suffix(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA…"""
    if index < 0:
        index = 0
    chars: list[str] = []
    n = index
    while True:
        chars.append(chr(ord("A") + (n % 26)))
        n = n // 26 - 1
        if n < 0:
            break
    return "".join(reversed(chars))


def group_letter_label(index: int) -> str:
    """Fallback mixt: 0 → Grup A…"""
    return f"Grup {_letter_suffix(index)}"


def category_display_name(team: Team) -> str:
    """Nom de categoria sense línia A/B (p. ex. «Aleví A» → «Aleví»)."""
    cat = (team.category or "").strip()
    if not cat:
        cat = (team.name or "").strip()
    cleaned = re.sub(r"\s+[ABab]$", "", cat).strip()
    return cleaned or cat or "?"


def group_label_for_teams(
    teams: list[Team],
    *,
    disambiguator: str | None = None,
) -> str:
    """Nom significatiu: categoria; si cal desambiguar, categoria + lletra.

    Mai posa noms d’equips al nom del grup. Mixt → «Grup A».
    """
    if not teams:
        return f"Grup {disambiguator}" if disambiguator else "Grup"
    keys = {_category_key(t) for t in teams}
    if len(keys) == 1:
        stem = category_display_name(teams[0])
        if disambiguator:
            return f"{stem} {disambiguator}"[:120]
        return stem[:120]
    return f"Grup {disambiguator or 'A'}"


def assign_unit_labels(units: list[list[Team]]) -> list[str]:
    """Etiqueta un conjunt d’unitats: categoria sola si és única; si no, + A/B…"""
    from collections import Counter, defaultdict

    keys: list[str | None] = []
    for teams in units:
        if teams and len({_category_key(t) for t in teams}) == 1:
            keys.append(_category_key(teams[0]))
        else:
            keys.append(None)
    counts = Counter(k for k in keys if k is not None)
    seen: dict[str, int] = defaultdict(int)
    mixed_i = 0
    out: list[str] = []
    for teams, key in zip(units, keys):
        if key is None:
            out.append(group_letter_label(mixed_i))
            mixed_i += 1
            continue
        stem = category_display_name(teams[0])
        if counts[key] == 1:
            out.append(stem[:120])
        else:
            letter = _letter_suffix(seen[key])
            seen[key] += 1
            out.append(f"{stem} {letter}"[:120])
    return out


def labels_by_team_ids(units: list[list[Team]]) -> dict[frozenset[int], str]:
    """Mapa frozenset(team_ids) → etiqueta (mateixa regla que assign_unit_labels)."""
    labels = assign_unit_labels(units)
    out: dict[frozenset[int], str] = {}
    for teams, lab in zip(units, labels):
        out[frozenset(t.id for t in teams if t)] = lab
    return out


def group_label_from_teams(teams: list[Team], club_name: str | None = None) -> str:
    """Llista d’equips (tooltips / detalls)."""
    labels = [team_display_label(t, club_name) for t in teams]
    if len(labels) != len(set(labels)):
        labels = [(t.name or team_display_label(t, club_name)).strip() or "?" for t in teams]
    return " + ".join(labels)[:120]


def refresh_group_labels(db: Session, season_id: int) -> int:
    """Reanomena amb categoria (sola o + lletra si n’hi ha més d’un)."""
    groups = load_groups(db, season_id)
    units = [[m.team for m in g.members if m.team] for g in groups]
    labels = assign_unit_labels(units)
    n = 0
    for g, new_label in zip(groups, labels):
        if g.label != new_label:
            g.label = new_label
            n += 1
    if n:
        db.commit()
    return n


def _category_key(team: Team) -> str:
    cat = (team.category or "").strip().casefold()
    return re.sub(r"\s+[ab]$", "", cat) or cat


def _is_a_line(team: Team) -> bool:
    blob = f"{team.name} {team.category or ''}".casefold()
    return bool(re.search(r"\ba\b", blob)) or blob.rstrip().endswith(" a")


def clear_groups(db: Session, season_id: int) -> int:
    """Esborra totes les plantilles de grup de la temporada (no drafte sessions)."""
    from app.db import Training

    groups = load_groups(db, season_id)
    if not groups:
        return 0
    ids = [g.id for g in groups]
    db.query(Training).filter(Training.training_group_id.in_(ids)).update(
        {Training.training_group_id: None}, synchronize_session=False
    )
    n = 0
    for g in groups:
        db.delete(g)
        n += 1
    db.commit()
    return n


def _even_partition(n_items: int, n_buckets: int) -> list[int]:
    """Mides de cubells el més equilibrades possible."""
    if n_buckets <= 0 or n_items <= 0:
        return []
    n_buckets = min(n_buckets, n_items)
    base, rem = divmod(n_items, n_buckets)
    return [base + (1 if i < rem else 0) for i in range(n_buckets)]


def propose_capacity_groups(
    db: Session,
    season,
    *,
    weekdays: list[int] | None = None,
) -> list[TrainingGroup]:
    """Mínim de grups per encabir la demanda a l’oferta (plantilla dl–dv).

    max_unitats = floor(oferta / hores_mitjana). Reparteix els equips en
    unitats equilibrades (mida 2..MAX). Esborra les plantilles prèvies.
    """
    weekdays = weekdays or list(DEFAULT_GROUP_WEEKDAYS)
    clear_groups(db, season.id)

    teams = (
        db.query(Team)
        .filter(Team.season_id == season.id)
        .order_by(Team.category.nulls_last(), Team.name)
        .all()
    )
    active: list[Team] = []
    hours_list: list[float] = []
    for t in teams:
        h = effective_hours(t, season)
        if h and h > 0:
            active.append(t)
            hours_list.append(float(h))
    if len(active) < 2:
        return []

    cap = estimate_capacity(db, season)
    if not cap.supply_minutes or not hours_list:
        return []
    avg_min = int(round(sum(hours_list) / len(hours_list) * 60))
    avg_min = max(45, (avg_min // 15) * 15)
    # Màxim d’unitats que caben a l’oferta (= maximitzar equips sols / grups petits)
    max_units = max(1, min(len(active), cap.supply_minutes // avg_min))
    # Mínim d’unitats perquè cap grup superi MAX_GROUP_SIZE
    min_units = max(1, math.ceil(len(active) / MAX_GROUP_SIZE))
    n_groups = max(max_units, min_units)

    # Si ja caben en solitari (una unitat per equip), no calen grups
    if cap.demand_minutes <= cap.supply_minutes and max_units >= len(active):
        return []
    if len(active) <= n_groups:
        return []

    sizes = _even_partition(len(active), n_groups)
    while any(s == 1 for s in sizes) and len(sizes) >= 2:
        i = next(j for j, s in enumerate(sizes) if s == 1)
        sizes.pop(i)
        j = min(range(len(sizes)), key=lambda k: sizes[k])
        sizes[j] += 1

    # Afinitat futura: categoria / nivell, després línia A amb A
    active_sorted = sorted(
        active,
        key=lambda t: (_category_key(t), 0 if _is_a_line(t) else 1, t.name or ""),
    )
    created: list[TrainingGroup] = []
    idx = 0
    letter_i = 0
    for size in sizes:
        chunk = active_sorted[idx : idx + size]
        idx += size
        if len(chunk) < MIN_GROUP_SIZE:
            continue
        g = _insert_group(
            db,
            season.id,
            chunk,
            weekdays,
            label=group_label_for_teams(chunk, disambiguator=_letter_suffix(letter_i)),
        )
        if g:
            created.append(g)
            letter_i += 1
    db.commit()
    refresh_group_labels(db, season.id)
    for g in created:
        db.refresh(g)
    return created


def _insert_group(
    db: Session,
    season_id: int,
    teams: list[Team],
    weekdays: list[int],
    *,
    label: str,
) -> TrainingGroup | None:
    if len(teams) < MIN_GROUP_SIZE:
        return None
    g = TrainingGroup(
        season_id=season_id,
        mode="shared",
        overlap_minutes=0,
        weekdays=format_weekdays(weekdays),
        label=(label or group_label_for_teams(teams))[:120],
    )
    db.add(g)
    db.flush()
    for i, t in enumerate(teams):
        db.add(TrainingGroupMember(group_id=g.id, team_id=t.id, sort_order=i))
    return g


def ensure_unit_group(
    db: Session,
    season_id: int,
    team_ids: list[int],
    *,
    weekdays: list[int] | None = None,
) -> TrainingGroup | None:
    """Troba o crea un grup amb exactament aquests equips (unitat del puzle / solape).

    Permet solapar membres amb altres grups: al puzle un equip pot compartir
    amb parelles diferents segons el dia.
    """
    want = frozenset(int(x) for x in team_ids)
    if len(want) < MIN_GROUP_SIZE:
        return None
    for g in load_groups(db, season_id):
        have = frozenset(m.team_id for m in g.members)
        if have == want:
            return g
    teams = (
        db.query(Team)
        .filter(Team.season_id == season_id, Team.id.in_(want))
        .all()
    )
    if len(teams) != len(want):
        return None
    teams_sorted = sorted(teams, key=lambda t: (t.name or "", t.id))
    g = _insert_group(
        db,
        season_id,
        teams_sorted,
        weekdays or list(DEFAULT_GROUP_WEEKDAYS),
        label=group_label_for_teams(teams_sorted),
    )
    if g:
        db.commit()
        db.refresh(g)
        refresh_group_labels(db, season_id)
        db.refresh(g)
    return g


def propose_groups(
    db: Session,
    season,
    *,
    mode: str = "shared",
    overlap_minutes: int = 0,
    weekdays: list[int] | None = None,
    max_pairs: int = 20,
) -> list[TrainingGroup]:
    """Compat: proposa per capacitat (ignora max_pairs / mode antics)."""
    return propose_capacity_groups(db, season, weekdays=weekdays)


def create_group(
    db: Session,
    *,
    season_id: int,
    team_ids: list[int],
    mode: str,
    overlap_minutes: int,
    weekdays: list[int],
    label: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    venue_id: int | None = None,
    is_draft: bool = False,
) -> TrainingGroup | None:
    ids = []
    for tid in team_ids:
        if tid not in ids:
            ids.append(tid)
    if len(ids) < MIN_GROUP_SIZE or len(ids) > MAX_GROUP_SIZE:
        return None
    mode = "shared"

    # Els equips poden estar en múltiples grups (diferents franjes/dates)

    teams = (
        db.query(Team)
        .filter(Team.season_id == season_id, Team.id.in_(ids))
        .all()
    )
    if len(teams) != len(ids):
        return None
    if not label:
        label = group_label_for_teams(teams)

    g = TrainingGroup(
        season_id=season_id,
        mode="shared",
        overlap_minutes=0,
        weekdays=format_weekdays(weekdays or list(DEFAULT_GROUP_WEEKDAYS)),
        start_date=start_date,
        end_date=end_date,
        start_time=start_time or time(9, 0),
        end_time=end_time or time(10, 30),
        venue_id=venue_id,
        is_draft=is_draft,
        label=label[:120],
    )
    db.add(g)
    db.flush()
    for i, tid in enumerate(ids):
        db.add(
            TrainingGroupMember(group_id=g.id, team_id=tid, sort_order=i)
        )
    db.commit()
    refresh_group_labels(db, season_id)
    db.refresh(g)
    return g


def update_group(
    db: Session,
    *,
    season_id: int,
    group_id: int,
    team_ids: list[int],
    weekdays: list[int],
    start_date: date | None = None,
    end_date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    venue_id: int | None = None,
) -> TrainingGroup | None:
    g = db.get(TrainingGroup, group_id)
    if not g or g.season_id != season_id:
        return None
    ids = []
    for tid in team_ids:
        if tid not in ids:
            ids.append(tid)
    if len(ids) < MIN_GROUP_SIZE or len(ids) > MAX_GROUP_SIZE:
        return None

    # Els equips poden estar en múltiples grups

    teams = (
        db.query(Team)
        .filter(Team.season_id == season_id, Team.id.in_(ids))
        .all()
    )
    if len(teams) != len(ids):
        return None
    # replace members i actualitza el nom per categoria
    for m in list(g.members):
        db.delete(m)
    db.flush()
    for i, tid in enumerate(ids):
        db.add(
            TrainingGroupMember(group_id=g.id, team_id=tid, sort_order=i)
        )
    g.weekdays = format_weekdays(weekdays or list(DEFAULT_GROUP_WEEKDAYS))
    g.start_date = start_date
    g.end_date = end_date
    g.start_time = start_time or g.start_time or time(9, 0)
    g.end_time = end_time or g.end_time or time(10, 30)
    g.venue_id = venue_id
    g.label = group_label_for_teams(teams)
    g.mode = "shared"
    g.overlap_minutes = 0
    db.commit()
    refresh_group_labels(db, season_id)
    db.refresh(g)
    return g


def delete_group(db: Session, season_id: int, group_id: int) -> bool:
    from app.db import Training

    g = db.get(TrainingGroup, group_id)
    if not g or g.season_id != season_id:
        return False
    db.query(Training).filter(Training.training_group_id == group_id).delete(
        synchronize_session=False
    )
    db.delete(g)
    db.commit()
    return True


def generate_draft_from_groups(db: Session, season) -> int:
    """Crea sessions de borrador a partir de les plantilles de grup."""
    groups = load_groups(db, season.id)
    season_start = getattr(season, "start_date", None) or date.today()
    season_end = season.end_date or (season_start + timedelta(days=365))
    created = 0
    for g in groups:
        if not g.start_time or not g.end_time or not g.venue_id:
            continue
        weekdays = set(parse_weekdays(g.weekdays))
        start = g.start_date or season_start
        end = g.end_date or season_end
        team_ids = [m.team_id for m in g.members]
        current = start
        while current <= end:
            if current.weekday() in weekdays:
                for tid in team_ids:
                    exists = (
                        db.query(Training.id)
                        .filter(
                            Training.season_id == season.id,
                            Training.team_id == tid,
                            Training.session_date == current,
                            Training.start_time == g.start_time,
                            Training.end_time == g.end_time,
                            Training.venue_id == g.venue_id,
                        )
                        .first()
                    )
                    if not exists:
                        series = f"tg{g.id}-{tid}-{uuid.uuid4().hex[:6]}"
                        db.add(
                            Training(
                                season_id=season.id,
                                team_id=tid,
                                session_date=current,
                                start_time=g.start_time,
                                end_time=g.end_time,
                                venue_id=g.venue_id,
                                is_draft=True,
                                is_manual=True,
                                series_id=series,
                                training_group_id=g.id,
                                allows_share=True,
                            )
                        )
                        created += 1
            current += timedelta(days=1)
    db.commit()
    return created


def _matching_group_for_key(
    db: Session,
    season_id: int,
    key: tuple[int, time, time, int | None],
    team_ids: set[int],
) -> TrainingGroup | None:
    wd, st, et, vid = key
    wd_s = format_weekdays([wd])
    candidates = (
        db.query(TrainingGroup)
        .options(joinedload(TrainingGroup.members))
        .filter(
            TrainingGroup.season_id == season_id,
            TrainingGroup.venue_id == vid,
            TrainingGroup.start_time == st,
            TrainingGroup.end_time == et,
            TrainingGroup.weekdays == wd_s,
        )
        .all()
    )
    for g in candidates:
        if set(m.team_id for m in g.members) == team_ids:
            return g
    return None


def import_draft_groups(db: Session, season) -> dict:
    """Crea grups de temporada a partir de les combinacions del borrador.

    Només afecta entrenos en estat borrador que encara no tenen un grup assignat.
    """
    from sqlalchemy.orm import joinedload

    trainings = (
        db.query(Training)
        .options(joinedload(Training.team))
        .filter(
            Training.season_id == season.id,
            Training.is_draft.is_(True),
            Training.training_group_id.is_(None),
            Training.training_solape_id.is_(None),
            Training.is_manual.is_(False),
        )
        .all()
    )

    by_key: dict[tuple, list[Training]] = {}
    for t in trainings:
        if t.team_id is None:
            continue
        key = (t.session_date.weekday(), t.start_time, t.end_time, t.venue_id)
        by_key.setdefault(key, []).append(t)

    season_start = None
    season_end = season.end_date
    linked = 0
    created = 0

    for key, rows in by_key.items():
        if len(rows) < 2:
            continue
        team_ids = {r.team_id for r in rows}
        g = _matching_group_for_key(db, season.id, key, team_ids)
        if g is None:
            wd, st, et, vid = key
            teams = sorted(
                {r.team.id: r.team for r in rows if r.team}.values(),
                key=lambda tm: (tm.name or "").casefold(),
            )
            label = f"Borrador: {group_label_for_teams(teams)}"[:120]
            g = TrainingGroup(
                season_id=season.id,
                mode="shared",
                weekdays=format_weekdays([wd]),
                start_date=season_start,
                end_date=season_end,
                start_time=st,
                end_time=et,
                venue_id=vid,
                is_draft=True,
                label=label,
            )
            for i, tm in enumerate(teams):
                g.members.append(TrainingGroupMember(team=tm, sort_order=i))
            db.add(g)
            db.flush()
            created += 1
        for r in rows:
            r.training_group_id = g.id
            linked += 1

    db.commit()
    return {"created": created, "linked": linked}


def clear_draft_group_import(db: Session, season) -> dict:
    """Desfà l'assignació automàtica: desvincula i esborra els grups 'Borrador: ...' en estat esborrador."""
    groups = (
        db.query(TrainingGroup)
        .filter(
            TrainingGroup.season_id == season.id,
            TrainingGroup.is_draft.is_(True),
            TrainingGroup.label.like("Borrador:%"),
        )
        .all()
    )
    unlinked = 0
    for g in groups:
        group_id = g.id
        rows = (
            db.query(Training)
            .filter(
                Training.season_id == season.id,
                Training.is_draft.is_(True),
                Training.training_group_id == group_id,
            )
            .all()
        )
        for r in rows:
            r.training_group_id = None
            unlinked += 1
        db.delete(g)
    db.commit()
    return {"deleted": len(groups), "unlinked": unlinked}
