from __future__ import annotations

import os
import re
from datetime import date, datetime, time
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR = Path(os.environ.get("ATEMPO_DATA_DIR") or _DEFAULT_DATA_DIR)
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "atempo.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def default_end_date_for_season(name: str) -> date:
    """Final de temporada per defecte: 30 de juny de l'any final."""
    years = re.findall(r"\d{4}", name)
    if len(years) >= 2:
        year = int(years[-1])
    elif len(years) == 1:
        year = int(years[0]) + 1
    else:
        year = date.today().year + 1
    return date(year, 6, 30)


class Base(DeclarativeBase):
    pass


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(40))
    slug: Mapped[str | None] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(160))

    seasons: Mapped[list[Season]] = relationship(back_populates="club")
    venues: Mapped[list[Venue]] = relationship(back_populates="club")
    password_resets: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="club"
    )


class PasswordResetToken(Base):
    """Token de un sol ús per recuperar la contrasenya (hash, no el token en clar)."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    club: Mapped[Club] = relationship(back_populates="password_resets")


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("club_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)  # e.g. 2026/27
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Data de final de temporada (per defecte 30 juny de l'any final)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Hores d'entrenament/setmana per defecte (tots els equips sense override)
    default_training_hours: Mapped[float | None] = mapped_column(Float)
    # Darrer lot d’entrenos aplicats al calendari (per poder desfer)
    last_training_apply_batch: Mapped[str | None] = mapped_column(String(40))

    club: Mapped[Club] = relationship(back_populates="seasons")
    teams: Mapped[list[Team]] = relationship(back_populates="season")
    people: Mapped[list[Person]] = relationship(back_populates="season")
    matches: Mapped[list[Match]] = relationship(back_populates="season")
    trainings: Mapped[list[Training]] = relationship(back_populates="season")
    training_groups: Mapped[list[TrainingGroup]] = relationship(
        back_populates="season"
    )
    training_solapes: Mapped[list["TrainingSolape"]] = relationship(
        back_populates="season"
    )


class Venue(Base):
    """Pista / espacio del club."""

    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    allows_share_default: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_matches: Mapped[bool] = mapped_column(Boolean, default=False)

    club: Mapped[Club] = relationship(back_populates="venues")
    availabilities: Mapped[list[VenueAvailability]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    match_availabilities: Mapped[list["VenueMatchAvailability"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )


class VenueAvailability(Base):
    """Franja disponible de una pista (horarios distintos por pista)."""

    __tablename__ = "venue_availabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=lunes … 6=domingo
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    allows_share: Mapped[bool | None] = mapped_column(Boolean)  # None = usar default pista

    venue: Mapped[Venue] = relationship(back_populates="availabilities")


class VenueMatchAvailability(Base):
    """Franja disponible de una pista per a partits."""

    __tablename__ = "venue_match_availabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=lunes … 6=domingo
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    venue: Mapped[Venue] = relationship(back_populates="match_availabilities")


class Person(Base):
    """Persona maestra dentro de una temporada (jugador y/o entrenador)."""

    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("season_id", "full_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_player: Mapped[bool] = mapped_column(Boolean, default=True)
    is_coach: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    season: Mapped[Season] = relationship(back_populates="people")
    memberships: Mapped[list[TeamMembership]] = relationship(back_populates="person")
    unavailabilities: Mapped[list[PersonUnavailability]] = relationship(
        back_populates="person"
    )


class PersonUnavailability(Base):
    """Días/horas en los que una persona no está disponible."""

    __tablename__ = "person_unavailabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    # Si weekday está definido (0=lun…6=dom): recurrente cada semana
    weekday: Mapped[int | None] = mapped_column(Integer)
    # Si specific_date está definido: solo ese día
    specific_date: Mapped[date | None] = mapped_column(Date)
    # Si start/end son null: todo el día
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    reason: Mapped[str | None] = mapped_column(String(200))

    person: Mapped[Person] = relationship(back_populates="unavailabilities")


class Team(Base):
    __tablename__ = "teams"
    # Mismo nombre corto (Mataró) en ligas distintas = equipos distintos
    __table_args__ = (UniqueConstraint("season_id", "name", "category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Nom oficial de la federació (es pot mostrar si l'usuari ho vol)
    official_name: Mapped[str | None] = mapped_column(String(160))
    # Identificador extern de l'equip a la federació
    external_id: Mapped[str | None] = mapped_column(String(80))
    # Font: rfep | fecapa | manual
    source: Mapped[str | None] = mapped_column(String(40))
    category: Mapped[str | None] = mapped_column(String(80))
    # mixte | male | female — sección en la ficha de equipos
    branch: Mapped[str | None] = mapped_column(String(20))
    # Restricciones simples (fase 1)
    only_venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"))
    not_before: Mapped[time | None] = mapped_column(Time)
    not_after: Mapped[time | None] = mapped_column(Time)
    immovable: Mapped[bool] = mapped_column(Boolean, default=False)
    # Override d'hores/setmana (None = usar default de temporada)
    training_hours_week: Mapped[float | None] = mapped_column(Float)

    season: Mapped[Season] = relationship(back_populates="teams")
    memberships: Mapped[list[TeamMembership]] = relationship(back_populates="team")
    external_names: Mapped[list[TeamExternalName]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    only_venue: Mapped[Venue | None] = relationship()


class TeamMembership(Base):
    """Vínculo persona↔equipo en la temporada."""

    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("team_id", "person_id", "role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)  # player|reinforce|coach

    team: Mapped[Team] = relationship(back_populates="memberships")
    person: Mapped[Person] = relationship(back_populates="memberships")


class Match(Base):
    """Partido de liga (calendario puede ser parcial)."""

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    opponent: Mapped[str] = mapped_column(String(160), nullable=False)
    is_home: Mapped[bool] = mapped_column(Boolean, default=True)
    match_date: Mapped[date | None] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    jornada: Mapped[int | None] = mapped_column(Integer)
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"))
    # Texto federativo de pista/localidad (Sidgad); complementa venue_id
    place_name: Mapped[str | None] = mapped_column(String(160))
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(40), default="manual")  # manual|fecapa|rfep
    external_id: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    # Horario del calendario oficial (federación); se conserva al aplicar cambios locales
    official_date: Mapped[date | None] = mapped_column(Date)
    official_start_time: Mapped[time | None] = mapped_column(Time)
    official_end_time: Mapped[time | None] = mapped_column(Time)
    official_venue_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    season: Mapped[Season] = relationship(back_populates="matches")
    team: Mapped[Team] = relationship()
    venue: Mapped[Venue | None] = relationship(
        foreign_keys="Match.venue_id",
    )

    @property
    def is_changed_from_official(self) -> bool:
        """True si el horario actual difiere del oficial guardado."""
        if self.official_date is None and self.official_start_time is None:
            return False
        return (
            self.match_date != self.official_date
            or self.start_time != self.official_start_time
            or self.end_time != self.official_end_time
            or self.venue_id != self.official_venue_id
        )

    def snapshot_official_from_current(self) -> None:
        """Guarda el horario actual como oficial (si aún no hay oficial)."""
        if self.official_date is not None or self.official_start_time is not None:
            return
        self.official_date = self.match_date
        self.official_start_time = self.start_time
        self.official_end_time = self.end_time
        self.official_venue_id = self.venue_id

    def set_official(
        self,
        md: date | None,
        st: time | None,
        et: time | None,
        venue_id: int | None = None,
    ) -> None:
        self.official_date = md
        self.official_start_time = st
        self.official_end_time = et
        if venue_id is not None:
            self.official_venue_id = venue_id


class Training(Base):
    """Sesión de entrenamiento (ocupa personas + pista)."""

    __tablename__ = "trainings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"))
    allows_share: Mapped[bool] = mapped_column(Boolean, default=False)
    series_id: Mapped[str | None] = mapped_column(String(40))  # agrupa recurrencia
    # Borrador: no surt al calendari oficial fins a aplicar
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    # Alta manual / sèrie a mà (es conserva si es regenera el plan automàtic)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    # Lot d’aplicació (permet desfer la darrera aplicació)
    apply_batch: Mapped[str | None] = mapped_column(String(40))
    # Plantilla de grup (unitat)
    training_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_groups.id")
    )
    # Plantilla de solape / relevo
    training_solape_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_solapes.id")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    season: Mapped[Season] = relationship(back_populates="trainings")
    team: Mapped[Team] = relationship()
    venue: Mapped[Venue | None] = relationship()
    training_group: Mapped[TrainingGroup | None] = relationship()
    training_solape: Mapped["TrainingSolape | None"] = relationship()


class TrainingGroup(Base):
    """Plantilla estable de temporada: unitat (superequip, mateixa franja)."""

    __tablename__ = "training_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    # shared = mateixa franja; overlap = relevo amb solape
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="shared")
    overlap_minutes: Mapped[int] = mapped_column(Integer, default=30)
    # Dies de la setmana (0=dl…6=dg), p.ex. "4" o "0,2,4"
    weekdays: Mapped[str] = mapped_column(String(40), nullable=False, default="4")
    # Període actiu del grup (opcional; si és None és tota la temporada)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"), nullable=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    label: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    season: Mapped[Season] = relationship(back_populates="training_groups")
    venue: Mapped[Venue | None] = relationship()
    members: Mapped[list[TrainingGroupMember]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="TrainingGroupMember.sort_order",
    )


class TrainingGroupMember(Base):
    __tablename__ = "training_group_members"
    __table_args__ = (UniqueConstraint("group_id", "team_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("training_groups.id"), nullable=False
    )
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    group: Mapped[TrainingGroup] = relationship(back_populates="members")
    team: Mapped[Team] = relationship()


class TrainingSolape(Base):
    """Relevo A→B a la mateixa pista (solape N min, 0 = consecutiu)."""

    __tablename__ = "training_solapes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    # Costat A (entra primer): exactament un de team_a / group_a
    team_a_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    group_a_id: Mapped[int | None] = mapped_column(ForeignKey("training_groups.id"))
    # Costat B (entra després)
    team_b_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    group_b_id: Mapped[int | None] = mapped_column(ForeignKey("training_groups.id"))
    overlap_minutes: Mapped[int] = mapped_column(Integer, default=0)
    weekdays: Mapped[str] = mapped_column(String(40), nullable=False, default="4")
    label: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    season: Mapped[Season] = relationship(back_populates="training_solapes")
    team_a: Mapped[Team | None] = relationship(foreign_keys=[team_a_id])
    team_b: Mapped[Team | None] = relationship(foreign_keys=[team_b_id])
    group_a: Mapped[TrainingGroup | None] = relationship(foreign_keys=[group_a_id])
    group_b: Mapped[TrainingGroup | None] = relationship(foreign_keys=[group_b_id])


class CompetitionSource(Base):
    """Competición externa (RFEP/FECAPA) enlazada a una temporada."""

    __tablename__ = "competition_sources"
    __table_args__ = (UniqueConstraint("season_id", "source", "external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)  # rfep|fecapa
    external_id: Mapped[str] = mapped_column(String(40), nullable=False)  # idc
    label: Mapped[str | None] = mapped_column(String(160))

    season: Mapped[Season] = relationship()


class FedMatchChange(Base):
    """Canvi d’horari detectat a un partit federatiu."""

    __tablename__ = "fed_match_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)  # rfep|fecapa
    old_match_date: Mapped[date | None] = mapped_column(Date)
    old_start_time: Mapped[time | None] = mapped_column(Time)
    old_end_time: Mapped[time | None] = mapped_column(Time)
    old_venue_id: Mapped[int | None] = mapped_column(Integer)
    new_match_date: Mapped[date | None] = mapped_column(Date)
    new_start_time: Mapped[time | None] = mapped_column(Time)
    new_end_time: Mapped[time | None] = mapped_column(Time)
    new_venue_id: Mapped[int | None] = mapped_column(Integer)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime)

    match: Mapped[Match] = relationship()


class TeamExternalName(Base):
    """Nombre del equipo tal como aparece en la federación."""

    __tablename__ = "team_external_names"
    __table_args__ = (UniqueConstraint("team_id", "source", "external_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)  # rfep|fecapa
    external_name: Mapped[str] = mapped_column(String(160), nullable=False)

    team: Mapped[Team] = relationship(back_populates="external_names")


class Conflict(Base):
    """Conflicte detectat i persistit per identificar-lo establement."""

    __tablename__ = "conflicts"
    __table_args__ = (UniqueConstraint("season_id", "conflict_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    conflict_key: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    ignored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    season: Mapped[Season] = relationship()
    ignored_dates: Mapped[list["ConflictIgnored"]] = relationship(
        back_populates="conflict", cascade="all, delete-orphan"
    )


class ConflictIgnored(Base):
    """Dia concret d'un conflicte que s'ha ignorat."""

    __tablename__ = "conflict_ignored_dates"
    __table_args__ = (UniqueConstraint("conflict_id", "ignored_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conflict_id: Mapped[int] = mapped_column(ForeignKey("conflicts.id"), nullable=False)
    ignored_date: Mapped[date] = mapped_column(Date, nullable=False)

    conflict: Mapped[Conflict] = relationship(back_populates="ignored_dates")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    """Añade columnas nuevas en SQLite sin migraciones formales."""
    from sqlalchemy import text

    alters = [
        ("trainings", "series_id", "VARCHAR(40)"),
        ("trainings", "is_draft", "INTEGER DEFAULT 0"),
        ("trainings", "is_manual", "INTEGER DEFAULT 0"),
        ("trainings", "apply_batch", "VARCHAR(40)"),
        ("trainings", "training_group_id", "INTEGER"),
        ("trainings", "training_solape_id", "INTEGER"),
        ("seasons", "last_training_apply_batch", "VARCHAR(40)"),
        ("clubs", "slug", "VARCHAR(40)"),        ("clubs", "password_hash", "VARCHAR(200)"),
        ("clubs", "email", "VARCHAR(160)"),
        ("seasons", "end_date", "DATE"),
        ("seasons", "default_training_hours", "FLOAT"),
        ("teams", "branch", "VARCHAR(20)"),
        ("teams", "official_name", "VARCHAR(160)"),
        ("teams", "external_id", "VARCHAR(80)"),
        ("teams", "source", "VARCHAR(40)"),
        ("teams", "training_hours_week", "FLOAT"),
        ("matches", "official_date", "DATE"),
        ("matches", "official_start_time", "TIME"),
        ("matches", "official_end_time", "TIME"),
        ("matches", "official_venue_id", "INTEGER"),
        ("matches", "place_name", "VARCHAR(160)"),
        ("venues", "allows_matches", "INTEGER DEFAULT 0"),
        ("training_groups", "start_date", "DATE"),
        ("training_groups", "end_date", "DATE"),
        ("training_groups", "start_time", "TIME"),
        ("training_groups", "end_time", "TIME"),
        ("training_groups", "venue_id", "INTEGER"),
        ("training_groups", "is_draft", "INTEGER DEFAULT 1"),
    ]
    with engine.begin() as conn:
        for table, col, typ in alters:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            names = {r[1] for r in rows}
            if col not in names:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
        # Backfill: partidos federativos sin oficial → el actual es el oficial
        conn.execute(
            text(
                """
                UPDATE matches
                SET official_date = match_date,
                    official_start_time = start_time,
                    official_end_time = end_time,
                    official_venue_id = venue_id
                WHERE official_date IS NULL
                  AND official_start_time IS NULL
                  AND source IN ('fecapa', 'rfep', 'fgp', 'fap', 'fmp', 'fnp')
                  AND match_date IS NOT NULL
                """,
            )
        )
        # Backfill: seasons sense end_date → 30 juny any final del nom
        conn.execute(
            text(
                """
                UPDATE seasons
                SET end_date = '2027-06-30'
                WHERE end_date IS NULL
                """
            )
        )
        _migrate_teams_unique_with_category(conn)


def _migrate_teams_unique_with_category(conn) -> None:
    """Permite el mismo nombre corto en categorías distintas (SQLite)."""
    from sqlalchemy import text

    indexes = conn.execute(text("PRAGMA index_list(teams)")).fetchall()
    # index_list: seq, name, unique, origin, partial
    has_new = False
    old_uniques: list[str] = []
    for idx in indexes:
        name = idx[1]
        is_unique = bool(idx[2])
        if not is_unique:
            continue
        cols = [
            r[2]
            for r in conn.execute(text(f"PRAGMA index_info('{name}')")).fetchall()
        ]
        if cols == ["season_id", "name", "category"]:
            has_new = True
        elif cols == ["season_id", "name"]:
            old_uniques.append(name)
    if has_new and not old_uniques:
        return
    # Rebuild table with new unique constraint
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE teams_new (
                id INTEGER NOT NULL PRIMARY KEY,
                season_id INTEGER NOT NULL,
                name VARCHAR(120) NOT NULL,
                category VARCHAR(80),
                branch VARCHAR(20),
                only_venue_id INTEGER,
                not_before TIME,
                not_after TIME,
                immovable BOOLEAN,
                UNIQUE (season_id, name, category),
                FOREIGN KEY(season_id) REFERENCES seasons (id),
                FOREIGN KEY(only_venue_id) REFERENCES venues (id)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO teams_new (
                id, season_id, name, category, branch,
                only_venue_id, not_before, not_after, immovable
            )
            SELECT id, season_id, name, category, branch,
                   only_venue_id, not_before, not_after, immovable
            FROM teams
            """
        )
    )
    conn.execute(text("DROP TABLE teams"))
    conn.execute(text("ALTER TABLE teams_new RENAME TO teams"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
