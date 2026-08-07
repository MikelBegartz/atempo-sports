"""Carga datos demo (Mataró) con un choque intencionado para probar el motor."""

from __future__ import annotations

from datetime import date, time, timedelta

from app.auth import ensure_mataro_access, hash_password
from app.settings import demo_password
from app.db import (
    Club,
    CompetitionSource,
    Match,
    Person,
    Season,
    SessionLocal,
    Team,
    TeamExternalName,
    TeamMembership,
    Venue,
    VenueAvailability,
    VenueMatchAvailability,
    default_end_date_for_season,
    engine,
    init_db,
)


def seed() -> None:
    print("[seed] abans SessionLocal")
    db = SessionLocal()
    print("[seed] despres SessionLocal")
    try:
        print("[seed] abans query")
        existing = db.query(Club).filter(Club.name == "CH Mataró").first()
        print(f"[seed] existing: {existing}")
        if existing:
            ensure_mataro_access(db)
            pwd = demo_password()
            if pwd:
                print(f"Seed ya aplicado (CH Mataró existe). Acceso: mataro / {pwd}")
            else:
                print(
                    "Seed ya aplicado (CH Mataró existe). "
                    "Demo sense clau automàtica (posa ATEMPO_DEMO_PASSWORD o usa /admin)."
                )
            return

        pwd = demo_password() or "mataro"
        print(f"[seed] creant club amb pwd: {pwd}")
        club = Club(
            name="CH Mataró",
            short_name="Mataró",
            slug="mataro",
            password_hash=hash_password(pwd),
        )
        db.add(club)
        db.flush()
        print("[seed] club flush")

        season = Season(
            club_id=club.id,
            name="2026/27",
            is_active=True,
            end_date=default_end_date_for_season("2026/27"),
        )
        db.add(season)
        db.flush()

        p1 = Venue(club_id=club.id, name="Pista 1", allows_share_default=False, allows_matches=True)
        p2 = Venue(club_id=club.id, name="Pista 2", allows_share_default=True, allows_matches=True)
        p3 = Venue(club_id=club.id, name="Pista 3", allows_share_default=False, allows_matches=False)
        db.add_all([p1, p2, p3])
        db.flush()
        print("[seed] venues flush")

        for weekday in range(7):
            db.add(
                VenueAvailability(
                    venue_id=p1.id,
                    weekday=weekday,
                    start_time=time(17, 0) if weekday < 5 else time(9, 0),
                    end_time=time(22, 0) if weekday < 5 else time(14, 0),
                )
            )
            db.add(
                VenueAvailability(
                    venue_id=p2.id,
                    weekday=weekday,
                    start_time=time(18, 0) if weekday < 5 else time(9, 0),
                    end_time=time(21, 30) if weekday < 5 else time(13, 0),
                )
            )
            if weekday >= 5:
                db.add(
                    VenueAvailability(
                        venue_id=p3.id,
                        weekday=weekday,
                        start_time=time(9, 0),
                        end_time=time(20, 0),
                    )
                )
            if weekday >= 5 and p1.allows_matches:
                db.add(
                    VenueMatchAvailability(
                        venue_id=p1.id,
                        weekday=weekday,
                        start_time=time(9, 0),
                        end_time=time(14, 0),
                    )
                )
            if weekday >= 5 and p2.allows_matches:
                db.add(
                    VenueMatchAvailability(
                        venue_id=p2.id,
                        weekday=weekday,
                        start_time=time(9, 0),
                        end_time=time(13, 0),
                    )
                )

        senior = Team(
            season_id=season.id,
            name="Senior A",
            category="Senior",
            branch="senior_male",
            not_before=time(18, 0),
        )
        fem = Team(
            season_id=season.id,
            name="Sènior",
            category="Femení",
            branch="senior_female",
        )
        mix = Team(
            season_id=season.id,
            name="Juvenil",
            category="Mixte",
            branch="base_mixed",
        )
        alev = Team(
            season_id=season.id, name="Aleví A", category="Aleví", branch="base_mixed"
        )
        db.add_all([senior, fem, mix, alev])
        db.flush()

        coach = Person(
            season_id=season.id,
            full_name="Jordi Coach",
            is_player=False,
            is_coach=True,
        )
        maria = Person(
            season_id=season.id,
            full_name="Maria Refuerzo",
            is_player=True,
            is_coach=False,
        )
        pau = Person(
            season_id=season.id,
            full_name="Pau Senior",
            is_player=True,
            is_coach=False,
        )
        db.add_all([coach, maria, pau])
        db.flush()

        db.add_all(
            [
                TeamMembership(team_id=senior.id, person_id=coach.id, role="coach"),
                TeamMembership(team_id=alev.id, person_id=coach.id, role="coach"),
                TeamMembership(team_id=fem.id, person_id=maria.id, role="player"),
                TeamMembership(team_id=mix.id, person_id=maria.id, role="reinforce"),
                TeamMembership(team_id=senior.id, person_id=pau.id, role="player"),
            ]
        )

        d1 = date.today() + timedelta(days=5)
        d2 = date.today() + timedelta(days=6)
        d3 = date.today() + timedelta(days=12)

        db.add(
            Match(
                season_id=season.id,
                team_id=senior.id,
                opponent="Vic",
                is_home=True,
                match_date=d1,
                start_time=time(20, 0),
                end_time=time(21, 30),
                venue_id=p1.id,
                jornada=12,
                source="manual",
            )
        )
        db.add(
            Match(
                season_id=season.id,
                team_id=alev.id,
                opponent="Molins",
                is_home=True,
                match_date=d1,
                start_time=time(19, 30),
                end_time=time(20, 45),
                venue_id=p3.id,
                jornada=12,
                source="manual",
            )
        )
        db.add(
            Match(
                season_id=season.id,
                team_id=fem.id,
                opponent="SHUM",
                is_home=True,
                match_date=d2,
                start_time=time(11, 0),
                end_time=time(12, 15),
                venue_id=p1.id,
                jornada=12,
                source="manual",
            )
        )
        db.add(
            Match(
                season_id=season.id,
                team_id=mix.id,
                opponent="Castellar",
                is_home=False,
                match_date=d2,
                start_time=time(11, 30),
                end_time=time(12, 45),
                jornada=12,
                source="manual",
            )
        )
        db.add(
            Match(
                season_id=season.id,
                team_id=senior.id,
                opponent="Barcelona",
                is_home=True,
                match_date=d3,
                start_time=time(9, 0),
                end_time=time(10, 30),
                venue_id=p1.id,
                jornada=13,
                source="manual",
            )
        )

        db.add(
            CompetitionSource(
                season_id=season.id,
                source="rfep",
                external_id="123",
                label="Demo RFEP",
            )
        )

        db.commit()
        print(f"Seed OK: CH Mataró 2026/27. Acceso club: mataro / {pwd}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
