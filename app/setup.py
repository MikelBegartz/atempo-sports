"""Onboarding mínimo: RFEP → pistas (+ equipos). Personas después, sin bloquear."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.db import Season, Team, Venue
from app.link_rfep import has_rfep_link


@dataclass
class SetupStatus:
    venue_count: int
    team_count: int
    teams_ready: int
    teams_missing: list[str]
    has_rfep: bool
    has_venues: bool
    has_teams: bool
    teams_staffed: bool

    @property
    def ready(self) -> bool:
        """Mínimo para salir del onboarding: pistas + equipos. RFEP és opcional."""
        return self.has_venues and self.has_teams

    @property
    def complete(self) -> bool:
        """Configuración completa (también personas en cada equipo)."""
        return self.ready and self.teams_staffed

    @property
    def step(self) -> str:
        if not self.has_venues and not self.has_teams and not self.has_rfep:
            return "welcome"
        if not self.has_venues:
            return "venues"
        if not self.has_teams:
            return "teams"
        return "done"


def setup_next_path(season_id: int, status: SetupStatus) -> str:
    """URL del siguiente paso pendiente (sin hub intermedio)."""
    step = status.step
    if step == "welcome":
        return f"/season/{season_id}/welcome"
    if step == "venues":
        return f"/season/{season_id}/venues"
    if step == "teams":
        return f"/season/{season_id}/teams"
    return "/app"


MIN_TEAMS = 1


def season_setup_status(db: Session, season: Season) -> SetupStatus:
    venue_count = (
        db.query(Venue).filter(Venue.club_id == season.club_id).count()
    )
    teams = (
        db.query(Team)
        .options(joinedload(Team.memberships))
        .filter(Team.season_id == season.id)
        .order_by(Team.name)
        .all()
    )
    missing = [t.name for t in teams if not t.memberships]
    return SetupStatus(
        venue_count=venue_count,
        team_count=len(teams),
        teams_ready=len(teams) - len(missing),
        teams_missing=missing,
        has_rfep=has_rfep_link(db, season.id),
        has_venues=venue_count >= 1,
        has_teams=len(teams) >= MIN_TEAMS,
        teams_staffed=len(teams) >= MIN_TEAMS and not missing,
    )
