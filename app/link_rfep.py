"""Asistente RFEP: catálogo Sidgad → elegir equipos del club → importar partidos."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.db import CompetitionSource, Team, TeamExternalName
from app.import_fed import ImportReport, import_competition
from app.sidgad import FEDERATIONS, SidgadClient
from app.teams_meta import (
    BRANCH_SENIOR_FEMALE,
    BRANCH_SENIOR_MALE,
    BRANCH_BASE_MIXED,
    BRANCH_BASE_FEMALE,
    normalize_branch,
)


def _fold(s: str) -> str:
    """minúscules, sense accents, sense puntuació i espais compactats."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(s.casefold().split())


@dataclass
class FedTeam:
    sidgad_id: int | None
    short: str
    full_name: str
    logo: str = ""


@dataclass
class CompetitionInfo:
    idc: int
    name: str
    temp: int
    teams: list[FedTeam] = field(default_factory=list)


@dataclass
class ClubTeamHit:
    """Un equipo federativo en una competición (resultado de búsqueda)."""

    source: str
    idc: int
    competition: str
    temp: int
    team: FedTeam
    suggested: bool = False

    @property
    def key(self) -> str:
        return f"{self.source}|{self.idc}|{self.team.full_name}"

    @property
    def pick_value(self) -> str:
        return f"{self.source}||{self.idc}||{self.team.full_name}||{self.competition}"


def parse_teams_array(value: str) -> list[FedTeam]:
    """logo,sidgad_id,short,full_name;..."""
    out: list[FedTeam] = []
    raw = (value or "").strip()
    if not raw:
        return out
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        bits = part.split(",")
        if len(bits) < 4:
            continue
        logo, sid, short, full = bits[0], bits[1], bits[2], ",".join(bits[3:]).strip()
        sid_id = None
        if sid.isdigit():
            sid_id = int(sid)
        if not full:
            continue
        out.append(FedTeam(sidgad_id=sid_id, short=short.strip(), full_name=full, logo=logo))
    return out


def parse_competition_catalog(html: str) -> list[CompetitionInfo]:
    soup = BeautifulSoup(html, "lxml")
    out: list[CompetitionInfo] = []
    seen: set[int] = set()

    for a in soup.select("a.listado_competiciones_fila"):
        idc_s = a.get("id")
        if not idc_s or not str(idc_s).isdigit():
            continue
        idc = int(idc_s)
        if idc in seen:
            continue
        seen.add(idc)
        name = (a.get("name") or a.get("idc_name") or "").strip()
        cls = " ".join(a.get("class") or [])
        tm = re.search(r"temp_(\d+)", cls)
        temp = int(tm.group(1)) if tm else 0
        inp = soup.find("input", id=f"teams_array_{idc}")
        teams = parse_teams_array(inp.get("value") if inp else "")
        out.append(CompetitionInfo(idc=idc, name=name, temp=temp, teams=teams))

    out.sort(key=lambda c: (-c.temp, c.name.casefold(), -c.idc))
    return out


def current_season_temp(catalog: list[CompetitionInfo]) -> int:
    """Temporada Sidgad actual (excluye temp>=1000 especiales)."""
    temps = [c.temp for c in catalog if 0 < c.temp < 1000]
    return max(temps) if temps else 0


FED_SOURCES = tuple(FEDERATIONS.keys()) + ("fvp",)


def load_fed_catalog(source: str = "rfep") -> list[CompetitionInfo]:
    if source not in FED_SOURCES:
        raise ValueError(f"Fuente no soportada: {source}")
    client = SidgadClient(source, sleep_s=0.15)
    html = client.fetch_competition_list()
    return parse_competition_catalog(html)


def load_rfep_catalog() -> list[CompetitionInfo]:
    return load_fed_catalog("rfep")


def search_club_in_catalog(
    catalog: list[CompetitionInfo],
    query: str,
    *,
    source: str,
    current_only: bool = True,
    prefer_club: str | None = None,
) -> list[ClubTeamHit]:
    q = _fold(query)
    if len(q) < 2:
        return []
    prefer = _fold(prefer_club or "")
    cur = current_season_temp(catalog) if current_only else 0
    hits: list[ClubTeamHit] = []
    for comp in catalog:
        if current_only and cur and comp.temp != cur:
            continue
        for team in comp.teams:
            blob = _fold(f"{team.full_name} {team.short}")
            if q in blob:
                hits.append(
                    ClubTeamHit(
                        source=source,
                        idc=comp.idc,
                        competition=comp.name,
                        temp=comp.temp,
                        team=team,
                        suggested=bool(prefer and prefer in blob),
                    )
                )
    hits.sort(
        key=lambda h: (
            not h.suggested,
            h.competition.casefold(),
            h.team.full_name.casefold(),
        )
    )
    return hits


def _infer_branch(competition: str) -> str:
    n = competition.casefold()
    fem = any(
        x in n for x in ("femenin", "iberdrola", "femení", "femenina", "fem ")
    )
    if fem:
        if any(x in n for x in ("sènior", "senior", "iberdrola", "ok liga")):
            return BRANCH_SENIOR_FEMALE
        return BRANCH_BASE_FEMALE
    if any(x in n for x in ("ok liga",)) or (
        any(x in n for x in ("plata", "bronce")) and "fem" not in n
    ):
        return BRANCH_SENIOR_MALE
    if any(x in n for x in ("masculin", "masculí")):
        return BRANCH_SENIOR_MALE
    return BRANCH_BASE_MIXED


def _unique_team_name(db: Session, season_id: int, base: str, competition: str) -> str:
    """Mismo nombre corto OK en otra categoría; solo colisiona name+category."""
    existing = {
        (t.name.casefold(), (t.category or "").casefold())
        for t in db.query(Team).filter(Team.season_id == season_id).all()
    }
    key = (base.casefold(), (competition or "").casefold())
    if key not in existing:
        return base
    n = 2
    while (f"{base} ({n})".casefold(), key[1]) in existing:
        n += 1
    return f"{base} ({n})"


def ensure_team_for_fed(
    db: Session,
    season_id: int,
    *,
    external_name: str,
    competition: str,
    source: str = "rfep",
) -> Team:
    """Un Team por (nombre federativo + competición). Nombre = completo federativo."""
    if source not in FED_SOURCES:
        raise ValueError(f"Fuente no soportada: {source}")
    # Identidad: alias + categoría (liga). Misma marca en ligas distintas = equipos distintos.
    alias = (
        db.query(TeamExternalName)
        .join(Team)
        .filter(
            Team.season_id == season_id,
            Team.category == competition,
            TeamExternalName.source == source,
            TeamExternalName.external_name == external_name,
        )
        .first()
    )
    if alias:
        return alias.team

    branch = normalize_branch(_infer_branch(competition))
    name = _unique_team_name(db, season_id, external_name.strip(), competition)
    team = Team(
        season_id=season_id,
        name=name,
        category=competition,
        branch=branch,
    )
    db.add(team)
    db.flush()

    db.add(
        TeamExternalName(
            team_id=team.id,
            source=source,
            external_name=external_name,
        )
    )
    db.flush()
    return team


def has_fed_link(db: Session, season_id: int) -> bool:
    """Qualsevol federació enllaçada (RFEP, FECAPA, …)."""
    return (
        db.query(CompetitionSource)
        .filter(
            CompetitionSource.season_id == season_id,
            CompetitionSource.source.in_(FED_SOURCES),
        )
        .first()
        is not None
    )


def has_rfep_link(db: Session, season_id: int) -> bool:
    """Compat: «té federació» (no només RFEP)."""
    return has_fed_link(db, season_id)


def import_selected_fed_teams(
    db: Session,
    season_id: int,
    selections: list[tuple[int, str, str]],
    *,
    source: str = "rfep",
) -> list[ImportReport]:
    """
    selections: [(idc, external_name, competition_label), ...]
    Crea equipos/alias e importa cada competición implicada.
    """
    if source not in FED_SOURCES:
        raise ValueError(f"Fuente no soportada: {source}")
    if not selections:
        return []

    by_idc: dict[int, list[tuple[str, str]]] = {}
    for idc, ext_name, comp_label in selections:
        ensure_team_for_fed(
            db,
            season_id,
            external_name=ext_name,
            competition=comp_label,
            source=source,
        )
        by_idc.setdefault(idc, []).append((ext_name, comp_label))

    db.commit()

    reports: list[ImportReport] = []
    for idc, items in by_idc.items():
        label = items[0][1]
        names = [ext for ext, _ in items]
        reports.append(
            import_competition(
                db,
                season_id,
                source,
                idc,
                apply=True,
                label=label,
                only_external_names=names,
            )
        )
    return reports


def import_selected_rfep_teams(
    db: Session,
    season_id: int,
    selections: list[tuple[int, str, str]],
) -> list[ImportReport]:
    return import_selected_fed_teams(db, season_id, selections, source="rfep")


def group_hits_by_team(
    hits: list[ClubTeamHit],
) -> list[tuple[str, list[ClubTeamHit]]]:
    """Agrupa los resultados por nombre de equipo (sin importar la federación)."""
    groups: dict[str, list[ClubTeamHit]] = {}
    for h in hits:
        groups.setdefault(h.team.full_name, []).append(h)
    out: list[tuple[str, list[ClubTeamHit]]] = []
    for name in sorted(groups, key=lambda n: _fold(n)):
        items = groups[name]
        items.sort(
            key=lambda h: (h.source.casefold(), h.competition.casefold())
        )
        out.append((name, items))
    return out


def search_all_federations(query: str) -> list[ClubTeamHit]:
    """Búsqueda global: recorre todas las federaciones Sidgad + FVP."""
    q = _fold(query)
    if len(q) < 2:
        return []
    all_hits: list[ClubTeamHit] = []
    for source in FEDERATIONS:
        try:
            catalog = load_fed_catalog(source)
            all_hits.extend(
                search_club_in_catalog(
                    catalog, query, source=source
                )
            )
        except Exception:
            continue
    try:
        from app.fvp import search_fvp_club_hits

        all_hits.extend(search_fvp_club_hits(query, source="fvp"))
    except Exception:
        pass
    seen: set[tuple[str, int, str]] = set()
    unique: list[ClubTeamHit] = []
    for h in all_hits:
        k = (h.source, h.idc, h.team.full_name)
        if k in seen:
            continue
        seen.add(k)
        unique.append(h)
    unique.sort(
        key=lambda h: (
            _fold(h.team.full_name),
            h.source.casefold(),
            h.competition.casefold(),
        )
    )
    return unique
