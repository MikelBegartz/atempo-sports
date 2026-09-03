from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, time
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.conflicts import find_conflicts, persist_conflicts
from app.db import CompetitionSource, Match, Season, Training
from app.import_fed import ImportReport, ImportRow, _match_home_venue_id
from app.link_rfep import ClubTeamHit, FedTeam, ensure_team_for_fed

FVP_BASE = "https://fvpatinaje.eus"
FVP_WS = f"{FVP_BASE}/webservices/WSCompeticiones.asmx"
FVP_MODALIDAD = "hp"  # Hockey Patines
FVP_SOURCE = "fvp"


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _call_ws(method: str, payload: dict[str, Any]) -> Any:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    url = f"{FVP_WS}/{method}"
    r = requests.post(url, data=json.dumps(payload), headers=headers, timeout=60)
    r.raise_for_status()
    d = r.json().get("d", "")
    if isinstance(d, str) and d:
        return json.loads(d)
    return d


def fvp_temporada_actual(modalidad: str = FVP_MODALIDAD) -> int | None:
    temps = _call_ws("GetTemporadasCompeticion", {"modalidad": modalidad})
    for t in temps:
        if t.get("Actual"):
            return t["IdTempComp"]
    return None


def fvp_competiciones(modalidad: str = FVP_MODALIDAD) -> list[dict[str, Any]]:
    temp_id = fvp_temporada_actual(modalidad)
    if temp_id is None:
        return []
    return _call_ws(
        "GetCompeticiones",
        {"modalidad": modalidad, "temporada": str(temp_id)},
    )


def fvp_clubes(modalidad: str = FVP_MODALIDAD) -> list[dict[str, Any]]:
    return _call_ws("GetClubesCompeticiones", {"modalidad": modalidad})


def _competiciones_by_name(modalidad: str = FVP_MODALIDAD) -> dict[str, int]:
    return {c["DenoComp"]: c["IdCompeticion"] for c in fvp_competiciones(modalidad)}


def fvp_agenda_partidos(
    identidadclub: int,
    modalidad: str = FVP_MODALIDAD,
    dias: int = 999,
) -> list[dict[str, Any]]:
    return _call_ws(
        "GetAgendaPartidos",
        {
            "modalidad": modalidad,
            "dias": str(dias),
            "identidadclub": str(identidadclub),
        },
    )


def fvp_calendario_competicion(idcompeticion: int) -> list[dict[str, Any]]:
    d = _call_ws(
        "GetCalendarioCompeticion",
        {"idcompeticion": str(idcompeticion), "idequipocomp": "%"},
    )
    partidos: list[dict[str, Any]] = []
    for phase in d:
        partidos.extend(phase.get("Partidos", []))
    return partidos


def fvp_clasificacion_competicion(idcompeticion: int) -> list[dict[str, Any]]:
    return _call_ws(
        "GetClasificacionCompeticion",
        {"idcompeticion": str(idcompeticion), "idequipocomp": "%"},
    )


def search_fvp_club_hits(
    query: str, modalidad: str = FVP_MODALIDAD, source: str = FVP_SOURCE
) -> list[ClubTeamHit]:
    q = query.strip().lower()
    clubs = fvp_clubes(modalidad)
    comp_by_name = _competiciones_by_name(modalidad)
    hits: list[ClubTeamHit] = []
    seen: set[tuple[int, str]] = set()

    matched_ids: set[int] = set()
    for club in clubs:
        deno = (club.get("DenoAbreviada") or "").strip()
        if q in deno.lower() or q in _strip_accents(deno).lower():
            matched_ids.add(int(club["IdEntidadEquipo"]))

    # Equip principal (IdEquipo coincideix amb IdEntidadEquipo)
    for identidad in matched_ids:
        partidos = fvp_agenda_partidos(identidad, modalidad)
        for p in partidos:
            deno_comp = p.get("DenoComp")
            idc = comp_by_name.get(deno_comp)
            if idc is None:
                continue
            team_name = p.get("Eq1") if p.get("IdE1") == identidad else p.get("Eq2")
            if not team_name:
                continue
            key = (idc, team_name)
            if key in seen:
                continue
            seen.add(key)
            team = FedTeam(
                sidgad_id=None, short=team_name, full_name=team_name, logo=""
            )
            hits.append(
                ClubTeamHit(source=source, idc=idc, competition=deno_comp, temp=0, team=team)
            )

    # També equips amb IdEquipo diferent (femenins, categories, etc.)
    for comp in fvp_competiciones(modalidad):
        idc = comp["IdCompeticion"]
        for row in fvp_clasificacion_competicion(idc):
            entidad = row.get("IdEntidadEquipo")
            if entidad is not None:
                nombre = (row.get("NombreEquipo") or "").strip().lower()
                abrev = (row.get("NombreEquipoAbrev") or "").strip().lower()
                if (
                    entidad not in matched_ids
                    and (
                        q in nombre
                        or q in _strip_accents(nombre)
                        or q in abrev
                        or q in _strip_accents(abrev)
                    )
                ):
                    matched_ids.add(entidad)
            if entidad not in matched_ids:
                continue
            team_name = row.get("NombreEquipo")
            if not team_name:
                continue
            comp_name = row.get("DenoComp") or comp["DenoComp"]
            key = (idc, team_name)
            if key in seen:
                continue
            seen.add(key)
            short = row.get("NombreEquipoAbrev") or team_name
            team = FedTeam(
                sidgad_id=row.get("IdEntidadEquipo"),
                short=short,
                full_name=team_name,
                logo="",
            )
            hits.append(
                ClubTeamHit(
                    source=source,
                    idc=idc,
                    competition=comp_name,
                    temp=0,
                    team=team,
                )
            )

    return hits


def _parse_fvp_time(hora: str) -> time | None:
    if not hora or not hora.strip():
        return None
    try:
        h, m, s = hora.strip().split(":")
        return time(int(h), int(m), int(s) if s else 0)
    except Exception:
        return None


def _parse_fvp_jornada(nombre: str) -> int | None:
    m = re.search(r"(\d+)", nombre or "")
    return int(m.group(1)) if m else None


def import_fvp_competition(
    db: Session,
    season_id: int,
    idcompeticion: int,
    team_names: list[str],
    *,
    apply: bool = True,
    label: str | None = None,
) -> ImportReport:
    source = FVP_SOURCE
    report = ImportReport(0, 0, 0, 0, 0, [], source=source, idc=idcompeticion)
    team_names_set = {n.strip() for n in team_names if n}
    if not team_names_set:
        return report

    season = db.get(Season, season_id)
    club_id = season.club_id if season else None

    comp_label = label or f"FVP idc={idcompeticion}"
    team_map: dict[str, Any] = {}
    for name in team_names_set:
        team = ensure_team_for_fed(
            db,
            season_id,
            external_name=name,
            competition=comp_label,
            source=source,
        )
        team_map[name] = team

    partidos = fvp_calendario_competicion(idcompeticion)
    report.fetched = len(partidos)

    for p in partidos:
        local = p.get("EquipoLocal") or p.get("Eq1")
        visit = p.get("EquipoVisit") or p.get("Eq2")
        if not local or not visit:
            continue

        our_team_name: str | None = None
        is_home = False
        if local in team_names_set:
            our_team_name = local
            is_home = True
        elif visit in team_names_set:
            our_team_name = visit
            is_home = False
        else:
            continue

        team = team_map.get(our_team_name)
        if not team:
            continue

        opponent = visit if is_home else local
        match_date = date.fromisoformat(p["Fecha"]) if p.get("Fecha") else None
        start_time = _parse_fvp_time(p.get("Hora", ""))
        end_time: time | None = None
        jornada = _parse_fvp_jornada(p.get("NombreJornada", ""))
        place = (p.get("Instalacion") or "").strip()
        venue_id = None
        if is_home and club_id is not None:
            venue_id = _match_home_venue_id(
                db, club_id, place, team.home_venue_id if is_home else None
            )
        id_partido = p.get("IdPartido")
        ext_id = f"{source}:{idcompeticion}:{id_partido}"

        existing = (
            db.query(Match)
            .filter(
                Match.season_id == season_id,
                Match.team_id == team.id,
                Match.opponent == opponent,
                Match.is_home == is_home,
                Match.match_date == match_date,
                Match.start_time == start_time,
            )
            .first()
        )

        if existing and apply:
            if (
                existing.match_date != match_date
                or existing.start_time != start_time
                or existing.end_time != end_time
                or existing.jornada != jornada
                or existing.place_name != place
                or existing.venue_id != venue_id
            ):
                existing.match_date = match_date
                existing.start_time = start_time
                existing.end_time = end_time
                existing.jornada = jornada
                existing.place_name = place
                if venue_id is not None:
                    existing.venue_id = venue_id
                existing.official_date = match_date
                existing.official_start_time = start_time
                existing.official_end_time = end_time
                report.updated += 1
                report.rows.append(
                    ImportRow(
                        ext_id,
                        team.name,
                        opponent,
                        is_home,
                        match_date,
                        start_time,
                        jornada,
                        "update",
                        changed=True,
                    )
                )
            else:
                report.skipped += 1
                report.rows.append(
                    ImportRow(
                        ext_id,
                        team.name,
                        opponent,
                        is_home,
                        match_date,
                        start_time,
                        jornada,
                        "unchanged",
                    )
                )
        elif existing:
            report.skipped += 1
            report.rows.append(
                ImportRow(
                    ext_id,
                    team.name,
                    opponent,
                    is_home,
                    match_date,
                    start_time,
                    jornada,
                    "unchanged",
                )
            )
        else:
            if apply:
                db.add(
                    Match(
                        season_id=season_id,
                        team_id=team.id,
                        opponent=opponent,
                        is_home=is_home,
                        match_date=match_date,
                        start_time=start_time,
                        end_time=end_time,
                        jornada=jornada,
                        venue_id=venue_id,
                        place_name=place,
                        source=source,
                        external_id=ext_id,
                        official_date=match_date,
                        official_start_time=start_time,
                        official_end_time=end_time,
                    )
                )
                report.created += 1
            report.rows.append(
                ImportRow(
                    ext_id,
                    team.name,
                    opponent,
                    is_home,
                    match_date,
                    start_time,
                    jornada,
                    "create",
                )
            )

    if apply:
        src = (
            db.query(CompetitionSource)
            .filter(
                CompetitionSource.season_id == season_id,
                CompetitionSource.source == source,
                CompetitionSource.external_id == str(idcompeticion),
            )
            .first()
        )
        if not src:
            db.add(
                CompetitionSource(
                    season_id=season_id,
                    source=source,
                    external_id=str(idcompeticion),
                    label=comp_label,
                )
            )
        db.commit()
        matches = db.query(Match).filter(Match.season_id == season_id).all()
        trainings = (
            db.query(Training)
            .filter(
                Training.season_id == season_id,
                Training.is_draft.is_(False),
            )
            .all()
        )
        match_team = {m.id: m.team_id for m in matches}
        training_team = {t.id: t.team_id for t in trainings}
        conflicts = find_conflicts(db, season_id)
        persist_conflicts(db, season_id, conflicts, match_team, training_team)
    return report


def import_fvp_matches(
    db: Session,
    season_id: int,
    selections: list[tuple[int, str, str]],
) -> list[ImportReport]:
    by_idc: dict[int, list[str]] = {}
    labels: dict[int, str] = {}
    for idc, ext_name, comp_label in selections:
        by_idc.setdefault(idc, []).append(ext_name)
        labels[idc] = comp_label

    reports: list[ImportReport] = []
    for idc, names in by_idc.items():
        reports.append(
            import_fvp_competition(
                db,
                season_id,
                idc,
                names,
                apply=True,
                label=labels.get(idc),
            )
        )
    return reports
