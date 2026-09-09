"""Importación de partidos desde fuentes federativas (RFEP / FECAPA)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.conflicts import find_conflicts, persist_conflicts
from app.db import (
    CompetitionSource,
    FedMatchChange,
    Match,
    Season,
    Team,
    TeamExternalName,
    Training,
    Venue,
)
from app.calendar_week import match_duration_min
from app.sidgad import FEDERATIONS, SidgadClient, parse_calendar, parse_competition_list
from app.teams_meta import (
    BRANCH_BASE_FEMALE,
    BRANCH_SENIOR_FEMALE,
    infer_branch,
    team_branch,
)


@lru_cache(maxsize=128)
def _official_competition_name(source: str, idc: int) -> str | None:
    """Devuelve el nombre oficial de la competición según la federación."""
    try:
        for cid, name in list_federation_competitions(source):
            if cid == idc:
                return name
    except Exception:
        pass
    return None


@dataclass
class ImportRow:
    external_id: str
    team_name: str
    opponent: str
    is_home: bool
    match_date: date | None
    start_time: time | None
    jornada: int | None
    action: str  # create|update|skip_locked|skip_unmapped|unchanged
    detail: str = ""
    old_match_date: date | None = None
    old_start_time: time | None = None
    old_end_time: time | None = None
    old_venue_id: int | None = None
    changed: bool = False
    is_locked: bool = False


@dataclass
class ImportReport:
    fetched: int
    matched: int
    created: int
    updated: int
    skipped: int
    rows: list[ImportRow]
    error: str | None = None
    source: str = ""
    idc: int | None = None
    removed: int = 0


def _branch_compatible(team: Team, comp_branch: str) -> bool:
    """Evita assignar partits masculins a equips femenins o viceversa."""
    female_branches = {BRANCH_BASE_FEMALE, BRANCH_SENIOR_FEMALE}
    tb = team_branch(team)
    if tb in female_branches and comp_branch not in female_branches:
        return False
    if comp_branch in female_branches and tb not in female_branches:
        return False
    return True


def _norm(name: str) -> str:
    return " ".join((name or "").casefold().split())


def _parse_fecha(fecha: str | None, gamedate: str | None) -> date | None:
    if fecha:
        try:
            return datetime.strptime(fecha, "%d/%m/%Y").date()
        except ValueError:
            pass
    if gamedate and len(gamedate) == 8 and gamedate.isdigit():
        try:
            return datetime.strptime(gamedate, "%Y%m%d").date()
        except ValueError:
            pass
    return None


def _parse_hora(hora: str | None) -> time | None:
    if not hora:
        return None
    try:
        return datetime.strptime(hora, "%H:%M").time()
    except ValueError:
        try:
            return datetime.strptime(hora, "%H:%M:%S").time()
        except ValueError:
            return None


def _match_home_venue_id(
    db: Session,
    club_id: int,
    lugar: str | None,
    home_venue_id: int | None = None,
) -> int | None:
    """Assigna pista preferent del club/equip o la que coincideix pel nom."""
    venues = (
        db.query(Venue)
        .filter(Venue.club_id == club_id, Venue.allows_matches.is_(True))
        .order_by(Venue.preferred_for_matches.desc(), Venue.name)
        .all()
    )
    if not venues:
        all_venues = db.query(Venue).filter(Venue.club_id == club_id).all()
        if len(all_venues) == 1:
            return all_venues[0].id
        return None
    if len(venues) == 1:
        return venues[0].id
    if (lugar or "").strip():
        needle = _norm(lugar)
        for v in venues:
            vn = _norm(v.name)
            if vn == needle or needle in vn or vn in needle:
                return v.id
    if home_venue_id and any(v.id == home_venue_id for v in venues):
        return home_venue_id
    return venues[0].id


def team_alias_map(
    db: Session,
    season_id: int,
    source: str,
    *,
    prefer_category: str | None = None,
    only_external_names: list[str] | None = None,
    competition: str | None = None,
    label: str | None = None,
) -> dict[str, Team]:
    """Mapa nombre federativo → Team, estrictamente por vinculaciones.

    Si hay dos equipos con el mismo nombre (masc/fem), prefer_category
    o only_external_names acotan el de esta competición.

    `competition`: nombre oficial de la competición. Los alias que tienen
    competición propia solo casan si coincide con esta (o con `label`).
    Los alias sin competición (antiguos) solo se usan si no hay ninguno
    con competición concreta para ese nombre.
    """
    comp_names = {_norm(c) for c in (competition, label) if c}
    aliases = (
        db.query(TeamExternalName)
        .join(Team)
        .filter(Team.season_id == season_id, TeamExternalName.source == source)
        .all()
    )
    if only_external_names is not None:
        wanted = {_norm(n) for n in only_external_names}
        aliases = [a for a in aliases if _norm(a.external_name) in wanted]

    # 1) Alias con competición concreta y que coincida con esta competición
    scoped: dict[str, list[TeamExternalName]] = {}
    for a in aliases:
        if not (a.competition or "").strip():
            continue
        if _norm(a.competition) in comp_names:
            scoped.setdefault(_norm(a.external_name), []).append(a)

    # 2) Alias sin competición (legacy): solo si no hay scopado para ese nombre
    legacy: dict[str, list[TeamExternalName]] = {}
    for a in aliases:
        if (a.competition or "").strip():
            continue
        key = _norm(a.external_name)
        if key not in scoped:
            legacy.setdefault(key, []).append(a)

    out: dict[str, Team] = {}
    def pick(bucket: dict[str, list[TeamExternalName]], *, allow_ambiguous: bool = True) -> None:
        for key, lst in bucket.items():
            if len(lst) == 1:
                out[key] = lst[0].team
                continue
            # Si hay colisión, preferir el equipo cuya categoría interna
            # coincide con la competición actual
            if prefer_category:
                pref = _norm(prefer_category)
                for a in lst:
                    if _norm(a.team.category or "") == pref:
                        out[key] = a.team
                        break
            if key in out:
                continue
            if not allow_ambiguous:
                # Vinculación antigua sin competición y ambigua: no arriesgar
                # asignar a un equipo del sexo/categoría contrario.
                continue
            # Si no hay preferencia clara, quedarse con el primero
            out[key] = lst[0].team

    pick(scoped)
    # Alias sin competición: solo se usan si no hay scopado y son
    # inequívocos (un solo equipo para ese nombre federativo)
    pick(legacy, allow_ambiguous=False)
    return out


def fetch_official_teams(source: str, idc: int) -> list[str]:
    """Descarrega el calendari i retorna els noms d'equips únics."""
    client = SidgadClient(source)
    html = client.fetch_calendar(idc)
    calendar = parse_calendar(html, idc)
    names: set[str] = set()
    for cm in calendar:
        if cm.local:
            names.add(cm.local)
        if cm.visitante:
            names.add(cm.visitante)
    return sorted(names)


def import_competition(
    db: Session,
    season_id: int,
    source: str,
    idc: int,
    *,
    apply: bool = True,
    default_duration_min: int | None = None,
    label: str | None = None,
    only_external_names: list[str] | None = None,
) -> ImportReport:
    if source not in FEDERATIONS:
        return ImportReport(0, 0, 0, 0, 0, [], error=f"Fuente desconocida: {source}")

    client = SidgadClient(source)
    try:
        html = client.fetch_calendar(idc)
    except Exception as exc:  # noqa: BLE001
        return ImportReport(
            0, 0, 0, 0, 0, [], error=str(exc), source=source, idc=idc
        )

    try:
        calendar = parse_calendar(html, idc)
    except Exception as exc:  # noqa: BLE001
        return ImportReport(
            0, 0, 0, 0, 0, [], error=str(exc), source=source, idc=idc
        )

    # IDs externs que la federació publica ara mateix per aquesta competició
    current_ext_ids = {f"{source}:{cm.idc}:{cm.idp}" for cm in calendar}

    official_name = _official_competition_name(source, idc) or label
    aliases = team_alias_map(
        db,
        season_id,
        source,
        prefer_category=official_name,
        only_external_names=only_external_names,
        competition=official_name,
        label=label,
    )
    if not any(
        a.source == source
        for a in db.query(TeamExternalName)
        .join(Team)
        .filter(Team.season_id == season_id)
        .all()
    ):
        # Permitimos match por nombre interno, pero avisamos si no hay alias de esa fuente
        pass

    report = ImportReport(
        fetched=len(calendar),
        matched=0,
        created=0,
        updated=0,
        skipped=0,
        rows=[],
        source=source,
        idc=idc,
    )
    new_changes: list[FedMatchChange] = []
    seen_match_ids: set[int] = set()

    season = db.get(Season, season_id)
    club_id = season.club_id if season else None

    for cm in calendar:
        if apply:
            db.flush()
        local_n = _norm(cm.local)
        visit_n = _norm(cm.visitante)
        team = None
        opponent = None
        is_home = True
        matched_external_name = None
        if local_n in aliases:
            team = aliases[local_n]
            opponent = cm.visitante
            is_home = True
            matched_external_name = cm.local
        elif visit_n in aliases:
            team = aliases[visit_n]
            opponent = cm.local
            is_home = False
            matched_external_name = cm.visitante
        else:
            continue

        if not team or opponent is None:
            continue

        ext_id = f"{source}:{cm.idc}:{cm.idp}"

        # Última comprovació de seguretat: no assignar partits d'un
        # equip masculí a un equip femení (o al revés) per error d'àlies.
        comp_branch = infer_branch(name=official_name or label or "")
        if not _branch_compatible(team, comp_branch):
            if apply:
                # Si ja existia un partit importat d'aquesta jornada i ara
                # és incompatible (p. ex. OK Lliga masc a OK LLIGA FEM),
                # l'esborrem.
                bad_match = (
                    db.query(Match)
                    .filter(
                        Match.season_id == season_id,
                        Match.source == source,
                        Match.external_id == ext_id,
                    )
                    .first()
                )
                if (
                    bad_match
                    and not bad_match.locked
                    and not bad_match.is_changed_from_official
                ):
                    db.delete(bad_match)
                    report.removed += 1
            continue

        opponent = (opponent or "").strip() or "?"

        # Si l'àlies usat no té competició marcada, l'etiquetem amb la
        # competició oficial d'aquesta importació per evitar futures
        # fugides entre OK Lliga masc/fem o categories.
        if apply and matched_external_name:
            target_comp = official_name or label
            if target_comp:
                alias_to_tag = (
                    db.query(TeamExternalName)
                    .filter(
                        TeamExternalName.team_id == team.id,
                        TeamExternalName.source == source,
                        TeamExternalName.external_name == matched_external_name,
                    )
                    .filter(
                        or_(
                            TeamExternalName.competition.is_(None),
                            TeamExternalName.competition == "",
                        )
                    )
                    .first()
                )
                if alias_to_tag:
                    alias_to_tag.competition = target_comp

        report.matched += 1
        md = _parse_fecha(cm.fecha, cm.gamedate)
        st = _parse_hora(cm.hora)
        et = None
        if md and st:
            dur = (
                default_duration_min
                if default_duration_min is not None
                else match_duration_min(team.category)
            )
            et = (datetime.combine(md, st) + timedelta(minutes=dur)).time()
        place = (cm.lugar or "").strip() or None
        venue_id = None
        if is_home and club_id is not None:
            venue_id = _match_home_venue_id(
                db, club_id, place, team.home_venue_id if team else None
            )

        existing = (
            db.query(Match)
            .filter(
                Match.season_id == season_id,
                Match.source == source,
                Match.external_id == ext_id,
            )
            .first()
        )
        if not existing and team:
            # Fallback: la federación puede cambiar idp, hora o fecha.
            # En liga solo hay dos partidos contra el mismo rival: uno en
            # casa y otro fuera. Busquemos por equipo+rival+casa/fuera.
            existing = (
                db.query(Match)
                .filter(
                    Match.season_id == season_id,
                    Match.team_id == team.id,
                    Match.opponent == opponent,
                    Match.is_home == is_home,
                )
                .order_by(
                    Match.external_id.is_not(None).desc(),
                    Match.id.desc(),
                )
                .first()
            )
            if existing:
                existing.source = source
                existing.external_id = ext_id

        if existing:
            old_md = existing.match_date
            old_st = existing.start_time
            old_et = existing.end_time
            old_vid = existing.venue_id
            changed = (
                old_md != md
                or old_st != st
                or old_et != et
                or old_vid != venue_id
                or (existing.place_name or None) != place
                or existing.jornada != cm.jornada
            )
            if existing.locked and changed:
                if apply:
                    fc = FedMatchChange(
                        match_id=existing.id,
                        source=source,
                        old_match_date=old_md,
                        old_start_time=old_st,
                        old_end_time=old_et,
                        old_venue_id=old_vid,
                        new_match_date=md,
                        new_start_time=st,
                        new_end_time=et,
                        new_venue_id=venue_id,
                        is_locked=True,
                    )
                    db.add(fc)
                    new_changes.append(fc)
                report.skipped += 1
                report.rows.append(
                    ImportRow(
                        ext_id,
                        team.name,
                        opponent,
                        is_home,
                        md,
                        st,
                        cm.jornada,
                        "skip_locked",
                        "Partido bloqueado",
                        old_match_date=old_md,
                        old_start_time=old_st,
                        old_end_time=old_et,
                        old_venue_id=old_vid,
                        changed=True,
                        is_locked=True,
                    )
                )
                continue
            if not changed:
                report.rows.append(
                    ImportRow(
                        ext_id,
                        team.name,
                        opponent,
                        is_home,
                        md,
                        st,
                        cm.jornada,
                        "unchanged",
                        old_match_date=old_md,
                        old_start_time=old_st,
                        old_end_time=old_et,
                        old_venue_id=old_vid,
                        changed=False,
                    )
                )
                continue
            if apply:
                existing.team_id = team.id
                existing.opponent = opponent
                existing.is_home = is_home
                existing.match_date = md
                existing.start_time = st
                existing.end_time = et
                existing.jornada = cm.jornada
                existing.place_name = place
                if venue_id is not None:
                    existing.venue_id = venue_id
                # Reimportar = horario oficial de federación
                existing.set_official(md, st, et, venue_id)
                fc = FedMatchChange(
                    match_id=existing.id,
                    source=source,
                    old_match_date=old_md,
                    old_start_time=old_st,
                    old_end_time=old_et,
                    old_venue_id=old_vid,
                    new_match_date=md,
                    new_start_time=st,
                    new_end_time=et,
                    new_venue_id=venue_id,
                )
                db.add(fc)
                new_changes.append(fc)
            report.updated += 1
            report.rows.append(
                ImportRow(
                    ext_id,
                    team.name,
                    opponent,
                    is_home,
                    md,
                    st,
                    cm.jornada,
                    "update",
                    old_match_date=old_md,
                    old_start_time=old_st,
                    old_end_time=old_et,
                    old_venue_id=old_vid,
                    changed=True,
                )
            )
        else:
            if apply:
                same = (
                    db.query(Match)
                    .filter(
                        Match.season_id == season_id,
                        Match.team_id == team.id,
                        Match.opponent == opponent,
                        Match.is_home == is_home,
                        Match.match_date == md,
                        Match.start_time == st,
                    )
                    .first()
                )
                if not same:
                    db.add(
                        Match(
                            season_id=season_id,
                            team_id=team.id,
                            opponent=opponent,
                            is_home=is_home,
                            match_date=md,
                            start_time=st,
                            end_time=et,
                            jornada=cm.jornada,
                            venue_id=venue_id,
                            place_name=place,
                            source=source,
                            external_id=ext_id,
                            official_date=md,
                            official_start_time=st,
                            official_end_time=et,
                        )
                    )
                    report.created += 1
                else:
                    report.skipped += 1
            else:
                report.created += 1
            report.rows.append(
                ImportRow(
                    ext_id,
                    team.name,
                    opponent,
                    is_home,
                    md,
                    st,
                    cm.jornada,
                    "create",
                )
            )

    if apply:
        try:
            src = (
                db.query(CompetitionSource)
                .filter(
                    CompetitionSource.season_id == season_id,
                    CompetitionSource.source == source,
                    CompetitionSource.external_id == str(idc),
                )
                .first()
            )
            pretty = label or f"{source.upper()} idc={idc}"
            if not src:
                db.add(
                    CompetitionSource(
                        season_id=season_id,
                        source=source,
                        external_id=str(idc),
                        label=pretty,
                    )
                )
            else:
                src.label = pretty
            db.flush()

            # Partits que ja no figuren al calendari federatiu:
            # - sense canvis locals → s'eliminen (dades velles)
            # - bloquejats o moguts a mà → es marquen per revisió
            # Només si el calendari federatiu té contingut: una pàgina buida
            # o mal formada no ha d'esborrar mai partits existents.
            if only_external_names is None and calendar:
                prefix = f"{source}:{idc}:"
                # Equips que realment casen en aquesta competició
                cal_names: set[str] = set()
                for cm in calendar:
                    if cm.local:
                        cal_names.add(_norm(cm.local))
                    if cm.visitante:
                        cal_names.add(_norm(cm.visitante))
                expected_team_ids = {
                    aliases[n].id for n in cal_names if n in aliases
                }
                stale_conds = [
                    ~Match.external_id.in_(current_ext_ids or {""}),
                    # Si un partit encara és al calendari però cap àlies de
                    # la competició actual apunta al seu equip, vol dir que
                    # aquell partit està assignat a l'equip equivocat (p. ex.
                    # OK Lliga masc a OK Lliga fem) i s'ha d'eliminar.
                    ~Match.team_id.in_(expected_team_ids or {-1}),
                ]
                stale = (
                    db.query(Match)
                    .filter(
                        Match.season_id == season_id,
                        Match.source == source,
                        Match.external_id.like(f"{prefix}%"),
                        or_(*stale_conds),
                    )
                    .all()
                )
                delete_ids: list[int] = []
                for m in stale:
                    old_md = m.match_date
                    old_st = m.start_time
                    old_et = m.end_time
                    old_vid = m.venue_id
                    tname = m.team.name if m.team else ""
                    # Si encara és al calendari però apunta a un equip que
                    # no hi casa, és un partit importat amb àlies equivocat.
                    wrong_team = (
                        m.external_id in current_ext_ids
                        and m.team_id not in expected_team_ids
                    )
                    detail = (
                        "Equipo equivocado en esta competición"
                        if wrong_team
                        else "Ya no figura en la federación"
                    )
                    if m.locked or m.is_changed_from_official:
                        fc = FedMatchChange(
                            match_id=m.id,
                            source=source,
                            old_match_date=old_md,
                            old_start_time=old_st,
                            old_end_time=old_et,
                            old_venue_id=old_vid,
                            new_match_date=None,
                            new_start_time=None,
                            new_end_time=None,
                            new_venue_id=None,
                            is_locked=m.locked,
                        )
                        db.add(fc)
                        new_changes.append(fc)
                        report.skipped += 1
                        report.rows.append(
                            ImportRow(
                                m.external_id or "",
                                tname,
                                m.opponent,
                                m.is_home,
                                None,
                                None,
                                m.jornada,
                                "cancelled",
                                detail + " (revisar)",
                                old_match_date=old_md,
                                old_start_time=old_st,
                                old_end_time=old_et,
                                old_venue_id=old_vid,
                                changed=True,
                                is_locked=m.locked,
                            )
                        )
                    else:
                        delete_ids.append(m.id)
                        report.removed += 1
                        report.rows.append(
                            ImportRow(
                                m.external_id or "",
                                tname,
                                m.opponent,
                                m.is_home,
                                None,
                                None,
                                m.jornada,
                                "removed",
                                "Eliminado: " + detail,
                                old_match_date=old_md,
                                old_start_time=old_st,
                                old_end_time=old_et,
                                old_venue_id=old_vid,
                                changed=True,
                            )
                        )
                if delete_ids:
                    db.query(FedMatchChange).filter(
                        FedMatchChange.match_id.in_(delete_ids)
                    ).delete(synchronize_session=False)
                    db.query(Match).filter(Match.id.in_(delete_ids)).delete(
                        synchronize_session=False
                    )

            # Si un partido ha cambiado de idp u hora, fusionar duplicados
            # del mismo equipo+rival+fecha antes de recalcular conflictos.
            dedup_matches(db, season_id)

            conflicts = find_conflicts(db, season_id)
            if new_changes:
                match_ids = set()
                for c in conflicts:
                    match_ids.update(c.match_ids or [])
                for fc in new_changes:
                    count = sum(1 for mid in match_ids if mid == fc.match_id)
                    fc.has_conflict = count > 0
                    fc.conflict_count = count
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
            persist_conflicts(db, season_id, conflicts, match_team, training_team)
        except Exception as exc:  # noqa: BLE001
            report.error = str(exc)

    if report.matched == 0 and not report.error:
        report.error = (
            f"Se descargaron {report.fetched} partidos, pero ninguno coincide con tus "
            f"alias {source.upper()}. Revisa el nombre exacto en la federación."
        )

    return report


def import_rfep_competition(
    db: Session, season_id: int, idc: int, *, apply: bool = True
) -> ImportReport:
    return import_competition(db, season_id, "rfep", idc, apply=apply)


def import_fecapa_competition(
    db: Session,
    season_id: int,
    idc: int,
    *,
    apply: bool = True,
    label: str | None = None,
) -> ImportReport:
    return import_competition(
        db, season_id, "fecapa", idc, apply=apply, label=label
    )


def dedup_matches(db: Session, season_id: int) -> int:
    """Elimina partidos duplicados (mismo equipo, rival, casa/fuera, fecha)
    y también fusiona partidos cuya federación haya cambiado de hora/idp."""
    matches = db.query(Match).filter(Match.season_id == season_id).all()
    deleted_ids: set[int] = set()

    # Fase 1: mismo equipo, rival, casa/fuera (cualquier fecha u hora).
    # En liga solo hay dos partidos contra el mismo rival: casa y fuera.
    groups: dict[tuple[int, str, bool], list[Match]] = {}
    for m in matches:
        key = (m.team_id, m.opponent, m.is_home)
        groups.setdefault(key, []).append(m)

    to_delete: list[Match] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        # Se queda con: bloqueado > con external_id (federación) > id más alto
        group.sort(
            key=lambda m: (
                -int(m.locked),
                m.external_id is not None,
                m.id,
            ),
            reverse=True,
        )
        keep = group[0]
        for m in group[1:]:
            if m.locked and keep.locked:
                # Ambos bloqueados: no tocar, que el usuario decida
                continue
            # Si el descarte tiene datos más recientes de federación,
            # actualizar el conservado con ellos antes de borrar.
            if m.external_id and (not keep.external_id or m.id > keep.id):
                keep.source = m.source or keep.source
                keep.external_id = m.external_id or keep.external_id
                keep.start_time = m.start_time
                keep.end_time = m.end_time
                keep.venue_id = m.venue_id
                keep.place_name = m.place_name
                keep.jornada = m.jornada
                if m.match_date:
                    keep.match_date = m.match_date
                    keep.set_official(
                        m.match_date, m.start_time, m.end_time, m.venue_id
                    )
            to_delete.append(m)
            deleted_ids.add(m.id)

    if not to_delete:
        return 0

    delete_ids = [m.id for m in to_delete]
    db.query(FedMatchChange).filter(FedMatchChange.match_id.in_(delete_ids)).delete(
        synchronize_session=False
    )
    db.query(Match).filter(Match.id.in_(delete_ids)).delete(synchronize_session=False)

    conflicts = find_conflicts(db, season_id)
    matches = db.query(Match).filter(Match.season_id == season_id).all()
    trainings = (
        db.query(Training)
        .filter(Training.season_id == season_id, Training.is_draft.is_(False))
        .all()
    )
    match_team = {m.id: m.team_id for m in matches}
    training_team = {t.id: t.team_id for t in trainings}
    persist_conflicts(db, season_id, conflicts, match_team, training_team)
    db.commit()
    return len(to_delete)


def list_federation_competitions(source: str) -> list[tuple[int, str]]:
    client = SidgadClient(source)
    html = client.fetch_competition_list()
    return parse_competition_list(html)


def list_fecapa_competitions() -> list[tuple[int, str]]:
    return list_federation_competitions("fecapa")


def list_all_federation_competitions() -> list[tuple[str, int, str]]:
    """Devuelve [(source, idc, nombre), ...] de la temporada actual de cada federación."""
    out: list[tuple[str, int, str]] = []
    for source in FEDERATIONS:
        try:
            client = SidgadClient(source, sleep_s=0)
            html = client.fetch_competition_list()
            for idc, name in parse_competition_list(html):
                out.append((source, idc, name))
        except Exception:
            continue
    return out


def list_sources(db: Session, season_id: int) -> list[CompetitionSource]:
    return (
        db.query(CompetitionSource)
        .filter(CompetitionSource.season_id == season_id)
        .order_by(CompetitionSource.source, CompetitionSource.external_id)
        .all()
    )


def list_aliases(db: Session, season_id: int) -> list[TeamExternalName]:
    return (
        db.query(TeamExternalName)
        .options(joinedload(TeamExternalName.team))
        .join(Team)
        .filter(Team.season_id == season_id)
        .order_by(TeamExternalName.source, TeamExternalName.external_name)
        .all()
    )
