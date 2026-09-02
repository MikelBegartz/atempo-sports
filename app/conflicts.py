from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session, joinedload

from app.db import (
    Conflict as ConflictDB,
    Match,
    Person,
    PersonUnavailability,
    TeamMembership,
    Training,
    Venue,
    VenueAvailability,
)


_MSGS: dict[str, dict[str, str]] = {
    "ca": {
        "match_title": "partit vs {opponent}",
        "training_title": "entreno",
        "person": "{name} està a {team_a} ({title_a}) i {team_b} ({title_b}) el {date} ({time_a} / {time_b})",
        "venue": "{venue} ocupada per {team_a} ({title_a}) i {team_b} ({title_b}) el {date} ({time_a} / {time_b})",
        "venue_multi": "{venue} ocupada per {teams} el {date} ({times})",
        "venue_share": " — compartir permès",
        "not_before": "{team} ({title}): comença a les {start} però no pot abans de {not_before}",
        "not_after": "{team} ({title}): acaba a les {end} però ha d'acabar abans de {not_after}",
        "only_venue": "{team} ({title}): pista diferent de la permesa",
        "unavailable": "{name} no disponible ({why}) per a {team} ({title}) el {date} {time}",
        "venue_no_avail": "{venue} no té disponibilitat el {weekday} ({team} · {title})",
        "venue_out_of_hours": "{venue} fora d'horari disponible per a {team} ({title}) {time}",
        "coach_gap": "Atenció: {name} té {gap} min entre {team_a} ({title_a}) i {team_b} ({title_b}) el {date}. Assegura't que és temps suficient o ho movem a conflicte.",
        "weekday_0": "dl",
        "weekday_1": "dt",
        "weekday_2": "dx",
        "weekday_3": "dj",
        "weekday_4": "dv",
        "weekday_5": "ds",
        "weekday_6": "dg",
        "pista": "Pista",
        "block": "bloqueig",
        "all_day": "tot el dia",
        "month_1": "gen",
        "month_2": "feb",
        "month_3": "mar",
        "month_4": "abr",
        "month_5": "maig",
        "month_6": "jun",
        "month_7": "jul",
        "month_8": "ago",
        "month_9": "set",
        "month_10": "oct",
        "month_11": "nov",
        "month_12": "des",
    },
    "es": {
        "match_title": "partido vs {opponent}",
        "training_title": "entrenamiento",
        "person": "{name} está en {team_a} ({title_a}) y {team_b} ({title_b}) el {date} ({time_a} / {time_b})",
        "venue": "{venue} ocupada por {team_a} ({title_a}) y {team_b} ({title_b}) el {date} ({time_a} / {time_b})",
        "venue_share": " — compartir permitido",
        "not_before": "{team} ({title}): empieza a las {start} pero no puede antes de {not_before}",
        "not_after": "{team} ({title}): acaba a las {end} pero debe acabar antes de {not_after}",
        "only_venue": "{team} ({title}): pista diferente de la permitida",
        "unavailable": "{name} no disponible ({why}) para {team} ({title}) el {date} {time}",
        "venue_no_avail": "{venue} no tiene disponibilidad el {weekday} ({team} · {title})",
        "venue_out_of_hours": "{venue} fuera de horario disponible para {team} ({title}) {time}",
        "coach_gap": "Atención: {name} tiene {gap} min entre {team_a} ({title_a}) y {team_b} ({title_b}) el {date}. Asegúrate de que es tiempo suficiente o lo movemos a conflicto.",
        "weekday_0": "lun",
        "weekday_1": "mar",
        "weekday_2": "mié",
        "weekday_3": "jue",
        "weekday_4": "vie",
        "weekday_5": "sáb",
        "weekday_6": "dom",
        "pista": "Pista",
        "block": "bloqueo",
        "all_day": "todo el día",
        "month_1": "ene",
        "month_2": "feb",
        "month_3": "mar",
        "month_4": "abr",
        "month_5": "may",
        "month_6": "jun",
        "month_7": "jul",
        "month_8": "ago",
        "month_9": "sep",
        "month_10": "oct",
        "month_11": "nov",
        "month_12": "dic",
    },
    "pt": {
        "match_title": "partido vs {opponent}",
        "training_title": "treino",
        "person": "{name} está em {team_a} ({title_a}) e {team_b} ({title_b}) em {date} ({time_a} / {time_b})",
        "venue": "{venue} ocupada por {team_a} ({title_a}) e {team_b} ({title_b}) em {date} ({time_a} / {time_b})",
        "venue_share": " — partilha permitida",
        "not_before": "{team} ({title}): começa às {start} mas não pode antes de {not_before}",
        "not_after": "{team} ({title}): acaba às {end} mas tem de acabar antes de {not_after}",
        "only_venue": "{team} ({title}): pista diferente da permitida",
        "unavailable": "{name} não disponível ({why}) para {team} ({title}) em {date} {time}",
        "venue_no_avail": "{venue} não tem disponibilidade em {weekday} ({team} · {title})",
        "venue_out_of_hours": "{venue} fora do horário disponível para {team} ({title}) {time}",
        "coach_gap": "Atenção: {name} tem {gap} min entre {team_a} ({title_a}) e {team_b} ({title_b}) em {date}. Certifica-te de que é tempo suficiente ou movemos para conflito.",
        "weekday_0": "seg",
        "weekday_1": "ter",
        "weekday_2": "qua",
        "weekday_3": "qui",
        "weekday_4": "sex",
        "weekday_5": "sáb",
        "weekday_6": "dom",
        "pista": "Pista",
        "block": "bloqueio",
        "all_day": "todo o dia",
    },
    "fr": {
        "match_title": "match vs {opponent}",
        "training_title": "entraînement",
        "person": "{name} est dans {team_a} ({title_a}) et {team_b} ({title_b}) le {date} ({time_a} / {time_b})",
        "venue": "{venue} occupée par {team_a} ({title_a}) et {team_b} ({title_b}) le {date} ({time_a} / {time_b})",
        "venue_share": " — partage autorisé",
        "not_before": "{team} ({title}) : commence à {start} mais ne peut pas avant {not_before}",
        "not_after": "{team} ({title}) : finit à {end} mais doit finir avant {not_after}",
        "only_venue": "{team} ({title}) : piste différente de celle autorisée",
        "unavailable": "{name} non disponible ({why}) pour {team} ({title}) le {date} {time}",
        "venue_no_avail": "{venue} pas de disponibilité le {weekday} ({team} · {title})",
        "venue_out_of_hours": "{venue} hors horaire disponible pour {team} ({title}) {time}",
        "coach_gap": "Attention : {name} a {gap} min entre {team_a} ({title_a}) et {team_b} ({title_b}) le {date}. Assure-toi que c'est suffisant ou on le passe en conflit.",
        "weekday_0": "lun",
        "weekday_1": "mar",
        "weekday_2": "mer",
        "weekday_3": "jeu",
        "weekday_4": "ven",
        "weekday_5": "sam",
        "weekday_6": "dim",
        "pista": "Piste",
        "block": "blocage",
        "all_day": "toute la journée",
    },
    "de": {
        "match_title": "Spiel vs {opponent}",
        "training_title": "Training",
        "person": "{name} ist bei {team_a} ({title_a}) und {team_b} ({title_b}) am {date} ({time_a} / {time_b})",
        "venue": "{venue} belegt von {team_a} ({title_a}) und {team_b} ({title_b}) am {date} ({time_a} / {time_b})",
        "venue_share": " — Teilen erlaubt",
        "not_before": "{team} ({title}): beginnt um {start}, kann aber nicht vor {not_before}",
        "not_after": "{team} ({title}): endet um {end}, muss aber vor {not_after} enden",
        "only_venue": "{team} ({title}): andere Piste als erlaubt",
        "unavailable": "{name} nicht verfügbar ({why}) für {team} ({title}) am {date} {time}",
        "venue_no_avail": "{venue} keine Verfügbarkeit am {weekday} ({team} · {title})",
        "venue_out_of_hours": "{venue} außerhalb der Öffnungszeiten verfügbar für {team} ({title}) {time}",
        "coach_gap": "Achtung: {name} hat {gap} Min zwischen {team_a} ({title_a}) und {team_b} ({title_b}) am {date}. Stelle sicher, dass es reicht, oder wir verschieben es in Konflikt.",
        "weekday_0": "Mo",
        "weekday_1": "Di",
        "weekday_2": "Mi",
        "weekday_3": "Do",
        "weekday_4": "Fr",
        "weekday_5": "Sa",
        "weekday_6": "So",
        "pista": "Piste",
        "block": "Blockierung",
        "all_day": "ganzen Tag",
    },
    "it": {
        "match_title": "partita vs {opponent}",
        "training_title": "allenamento",
        "person": "{name} è in {team_a} ({title_a}) e {team_b} ({title_b}) il {date} ({time_a} / {time_b})",
        "venue": "{venue} occupata da {team_a} ({title_a}) e {team_b} ({title_b}) il {date} ({time_a} / {time_b})",
        "venue_share": " — condivisione permessa",
        "not_before": "{team} ({title}): inizia alle {start} ma non può prima di {not_before}",
        "not_after": "{team} ({title}): finisce alle {end} ma deve finire prima di {not_after}",
        "only_venue": "{team} ({title}): pista diversa da quella permessa",
        "unavailable": "{name} non disponibile ({why}) per {team} ({title}) il {date} {time}",
        "venue_no_avail": "{venue} nessuna disponibilità il {weekday} ({team} · {title})",
        "venue_out_of_hours": "{venue} fuori orario disponibile per {team} ({title}) {time}",
        "coach_gap": "Attenzione: {name} ha {gap} min tra {team_a} ({title_a}) e {team_b} ({title_b}) il {date}. Assicurati che sia tempo sufficiente o lo spostiamo in conflitto.",
        "weekday_0": "lun",
        "weekday_1": "mar",
        "weekday_2": "mer",
        "weekday_3": "gio",
        "weekday_4": "ven",
        "weekday_5": "sab",
        "weekday_6": "dom",
        "pista": "Pista",
        "block": "blocco",
        "all_day": "tutto il giorno",
    },
}


def _t(lang: str, key: str, **kwargs) -> str:
    return (_MSGS.get(lang, _MSGS["ca"]).get(key) or _MSGS["ca"][key]).format(**kwargs)


def _month_short(lang: str, month: int) -> str:
    return _t(lang, f"month_{month}")


def _weekday_short(lang: str, weekday: int) -> str:
    return _t(lang, f"weekday_{weekday}")



@dataclass
class Conflict:
    kind: str  # person|venue|category
    severity: str  # hard|soft
    message: str
    match_ids: list[int] = field(default_factory=list)
    training_ids: list[int] = field(default_factory=list)
    person_id: int | None = None
    d: date | None = None
    ignored: bool = False
    id: int | None = None


@dataclass
class _Occ:
    etype: str  # match|training
    eid: int
    team_id: int
    team_name: str
    title: str
    d: date
    start: time
    end: time
    venue_id: int | None
    share: bool
    team: object  # Team ORM for category rules
    is_home: bool | None = None  # per partits: True=local, False=fora; entrenos None (casa)
    opponent: str | None = None  # nom del rival, només per partits
    training_group_id: int | None = None


def _overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return a_start < b_end and b_start < a_end


def people_for_team(db: Session, team_id: int) -> list[Person]:
    rows = (
        db.query(TeamMembership)
        .options(joinedload(TeamMembership.person))
        .filter(TeamMembership.team_id == team_id)
        .all()
    )
    return [r.person for r in rows]


def _match_to_occ(m: Match, override: dict | None, lang: str) -> _Occ | None:
    md = m.match_date
    st = m.start_time
    et = m.end_time
    vid = m.venue_id
    if override:
        md = override.get("match_date", md)
        st = override.get("start_time", st)
        et = override.get("end_time", et)
        if "venue_id" in override:
            vid = override.get("venue_id")
    if md is None or st is None or m.team is None:
        return None
    if et is None:
        et = (datetime.combine(md, st) + timedelta(minutes=90)).time()
    share = bool(m.venue.allows_share_default) if m.venue else False
    return _Occ(
        etype="match",
        eid=m.id,
        team_id=m.team_id,
        team_name=m.team.name,
        title=_t(lang, "match_title", opponent=m.opponent),
        d=md,
        start=st,
        end=et,
        venue_id=vid if m.is_home else None,
        share=share,
        team=m.team,
        is_home=m.is_home if m.is_home is not None else True,
        opponent=m.opponent or None,
    )


def _training_to_occ(t: Training, lang: str) -> _Occ | None:
    if (
        t.team is None
        or t.session_date is None
        or t.start_time is None
        or t.end_time is None
    ):
        return None
    share = t.allows_share or (
        bool(t.venue.allows_share_default) if t.venue else False
    )
    return _Occ(
        etype="training",
        eid=t.id,
        team_id=t.team_id,
        team_name=t.team.name,
        title=_t(lang, "training_title"),
        d=t.session_date,
        start=t.start_time,
        end=t.end_time,
        venue_id=t.venue_id,
        share=share,
        team=t.team,
        is_home=None,
        opponent=None,
        training_group_id=t.training_group_id,
    )


def _ids(a: _Occ, b: _Occ | None = None) -> tuple[list[int], list[int], date]:
    mids: list[int] = []
    tids: list[int] = []
    for x in ([a, b] if b else [a]):
        if x.etype == "match":
            mids.append(x.eid)
        else:
            tids.append(x.eid)
    return mids, tids, a.d


def find_conflicts(
    db: Session,
    season_id: int,
    override: dict[int, dict] | None = None,
    *,
    lang: str | None = None,
) -> list[Conflict]:
    """Detecta conflictos entre partidos y entrenos. override: match_id → campos."""
    lang = lang or "ca"
    override = override or {}
    matches = (
        db.query(Match)
        .options(joinedload(Match.team), joinedload(Match.venue))
        .filter(Match.season_id == season_id)
        .all()
    )
    trainings = (
        db.query(Training)
        .options(joinedload(Training.team), joinedload(Training.venue))
        .filter(
            Training.season_id == season_id,
            Training.is_draft.is_(False),
        )
        .all()
    )

    occs: list[_Occ] = []
    for m in matches:
        o = _match_to_occ(m, override.get(m.id), lang)
        if o:
            occs.append(o)
    for t in trainings:
        o = _training_to_occ(t, lang)
        if o:
            occs.append(o)

    venue_ids = {o.venue_id for o in occs if o.venue_id is not None}
    venues_by_id = {
        v.id: v for v in db.query(Venue).filter(Venue.id.in_(venue_ids)).all()
    } if venue_ids else {}

    # Actualizar share desde venue si hace falta
    for o in occs:
        if o.venue_id and o.venue_id in venues_by_id and o.etype == "match":
            o.share = bool(venues_by_id[o.venue_id].allows_share_default)

    conflicts: list[Conflict] = []
    people_cache: dict[int, list[Person]] = {}

    def people(team_id: int) -> list[Person]:
        if team_id not in people_cache:
            people_cache[team_id] = people_for_team(db, team_id)
        return people_cache[team_id]

    # Person overlaps
    for i, a in enumerate(occs):
        people_a = {p.id: p for p in people(a.team_id)}
        for b in occs[i + 1 :]:
            if a.d != b.d or not _overlaps(a.start, a.end, b.start, b.end):
                continue
            people_b = {p.id: p for p in people(b.team_id)}
            shared = set(people_a) & set(people_b)
            if not shared:
                continue
            # Si els dos són entrenaments del mateix grup o a la mateixa pista, no és conflicte
            if (
                a.etype == "training"
                and b.etype == "training"
                and a.training_group_id
                and a.training_group_id == b.training_group_id
            ):
                continue
            if (
                a.etype == "training"
                and b.etype == "training"
                and a.venue_id == b.venue_id
            ):
                continue
            # Solapament entre entrenaments = avís (soft); la resta = dur (hard)
            severity = (
                "soft"
                if a.etype == "training" and b.etype == "training"
                else "hard"
            )
            for pid in shared:
                p = people_a[pid]
                mids, tids, d = _ids(a, b)
                conflicts.append(
                    Conflict(
                        kind="person",
                        severity=severity,
                        message=_t(
                            lang,
                            "person",
                            name=p.full_name,
                            team_a=a.team_name,
                            title_a=a.title,
                            team_b=b.team_name,
                            title_b=b.title,
                            date=a.d.isoformat(),
                            time_a=f"{a.start.strftime('%H:%M')}–{a.end.strftime('%H:%M')}",
                            time_b=f"{b.start.strftime('%H:%M')}–{b.end.strftime('%H:%M')}",
                        ),
                        match_ids=mids, d=d,
                        training_ids=tids,
                        person_id=pid,
                    )
                )

    # Venue overlaps
    with_venue = [o for o in occs if o.venue_id is not None]
    by_venue_day: dict[tuple[int, date], list[_Occ]] = {}
    for o in with_venue:
        by_venue_day.setdefault((o.venue_id, o.d), []).append(o)
    for (venue_id, day), v_occs in by_venue_day.items():
        v_occs.sort(key=lambda o: (o.start, o.end))
        clusters: list[list[_Occ]] = []
        cluster_ends: list[time] = []
        for o in v_occs:
            if not clusters or o.start >= cluster_ends[-1]:
                clusters.append([o])
                cluster_ends.append(o.end)
            else:
                clusters[-1].append(o)
                if o.end > cluster_ends[-1]:
                    cluster_ends[-1] = o.end
        for cluster in clusters:
            if len(cluster) < 2:
                continue
            all_training = all(o.etype == "training" for o in cluster)
            group_ids = {o.training_group_id for o in cluster}
            if (
                all_training
                and len(group_ids) == 1
                and next(iter(group_ids)) is not None
            ):
                continue
            if all_training and len({(o.start, o.end) for o in cluster}) == 1:
                continue
            share_ok = all(o.share for o in cluster)
            venue = venues_by_id.get(venue_id)
            venue_name = venue.name if venue else f"pista #{venue_id}"
            team_names = list(dict.fromkeys([o.team_name for o in cluster]))
            times = list(dict.fromkeys([f"{o.start.strftime('%H:%M')}–{o.end.strftime('%H:%M')}" for o in cluster]))
            if len(cluster) == 2:
                a, b = cluster[0], cluster[1]
                message = _t(
                    lang,
                    "venue",
                    venue=venue_name,
                    team_a=a.team_name,
                    title_a=a.title,
                    team_b=b.team_name,
                    title_b=b.title,
                    date=day.isoformat(),
                    time_a=f"{a.start.strftime('%H:%M')}–{a.end.strftime('%H:%M')}",
                    time_b=f"{b.start.strftime('%H:%M')}–{b.end.strftime('%H:%M')}",
                )
            else:
                message = _t(
                    lang,
                    "venue_multi",
                    venue=venue_name,
                    teams=", ".join(team_names),
                    date=day.isoformat(),
                    times=", ".join(times),
                )
            if share_ok:
                message += _t(lang, "venue_share")
            mids: list[int] = []
            tids: list[int] = []
            for o in cluster:
                if o.etype == "match":
                    mids.append(o.eid)
                else:
                    tids.append(o.eid)
            conflicts.append(
                Conflict(
                    kind="venue",
                    severity="soft" if share_ok else "hard",
                    message=message,
                    match_ids=mids, d=day,
                    training_ids=tids,
                )
            )

    # Category / team time restrictions
    for o in occs:
        t = o.team
        if t.not_before and o.start < t.not_before:
            mids, tids, d = _ids(o)
            conflicts.append(
                Conflict(
                    kind="category",
                    severity="hard",
                    message=_t(
                        lang,
                        "not_before",
                        team=o.team_name,
                        title=o.title,
                        start=o.start.strftime("%H:%M"),
                        not_before=t.not_before.strftime("%H:%M"),
                    ),
                    match_ids=mids, d=d,
                    training_ids=tids,
                )
            )
        if t.not_after and o.end > t.not_after:
            mids, tids, d = _ids(o)
            conflicts.append(
                Conflict(
                    kind="category",
                    severity="hard",
                    message=_t(
                        lang,
                        "not_after",
                        team=o.team_name,
                        title=o.title,
                        end=o.end.strftime("%H:%M"),
                        not_after=t.not_after.strftime("%H:%M"),
                    ),
                    match_ids=mids, d=d,
                    training_ids=tids,
                )
            )
        if t.only_venue_id and o.venue_id and o.venue_id != t.only_venue_id:
            mids, tids, d = _ids(o)
            conflicts.append(
                Conflict(
                    kind="category",
                    severity="hard",
                    message=_t(
                        lang,
                        "only_venue",
                        team=o.team_name,
                        title=o.title,
                    ),
                    match_ids=mids, d=d,
                    training_ids=tids,
                )
            )

    # Person unavailability
    person_ids = {p.id for o in occs for p in people(o.team_id)}
    unavs = []
    if person_ids:
        unavs = (
            db.query(PersonUnavailability)
            .filter(PersonUnavailability.person_id.in_(person_ids))
            .all()
        )
    unav_by_person: dict[int, list[PersonUnavailability]] = {}
    for u in unavs:
        unav_by_person.setdefault(u.person_id, []).append(u)

    for o in occs:
        for p in people(o.team_id):
            for u in unav_by_person.get(p.id, []):
                if not _unavailability_hits(u, o.d, o.start, o.end):
                    continue
                why = u.reason or _unavailability_label(u, lang)
                mids, tids, d = _ids(o)
                conflicts.append(
                    Conflict(
                        kind="person",
                        severity="hard",
                        message=_t(
                            lang,
                            "unavailable",
                            name=p.full_name,
                            why=why,
                            team=o.team_name,
                            title=o.title,
                            date=o.d.isoformat(),
                            time=f"{o.start.strftime('%H:%M')}–{o.end.strftime('%H:%M')}",
                        ),
                        match_ids=mids, d=d,
                        training_ids=tids,
                        person_id=p.id,
                    )
                )

    # Disponibilidad de pista (si hay franjas definidas)
    avails_by_venue: dict[int, list[VenueAvailability]] = {}
    if venue_ids:
        for a in (
            db.query(VenueAvailability)
            .filter(VenueAvailability.venue_id.in_(venue_ids))
            .all()
        ):
            avails_by_venue.setdefault(a.venue_id, []).append(a)

    for o in occs:
        if o.venue_id is None:
            continue
        avails = avails_by_venue.get(o.venue_id) or []
        day_avails = [a for a in avails if a.weekday == o.d.weekday()]
        if not day_avails:
            venue = venues_by_id.get(o.venue_id)
            mids, tids, d = _ids(o)
            conflicts.append(
                Conflict(
                    kind="venue",
                    severity="hard",
                    message=_t(
                        lang,
                        "venue_no_avail",
                        venue=venue.name if venue else _t(lang, "pista"),
                        weekday=_weekday_short(lang, o.d.weekday()),
                        team=o.team_name,
                        title=o.title,
                    ),
                    match_ids=mids, d=d,
                    training_ids=tids,
                )
            )
            continue
        covered = any(
            a.start_time <= o.start and o.end <= a.end_time for a in day_avails
        )
        if not covered:
            venue = venues_by_id.get(o.venue_id)
            mids, tids, d = _ids(o)
            conflicts.append(
                Conflict(
                    kind="venue",
                    severity="hard",
                    message=_t(
                        lang,
                        "venue_out_of_hours",
                        venue=venue.name if venue else _t(lang, "pista"),
                        team=o.team_name,
                        title=o.title,
                        time=f"{o.start.strftime('%H:%M')}–{o.end.strftime('%H:%M')}",
                    ),
                    match_ids=mids, d=d,
                    training_ids=tids,
                )
            )

    # Preferencia soft: entrenadors amb canvi de població (casa / fora) el mateix dia
    def _needs_travel(a: _Occ, b: _Occ) -> bool:
        """Hi ha desplaçament si canviem de població: casa→fora, fora→casa o fora→fora amb rival diferent."""
        home_a = a.etype == "training" or bool(a.is_home)
        home_b = b.etype == "training" or bool(b.is_home)
        if home_a != home_b:
            return True
        # tots dos a casa o tots dos fora
        if home_a and home_b:
            return False
        # tots dos fora: només és desplaçament si són rivals diferents
        return a.opponent != b.opponent

    coach_events: dict[int, list[tuple[_Occ, Person]]] = {}
    for o in occs:
        for p in people(o.team_id):
            if not p.is_coach:
                continue
            coach_events.setdefault(p.id, []).append((o, p))

    for _pid, items in coach_events.items():
        items.sort(key=lambda x: (x[0].d, x[0].start, x[0].end))
        by_day: dict[date, list[tuple[_Occ, Person]]] = {}
        for o, p in items:
            by_day.setdefault(o.d, []).append((o, p))
        for day, day_items in by_day.items():
            if len(day_items) < 2:
                continue
            for i in range(len(day_items) - 1):
                a, p = day_items[i]
                b, _ = day_items[i + 1]
                gap = _minutes_between(a.end, b.start)
                if gap is None or gap <= 30:
                    continue
                if not _needs_travel(a, b):
                    continue
                # hueco > 30 min entre sesiones del mismo entrenador con desplaçament
                mids, tids, d = _ids(a, b)
                conflicts.append(
                    Conflict(
                        kind="person",
                        severity="soft",
                        message=_t(
                            lang,
                            "coach_gap",
                            name=p.full_name,
                            gap=gap,
                            team_a=a.team_name,
                            title_a=a.title,
                            team_b=b.team_name,
                            title_b=b.title,
                            date=day.isoformat(),
                        ),
                        match_ids=mids, d=d,
                        training_ids=tids,
                        person_id=p.id,
                    )
                )

    return conflicts


def _minutes_between(a_end: time, b_start: time) -> int | None:
    if b_start < a_end:
        return None  # solape (ya cubierto como hard)
    return (b_start.hour * 60 + b_start.minute) - (a_end.hour * 60 + a_end.minute)


def _unavailability_label(u: PersonUnavailability, lang: str) -> str:
    if u.specific_date:
        base = u.specific_date.isoformat()
    elif u.weekday is not None:
        base = f"cada {_t(lang, f'weekday_{u.weekday}')}"
    else:
        base = _t(lang, "block")
    if u.start_time and u.end_time:
        return (
            f"{base} {u.start_time.strftime('%H:%M')}–{u.end_time.strftime('%H:%M')}"
        )
    return f"{base} ({_t(lang, 'all_day')})"


def _unavailability_hits(
    u: PersonUnavailability, m_date: date, m_start: time, m_end: time
) -> bool:
    if u.specific_date is not None:
        if m_date != u.specific_date:
            return False
    elif u.weekday is not None:
        if m_date.weekday() != u.weekday:
            return False
    else:
        return False

    if u.start_time is None and u.end_time is None:
        return True
    u_start = u.start_time or time(0, 0)
    u_end = u.end_time or time(23, 59)
    return _overlaps(m_start, m_end, u_start, u_end)


def hard_conflicts(
    db: Session, season_id: int, override: dict[int, dict] | None = None
) -> list[Conflict]:
    return [c for c in find_conflicts(db, season_id, override) if c.severity == "hard"]


def conflict_key(c: Conflict, match_team: dict, training_team: dict) -> str:
    teams = {match_team.get(mid) for mid in c.match_ids} | {training_team.get(tid) for tid in c.training_ids}
    return f"{c.kind}-{c.person_id or 'x'}-{c.severity}-{'-'.join(str(t) for t in sorted(teams) if t is not None)}"


def _is_ignored_on(row: ConflictDB, d: date | None) -> bool:
    if row.ignored:
        return True
    if not d:
        return False
    return any(i.ignored_date == d for i in row.ignored_dates)


def persist_conflicts(
    db: Session,
    season_id: int,
    conflicts: list[Conflict],
    match_team: dict,
    training_team: dict,
) -> None:
    """Persisteix i identifica els conflictes per obtenir IDs estables."""

    existing = {
        c.conflict_key: c
        for c in db.query(ConflictDB).filter(
            ConflictDB.season_id == season_id,
        ).all()
    }
    seen: set[str] = set()
    seen_rows: dict[str, ConflictDB] = {}
    for c in conflicts:
        key = conflict_key(c, match_team, training_team)
        if key in seen:
            c.id = seen_rows[key].id
            c.ignored = _is_ignored_on(seen_rows[key], c.d)
            continue
        seen.add(key)
        if key in existing:
            row = existing[key]
            seen_rows[key] = row
            c.id = row.id
            c.ignored = _is_ignored_on(row, c.d)
            if row.message != c.message:
                row.message = c.message
            if row.severity != c.severity:
                row.severity = c.severity
            if row.resolved_at:
                row.resolved_at = None
            continue
        row = ConflictDB(
            season_id=season_id,
            conflict_key=key,
            kind=c.kind,
            severity=c.severity,
            person_id=c.person_id,
            message=c.message,
        )
        db.add(row)
        db.flush()
        c.id = row.id
        seen_rows[key] = row
    for key, row in existing.items():
        if key not in seen and not row.ignored:
            row.resolved_at = datetime.utcnow()
    db.commit()
