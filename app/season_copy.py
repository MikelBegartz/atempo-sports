"""Copiar estructura de una temporada a otra."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.db import (
    Person,
    PersonUnavailability,
    Season,
    Team,
    TeamExternalName,
    TeamMembership,
)


def copy_season(
    db: Session,
    source_season_id: int,
    new_name: str,
    *,
    copy_unavailability: bool = True,
    copy_aliases: bool = True,
) -> Season:
    src = (
        db.query(Season)
        .options(joinedload(Season.club))
        .filter(Season.id == source_season_id)
        .first()
    )
    if not src:
        raise ValueError("Temporada origen no encontrada")

    name = new_name.strip()
    if not name:
        raise ValueError("Nombre de temporada vacío")

    exists = (
        db.query(Season)
        .filter(Season.club_id == src.club_id, Season.name == name)
        .first()
    )
    if exists:
        raise ValueError(f"Ya existe la temporada {name}")

    # Desactivar otras del club
    for s in db.query(Season).filter(Season.club_id == src.club_id).all():
        s.is_active = False

    dst = Season(club_id=src.club_id, name=name, is_active=True)
    db.add(dst)
    db.flush()

    # Personas
    person_map: dict[int, int] = {}
    for p in db.query(Person).filter(Person.season_id == src.id).all():
        np = Person(
            season_id=dst.id,
            full_name=p.full_name,
            is_player=p.is_player,
            is_coach=p.is_coach,
            notes=p.notes,
        )
        db.add(np)
        db.flush()
        person_map[p.id] = np.id

        if copy_unavailability:
            for u in (
                db.query(PersonUnavailability)
                .filter(PersonUnavailability.person_id == p.id)
                .all()
            ):
                db.add(
                    PersonUnavailability(
                        person_id=np.id,
                        weekday=u.weekday,
                        specific_date=u.specific_date,
                        start_time=u.start_time,
                        end_time=u.end_time,
                        reason=u.reason,
                    )
                )

    # Equipos
    team_map: dict[int, int] = {}
    for t in db.query(Team).filter(Team.season_id == src.id).all():
        nt = Team(
            season_id=dst.id,
            name=t.name,
            category=t.category,
            branch=getattr(t, "branch", None),
            only_venue_id=t.only_venue_id,
            not_before=t.not_before,
            not_after=t.not_after,
            immovable=t.immovable,
        )
        db.add(nt)
        db.flush()
        team_map[t.id] = nt.id

        if copy_aliases:
            for a in (
                db.query(TeamExternalName)
                .filter(TeamExternalName.team_id == t.id)
                .all()
            ):
                db.add(
                    TeamExternalName(
                        team_id=nt.id,
                        source=a.source,
                        external_name=a.external_name,
                    )
                )

    # Vínculos
    for m in (
        db.query(TeamMembership)
        .join(Team)
        .filter(Team.season_id == src.id)
        .all()
    ):
        if m.team_id in team_map and m.person_id in person_map:
            db.add(
                TeamMembership(
                    team_id=team_map[m.team_id],
                    person_id=person_map[m.person_id],
                    role=m.role,
                )
            )

    db.commit()
    db.refresh(dst)
    return dst
