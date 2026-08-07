"""Importación sencilla de listas: equipos, personas y plantillas (CSV)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db import Person, Team, TeamMembership
from app.teams_meta import infer_branch


ROLE_MAP = {
    "player": "player",
    "jugador": "player",
    "jogadora": "player",
    "jogadora/jogador": "player",
    "jogador": "player",
    "giocatore": "player",
    "joueur": "player",
    "spieler": "player",
    "coach": "coach",
    "entrenador": "coach",
    "entrenadora": "coach",
    "treinador": "coach",
    "allenatore": "coach",
    "entraîneur": "coach",
    "trainer": "coach",
    "reinforce": "reinforce",
    "refuerzo": "reinforce",
    "reforç": "reinforce",
    "reforço": "reinforce",
    "rinforzo": "reinforce",
    "renfort": "reinforce",
    "verstärkung": "reinforce",
}


@dataclass
class ImportReport:
    teams_created: int = 0
    people_created: int = 0
    links_created: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors or (
            self.teams_created + self.people_created + self.links_created > 0
        )


def _detect_delimiter(sample: str) -> str:
    first = (sample.splitlines() or [""])[0]
    if first.count(";") >= first.count(","):
        return ";"
    return ","


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_role(value: str) -> str:
    key = _norm(value).casefold()
    return ROLE_MAP.get(key, "player")


def _truthy(value: str) -> bool:
    return _norm(value).casefold() in {"1", "true", "yes", "si", "sí", "x", "s"}


def parse_csv_text(raw: str) -> list[dict[str, str]]:
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    # Quitar BOM Excel
    if text.startswith("\ufeff"):
        text = text[1:]
    delim = _detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if not reader.fieldnames:
        return []
    # Normalizar cabeceras
    field_map = {h: _norm(h).casefold() for h in reader.fieldnames if h}
    rows: list[dict[str, str]] = []
    for row in reader:
        clean = {}
        for orig, val in row.items():
            if orig is None:
                continue
            clean[field_map.get(orig, _norm(orig).casefold())] = _norm(val)
        if any(clean.values()):
            rows.append(clean)
    return rows


def _get_or_create_team(db: Session, season_id: int, name: str, category: str | None, report: ImportReport) -> Team | None:
    name = _norm(name)
    if not name:
        return None
    team = (
        db.query(Team)
        .filter(Team.season_id == season_id, Team.name == name)
        .first()
    )
    if team:
        return team
    cat = _norm(category) or None
    team = Team(
        season_id=season_id,
        name=name,
        category=cat,
        branch=infer_branch(name, cat),
    )
    db.add(team)
    db.flush()
    report.teams_created += 1
    return team


def _get_or_create_person(
    db: Session,
    season_id: int,
    name: str,
    role: str,
    report: ImportReport,
) -> Person | None:
    name = _norm(name)
    if not name:
        return None
    person = (
        db.query(Person)
        .filter(Person.season_id == season_id, Person.full_name == name)
        .first()
    )
    if person:
        # Ampliar flags si el CSV trae rol coach/player
        if role == "coach" and not person.is_coach:
            person.is_coach = True
        if role == "player" and not person.is_player:
            person.is_player = True
        return person
    person = Person(
        season_id=season_id,
        full_name=name,
        is_player=role != "coach",
        is_coach=role == "coach",
    )
    db.add(person)
    db.flush()
    report.people_created += 1
    return person


def import_roster_rows(db: Session, season_id: int, rows: list[dict[str, str]]) -> ImportReport:
    """CSV plantilla: equipo;persona;rol  (rol opcional)."""
    report = ImportReport()
    for i, row in enumerate(rows, start=2):
        team_name = (
            row.get("equipo")
            or row.get("team")
            or row.get("equipa")
            or row.get("squadra")
            or row.get("équipe")
            or ""
        )
        person_name = (
            row.get("persona")
            or row.get("person")
            or row.get("nombre")
            or row.get("name")
            or row.get("nome")
            or ""
        )
        role = _norm_role(
            row.get("rol")
            or row.get("role")
            or row.get("função")
            or row.get("ruolo")
            or "player"
        )
        if not team_name or not person_name:
            report.skipped += 1
            continue
        team = _get_or_create_team(
            db,
            season_id,
            team_name,
            row.get("categoria") or row.get("category"),
            report,
        )
        person = _get_or_create_person(db, season_id, person_name, role, report)
        if not team or not person:
            report.skipped += 1
            continue
        exists = (
            db.query(TeamMembership)
            .filter(
                TeamMembership.team_id == team.id,
                TeamMembership.person_id == person.id,
                TeamMembership.role == role,
            )
            .first()
        )
        if exists:
            report.skipped += 1
            continue
        db.add(TeamMembership(team_id=team.id, person_id=person.id, role=role))
        report.links_created += 1
    db.commit()
    return report


def import_teams_rows(db: Session, season_id: int, rows: list[dict[str, str]]) -> ImportReport:
    report = ImportReport()
    for i, row in enumerate(rows, start=2):
        name = row.get("equipo") or row.get("team") or row.get("nombre") or row.get("name") or ""
        category = row.get("categoria") or row.get("category") or ""
        if not _norm(name):
            report.skipped += 1
            continue
        before = report.teams_created
        _get_or_create_team(db, season_id, name, category, report)
        if report.teams_created == before:
            report.skipped += 1
    if report.teams_created:
        db.commit()
    else:
        db.rollback()
    return report


def import_people_rows(db: Session, season_id: int, rows: list[dict[str, str]]) -> ImportReport:
    report = ImportReport()
    for i, row in enumerate(rows, start=2):
        name = (
            row.get("persona")
            or row.get("person")
            or row.get("nombre")
            or row.get("name")
            or row.get("nome")
            or ""
        )
        if not _norm(name):
            report.skipped += 1
            continue
        is_coach = _truthy(row.get("entrenador") or row.get("coach") or "")
        is_player = _truthy(row.get("jugador") or row.get("player") or "1")
        if is_coach and not (row.get("jugador") or row.get("player")):
            is_player = False
        role = "coach" if is_coach and not is_player else "player"
        before = report.people_created
        _get_or_create_person(db, season_id, name, role, report)
        person = (
            db.query(Person)
            .filter(Person.season_id == season_id, Person.full_name == _norm(name))
            .first()
        )
        if person:
            person.is_coach = person.is_coach or is_coach
            person.is_player = person.is_player or is_player or not is_coach
        if report.people_created == before:
            report.skipped += 1
    if report.people_created:
        db.commit()
    else:
        db.rollback()
    return report


ROSTER_TEMPLATE = "equipo;persona;rol\nSenior A;Joan Garcia;jugador\nSenior A;Anna Coach;entrenador\nSenior B;Pere Lopez;jugador\n"
TEAMS_TEMPLATE = "equipo;categoria\nSenior A;Senior\nSenior B;Senior\n"
PEOPLE_TEMPLATE = "nombre;jugador;entrenador\nJoan Garcia;1;0\nAnna Coach;0;1\n"
