"""Gestor de persones: accions massives (bulk), substitució des de fitxer
i exportació CSV. La lògica viu aquí perquè main.py quedi prim."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db import Conflict, Person, PersonUnavailability, Team, TeamMembership
from app.import_lists import (
    PERSON_HEADERS,
    ROLE_HEADERS,
    TEAM_HEADERS,
    _first,
    _norm,
    _norm_role,
    _team_key,
    canon_person_name,
    find_person_canon,
    person_key,
)
from app.teams_meta import infer_branch

MEMBER_ROLES = ("player", "coach", "reinforce", "delegate")

# Etiquetes en català per al CSV exportat; totes són al ROLE_MAP de
# import_lists, així que el fitxer es pot reimportar tal qual.
ROLE_LABELS = {
    "player": "jugador",
    "coach": "entrenador",
    "reinforce": "reforç",
    "delegate": "delegat",
}


def parse_sel_pairs(values: list[str]) -> list[tuple[int | None, int]]:
    """Valors "team:person" dels checkboxes → [(team_id|None, person_id)].
    team 0 = grup de sense equip."""
    pairs: list[tuple[int | None, int]] = []
    seen: set[tuple[int | None, int]] = set()
    for v in values:
        try:
            t, p = str(v).split(":")
            pair = (int(t) or None, int(p))
        except ValueError:
            continue
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    return pairs


def _season_people(db: Session, season_id: int) -> dict[int, Person]:
    return {
        p.id: p
        for p in db.query(Person).filter(Person.season_id == season_id).all()
    }


def delete_people(db: Session, season_id: int, person_ids: list[int]) -> int:
    """Esborra persones del club: membresies, indisponibilitats i
    conflictes. Retorna quantes s'han esborrat."""
    valid = _season_people(db, season_id)
    ids = [pid for pid in set(person_ids) if pid in valid]
    if not ids:
        return 0
    db.query(PersonUnavailability).filter(
        PersonUnavailability.person_id.in_(ids)
    ).delete(synchronize_session=False)
    db.query(Conflict).filter(Conflict.person_id.in_(ids)).delete(
        synchronize_session=False
    )
    db.query(TeamMembership).filter(TeamMembership.person_id.in_(ids)).delete(
        synchronize_session=False
    )
    n = (
        db.query(Person)
        .filter(Person.id.in_(ids), Person.season_id == season_id)
        .delete(synchronize_session=False)
    )
    return n


def _memberships_of(db: Session, team_id: int, person_id: int) -> list[TeamMembership]:
    return (
        db.query(TeamMembership)
        .filter(
            TeamMembership.team_id == team_id,
            TeamMembership.person_id == person_id,
        )
        .all()
    )


def _link_exists(db: Session, team_id: int, person_id: int, role: str) -> bool:
    return (
        db.query(TeamMembership)
        .filter(
            TeamMembership.team_id == team_id,
            TeamMembership.person_id == person_id,
            TeamMembership.role == role,
        )
        .first()
        is not None
    )


def bulk_people(
    db: Session,
    season_id: int,
    action: str,
    pairs: list[tuple[int | None, int]],
    target_team_id: int | None = None,
    role: str | None = None,
) -> int:
    """Aplica l'acció sobre els parells (equip, persona) seleccionats.
    Retorna el nombre de persones/vínculs afectats."""
    valid = _season_people(db, season_id)
    team_ids = {
        t.id for t in db.query(Team).filter(Team.season_id == season_id).all()
    }
    pairs = [
        (t if t in team_ids else None, p)
        for t, p in pairs
        if p in valid and (t is None or t in team_ids)
    ]
    if target_team_id not in team_ids:
        target_team_id = None
    if role not in MEMBER_ROLES:
        role = None

    if action == "delete":
        n = delete_people(db, season_id, [p for _, p in pairs])
        db.commit()
        return n

    n = 0
    if action == "remove":
        for tid, pid in pairs:
            if tid is None:
                continue
            if _memberships_of(db, tid, pid):
                for m in _memberships_of(db, tid, pid):
                    db.delete(m)
                n += 1
    elif action == "role":
        if not role:
            return 0
        for tid, pid in pairs:
            if tid is None:
                continue
            ms = _memberships_of(db, tid, pid)
            if not ms:
                continue
            # Un sol rol per persona i equip: queda't el primer, esborra la resta
            for extra in ms[1:]:
                db.delete(extra)
            if _link_exists(db, tid, pid, role) and ms[0].role != role:
                db.delete(ms[0])
            else:
                ms[0].role = role
            n += 1
    elif action in ("move", "add"):
        if not target_team_id:
            return 0
        for tid, pid in pairs:
            if action == "move" and tid == target_team_id:
                continue
            if action == "move" and tid is not None:
                moved = False
                for m in _memberships_of(db, tid, pid):
                    if _link_exists(db, target_team_id, pid, m.role):
                        db.delete(m)
                    else:
                        m.team_id = target_team_id
                    moved = True
                n += 1 if moved else 0
            else:
                # add, o move des del grup "sense equip"
                r = role or "player"
                if not _link_exists(db, target_team_id, pid, r):
                    db.add(
                        TeamMembership(
                            team_id=target_team_id, person_id=pid, role=r
                        )
                    )
                    n += 1
    else:
        return 0
    db.commit()
    return n


# ------------------------------------------------------------------
# Substitució des de fitxer (replace)
# ------------------------------------------------------------------


def rows_to_rows_text(rows: list[dict[str, str]]) -> str:
    """Files parsejades → text canònic "equip;categoria;persona;rol"
    per reenviar-lo al confirmar (sense dependre del fitxer original)."""
    lines = []
    for r in rows:
        equipo = _first(r, TEAM_HEADERS)
        cat = r.get("categoria") or r.get("category") or ""
        persona = _first(r, PERSON_HEADERS)
        rol = _first(r, ROLE_HEADERS)
        if not persona.strip():
            continue
        fields = [equipo, cat, persona, rol]
        lines.append(";".join((f or "").replace(";", " ").strip() for f in fields))
    return "\n".join(lines)


def parse_rows_text(text: str) -> list[dict[str, str]]:
    """Invers de rows_to_rows_text."""
    rows = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split(";")]
        if not any(parts):
            continue
        equipo, cat, persona, rol = (parts + ["", "", "", ""])[:4]
        rows.append(
            {"equipo": equipo, "categoria": cat, "persona": persona, "rol": rol}
        )
    return rows


@dataclass
class ReplacePlan:
    scope: str = "team"
    scope_team_name: str = ""
    rows_ok: int = 0
    keep: int = 0
    new_people: list[str] = field(default_factory=list)
    new_links: list[tuple[str, str]] = field(default_factory=list)  # (persona, equip)
    new_teams: list[str] = field(default_factory=list)
    unlinks: list[tuple[str, str]] = field(default_factory=list)  # (persona, equip)
    deletes: list[str] = field(default_factory=list)
    also_elsewhere: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def applicable(self) -> bool:
        return self.rows_ok > 0 and not self.errors


@dataclass
class _TeamSpec:
    """Equip destí d'una fila: existent o a crear."""
    key: str
    name: str
    category: str
    team: Team | None


def _resolve_team(
    spec_name: str, spec_cat: str, teams: list[Team]
) -> Team | None:
    """Equip existent per nom canònic; si n'hi ha varis, preferència al
    que coincideixi la categoria."""
    key = _team_key(spec_name)
    cands = [t for t in teams if _team_key(t.name) == key]
    if not cands:
        return None
    ck = _team_key(spec_cat)
    if ck:
        match = next((t for t in cands if _team_key(t.category) == ck), None)
        if match:
            return match
    exact = next((t for t in cands if t.name == spec_name.strip()), None)
    return exact or cands[0]


def _desired_state(
    db: Session,
    season_id: int,
    rows: list[dict[str, str]],
    scope: str,
    scope_team: Team | None,
) -> tuple[dict, dict, list[_TeamSpec], int]:
    """Estat desitjat segons el fitxer.
    Retorna (persones {pkey: nom}, links {(pkey, spec_key, role)}, specs, files_vàlides)."""
    people_wanted: dict[str, str] = {}
    links_wanted: dict[tuple[str, str, str], None] = {}
    specs: dict[str, _TeamSpec] = {}
    rows_ok = 0
    for r in rows:
        name = canon_person_name(r.get("persona"))
        if not name:
            continue
        pkey = person_key(name)
        role = _norm_role(r.get("rol") or "player")
        rows_ok += 1
        people_wanted.setdefault(pkey, name)
        if scope == "team":
            spec_key = "scope"
            if spec_key not in specs and scope_team:
                specs[spec_key] = _TeamSpec(
                    key=spec_key,
                    name=scope_team.name,
                    category=scope_team.category or "",
                    team=scope_team,
                )
        else:
            tname = _norm(r.get("equipo"))
            if not tname:
                continue  # persona sense equip: existeix però no es vincula
            cat = _norm(r.get("categoria"))
            spec_key = f"{_team_key(tname)}||{_team_key(cat)}"
            if spec_key not in specs:
                specs[spec_key] = _TeamSpec(
                    key=spec_key, name=tname, category=cat, team=None
                )
        links_wanted[(pkey, spec_key, role)] = None
    return people_wanted, links_wanted, list(specs.values()), rows_ok


def build_replace_plan(
    db: Session,
    season_id: int,
    rows: list[dict[str, str]],
    scope: str,
    scope_team_id: int | None,
) -> ReplacePlan:
    """Calcula el diff fitxer vs BD sense escriure res (vista prèvia)."""
    plan = ReplacePlan(scope=scope)
    teams = db.query(Team).filter(Team.season_id == season_id).all()
    people = db.query(Person).filter(Person.season_id == season_id).all()
    memberships = (
        db.query(TeamMembership)
        .join(Team)
        .filter(Team.season_id == season_id)
        .all()
    )
    person_by_key = {person_key(p.full_name): p for p in people}
    person_by_id = {p.id: p for p in people}
    team_by_id = {t.id: t for t in teams}

    scope_team = None
    if scope == "team":
        scope_team = next((t for t in teams if t.id == scope_team_id), None)
        if not scope_team:
            plan.errors.append("team_missing")
            return plan
        plan.scope_team_name = scope_team.name

    people_wanted, links_wanted, specs, rows_ok = _desired_state(
        db, season_id, rows, scope, scope_team
    )
    plan.rows_ok = rows_ok
    if not rows_ok:
        plan.errors.append("no_rows")
        return plan

    # Resol specs a equips existents o nous
    spec_team: dict[str, Team | None] = {}
    for spec in specs:
        spec.team = scope_team if scope == "team" else _resolve_team(
            spec.name, spec.category, teams
        )
        spec_team[spec.key] = spec.team
        if spec.team is None:
            plan.new_teams.append(spec.name)

    # Links desitjats resolts a team_id (els equips nous encara no en tenen)
    want_links: set[tuple[str, int, str]] = {
        (pk, spec_team[sk].id, role)
        for pk, sk, role in links_wanted
        if spec_team[sk] is not None
    }

    for pk, sk, role in links_wanted:
        person = person_by_key.get(pk)
        tname = specs_name(specs, sk)
        pname = people_wanted[pk]
        if person is None and pname not in plan.new_people:
            plan.new_people.append(pname)
        if (
            person is not None
            and spec_team[sk] is not None
            and _link_exists(db, spec_team[sk].id, person.id, role)
        ):
            plan.keep += 1
        else:
            plan.new_links.append((pname, tname))

    # Baixes: membresies actuals fora de l'estat desitjat
    seen_unlink: set[tuple[int, int]] = set()
    for m in memberships:
        person = person_by_id.get(m.person_id)
        team = team_by_id.get(m.team_id)
        if not person or not team:
            continue
        pk = person_key(person.full_name)
        wanted = pk in people_wanted
        if scope == "team":
            if m.team_id == scope_team.id and not wanted:
                if (m.team_id, m.person_id) not in seen_unlink:
                    seen_unlink.add((m.team_id, m.person_id))
                    plan.unlinks.append((person.full_name, team.name))
            continue
        # scope == club
        if not wanted:
            continue  # la persona s'esborra sencera, no cal llistar el víncul
        # Persona desitjada: la membresia ha de estar a la llista exacta
        if (pk, m.team_id, m.role) not in want_links:
            if (m.team_id, m.person_id, m.role) not in seen_unlink:
                seen_unlink.add((m.team_id, m.person_id, m.role))
                plan.unlinks.append((person.full_name, team.name))

    if scope == "club":
        # Persones del fitxer sense equip: no esborrar-les ni crear-les dues
        for pk, pname in people_wanted.items():
            if pk not in person_by_key and pname not in plan.new_people:
                plan.new_people.append(pname)
        for p in people:
            if person_key(p.full_name) not in people_wanted:
                plan.deletes.append(p.full_name)
    else:
        # Info: gent del fitxer que també és a altres equips (s'hi queden)
        others = {
            m.person_id
            for m in memberships
            if m.team_id != scope_team.id
        }
        for pk, pname in people_wanted.items():
            person = person_by_key.get(pk)
            if person and person.id in others:
                plan.also_elsewhere.append(person.full_name)

    plan.new_links = sorted(set(plan.new_links))
    plan.new_people = sorted(set(plan.new_people))
    plan.new_teams = sorted(set(plan.new_teams))
    plan.unlinks = sorted(set(plan.unlinks))
    plan.deletes = sorted(set(plan.deletes))
    plan.also_elsewhere = sorted(set(plan.also_elsewhere))
    return plan


def specs_name(specs: list[_TeamSpec], key: str) -> str:
    for s in specs:
        if s.key == key:
            return s.name
    return ""


def apply_replace(
    db: Session,
    season_id: int,
    rows: list[dict[str, str]],
    scope: str,
    scope_team_id: int | None,
) -> dict[str, int]:
    """Aplica la substitució. Recalcula el pla (no confia en resposta del
    client) i escriu els canvis."""
    teams = db.query(Team).filter(Team.season_id == season_id).all()
    scope_team = None
    if scope == "team":
        scope_team = next((t for t in teams if t.id == scope_team_id), None)
        if not scope_team:
            return {"error": 1}

    people_wanted, links_wanted, specs, rows_ok = _desired_state(
        db, season_id, rows, scope, scope_team
    )
    if not rows_ok:
        return {"error": 1}

    counts = {
        "created": 0,
        "linked": 0,
        "unlinked": 0,
        "deleted": 0,
        "teams_created": 0,
    }

    # Equips nous
    team_by_spec: dict[str, Team] = {}
    for spec in specs:
        team = scope_team if scope == "team" else _resolve_team(
            spec.name, spec.category, teams
        )
        if team is None:
            team = Team(
                season_id=season_id,
                name=spec.name,
                category=spec.category or None,
                branch=infer_branch(spec.name, spec.category or None),
            )
            db.add(team)
            db.flush()
            teams.append(team)
            counts["teams_created"] += 1
        team_by_spec[spec.key] = team

    # Persones + membresies desitjades
    person_cache: dict[str, Person] = {}
    seen_links: set[tuple[int, int, str]] = set()
    for pk, sk, role in links_wanted:
        team = team_by_spec.get(sk)
        if team is None:
            continue
        person = person_cache.get(pk)
        if person is None:
            person = find_person_canon(db, season_id, people_wanted[pk])
            if person is None:
                person = Person(
                    season_id=season_id,
                    full_name=people_wanted[pk],
                    is_player=role in {"player", "reinforce"},
                    is_coach=role == "coach",
                    is_delegate=role == "delegate",
                )
                db.add(person)
                db.flush()
                counts["created"] += 1
            else:
                person.is_player = person.is_player or role in {"player", "reinforce"}
                person.is_coach = person.is_coach or role == "coach"
                person.is_delegate = person.is_delegate or role == "delegate"
            person_cache[pk] = person
        key = (team.id, person.id, role)
        if key not in seen_links and not _link_exists(db, team.id, person.id, role):
            db.add(TeamMembership(team_id=team.id, person_id=person.id, role=role))
            seen_links.add(key)
            counts["linked"] += 1

    # Persones del fitxer sense equip (abast club): existeixen però no
    # es vinculen — així el cicle exporta→reimporta no les perd.
    if scope == "club":
        for pk, pname in people_wanted.items():
            if pk in person_cache:
                continue
            person = find_person_canon(db, season_id, pname)
            if person is None:
                person = Person(
                    season_id=season_id,
                    full_name=pname,
                    is_player=True,
                )
                db.add(person)
                db.flush()
                counts["created"] += 1
            person_cache[pk] = person
    db.flush()

    # Baixes
    if scope == "team":
        for m in list(
            db.query(TeamMembership)
            .filter(TeamMembership.team_id == scope_team.id)
            .all()
        ):
            person = db.get(Person, m.person_id)
            if person and person_key(person.full_name) not in people_wanted:
                db.delete(m)
                counts["unlinked"] += 1
    else:
        want_resolved: set[tuple[int, int, str]] = set()
        for pk, sk, role in links_wanted:
            team = team_by_spec.get(sk)
            person = person_cache.get(pk)
            if team and person:
                want_resolved.add((team.id, person.id, role))
        all_ms = (
            db.query(TeamMembership)
            .join(Team)
            .filter(Team.season_id == season_id)
            .all()
        )
        for m in all_ms:
            person = db.get(Person, m.person_id)
            if not person:
                continue
            pk = person_key(person.full_name)
            if pk not in people_wanted:
                continue  # la persona sencera s'esborrarà
            if (m.team_id, m.person_id, m.role) not in want_resolved:
                db.delete(m)
                counts["unlinked"] += 1
        db.flush()
        drop_ids = [
            p.id
            for p in db.query(Person).filter(Person.season_id == season_id).all()
            if person_key(p.full_name) not in people_wanted
        ]
        counts["deleted"] = delete_people(db, season_id, drop_ids)

    db.commit()
    return counts


# ------------------------------------------------------------------
# Exportació CSV
# ------------------------------------------------------------------


def export_people_csv(
    db: Session, season_id: int, scope: str = "club", team_id: int | None = None
) -> str:
    """CSV "equipo;categoria;nombre;rol" reimportable (una fila per
    membresia; les persones sense equip van amb equip buit)."""
    ms = (
        db.query(TeamMembership)
        .join(Team)
        .filter(Team.season_id == season_id)
        .all()
    )
    if scope == "team" and team_id:
        ms = [m for m in ms if m.team_id == team_id]
    ms.sort(
        key=lambda m: (
            (m.team.name or "").casefold(),
            canon_person_name(m.person.full_name).casefold() if m.person else "",
        )
    )
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(["equipo", "categoria", "nombre", "rol"])
    for m in ms:
        w.writerow(
            [
                m.team.name,
                m.team.category or "",
                canon_person_name(m.person.full_name) if m.person else "",
                ROLE_LABELS.get(m.role, m.role),
            ]
        )
    if scope == "club":
        all_linked = {
            x.person_id
            for x in db.query(TeamMembership)
            .join(Team)
            .filter(Team.season_id == season_id)
            .all()
        }
        for p in db.query(Person).filter(Person.season_id == season_id).all():
            if p.id not in all_linked:
                w.writerow(["", "", canon_person_name(p.full_name), ""])
    return buf.getvalue()
