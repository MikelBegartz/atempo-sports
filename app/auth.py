"""Acceso por club: slug + contraseña, sesión firmada, recuperación y admin."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.db import (
    DATA_DIR,
    Club,
    CompetitionSource,
    Match,
    PasswordResetToken,
    Person,
    PersonUnavailability,
    Season,
    Team,
    TeamExternalName,
    TeamMembership,
    Training,
    TrainingGroup,
    TrainingGroupMember,
    TrainingSolape,
    Venue,
    VenueAvailability,
)
from app.mail import deliver_email
from app.settings import demo_password, is_production

SECRET_FILE = DATA_DIR / ".session_secret"
ADMIN_PASSWORD_FILE = DATA_DIR / ".admin_password"

RESET_TTL_HOURS = 1
MIN_PASSWORD_LEN = 8
WEAK_DEMO_PASSWORD = "mataro"


def session_secret() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()
    value = secrets.token_hex(32)
    SECRET_FILE.write_text(value, encoding="utf-8")
    return value


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 180_000
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), stored)


def set_club_password(club: Club, password: str) -> None:
    club.password_hash = hash_password(password)


def normalize_email(raw: str | None) -> str:
    return " ".join((raw or "").strip().casefold().split())


def password_ok(password: str) -> bool:
    return len((password or "").strip()) >= MIN_PASSWORD_LEN


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_password_reset(
    db: Session, club: Club, *, hours: int = RESET_TTL_HOURS
) -> str:
    """Invalida tokens previos y crea uno nuevo. Devuelve el token en claro."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.club_id == club.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)

    raw = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            club_id=club.id,
            token_hash=_token_hash(raw),
            expires_at=now + timedelta(hours=hours),
            created_at=now,
        )
    )
    db.commit()
    return raw


def find_valid_reset(db: Session, raw_token: str) -> PasswordResetToken | None:
    if not (raw_token or "").strip():
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = (
        db.query(PasswordResetToken)
        .options(joinedload(PasswordResetToken.club))
        .filter(PasswordResetToken.token_hash == _token_hash(raw_token.strip()))
        .first()
    )
    if not row or row.used_at is not None or row.expires_at < now:
        return None
    return row


def consume_password_reset(
    db: Session, row: PasswordResetToken, new_password: str
) -> Club:
    set_club_password(row.club, new_password)
    row.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return row.club


def request_password_reset(
    db: Session,
    *,
    slug: str,
    email: str,
    reset_url_for_token,
) -> bool:
    """
    Si slug+email coinciden, crea token y entrega el enlace.
    El caller muestra siempre el mismo mensaje de éxito.
    """
    code = (slug or "").strip().casefold()
    mail = normalize_email(email)
    if not code or not mail:
        return False
    club = db.query(Club).filter(Club.slug == code).first()
    if not club or not club.password_hash:
        return False
    if normalize_email(club.email) != mail:
        return False
    raw = create_password_reset(db, club)
    url = reset_url_for_token(raw)
    subject = "AtempoSports — recuperar contrasenya / reset password"
    body = (
        f"Hola,\n\n"
        f"Has demanat recuperar l'accés del club «{club.name}» ({club.slug}).\n"
        f"Obre aquest enllaç (caduca en {RESET_TTL_HOURS} h):\n\n"
        f"{url}\n\n"
        f"Si no has estat tu, ignora aquest missatge.\n"
    )
    deliver_email(to=club.email.strip(), subject=subject, body=body)
    return True


def admin_password() -> str:
    """Operador: env ATEMPO_ADMIN_PASSWORD o fitxer data/.admin_password."""
    env = (os.environ.get("ATEMPO_ADMIN_PASSWORD") or "").strip()
    if env:
        return env
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ADMIN_PASSWORD_FILE.exists():
        return (
            ADMIN_PASSWORD_FILE.read_text(encoding="utf-8")
            .lstrip("\ufeff")
            .strip()
        )
    value = secrets.token_urlsafe(14)
    ADMIN_PASSWORD_FILE.write_text(value + "\n", encoding="utf-8")
    return value


def is_admin(request: Request) -> bool:
    return bool(request.session.get("is_admin"))


def _keep_session_lang(request: Request) -> str | None:
    return request.session.get("lang")


def _restore_session_lang(request: Request, lang: str | None) -> None:
    if lang:
        request.session["lang"] = lang


def login_admin(request: Request) -> None:
    lang = _keep_session_lang(request)
    request.session.clear()
    _restore_session_lang(request, lang)
    request.session["is_admin"] = True


def logout_admin(request: Request) -> None:
    request.session.pop("is_admin", None)


def default_club(db: Session) -> Club | None:
    """Club de entrada por defecto (Mataró) mientras solo hay uno activo."""
    return (
        db.query(Club).filter(Club.slug == "mataro").first()
        or db.query(Club).filter(Club.name == "CH Mataró").first()
    )


def authenticate_club(db: Session, slug: str, password: str) -> Club | None:
    code = (slug or "").strip().casefold()
    pwd = (password or "").strip()
    if not code or not pwd:
        return None
    club = db.query(Club).filter(Club.slug == code).first()
    if not club or not club.password_hash:
        return None
    if not verify_password(password, club.password_hash):
        return None
    # En producció, bloqueja la clau demo feble coneguda
    if is_production() and code == "mataro" and verify_password(
        WEAK_DEMO_PASSWORD, club.password_hash
    ):
        return None
    return club


def login_club(request: Request, club: Club) -> None:
    lang = _keep_session_lang(request)
    request.session.clear()
    _restore_session_lang(request, lang)
    request.session["club_id"] = club.id
    request.session["club_slug"] = club.slug
    request.session["club_name"] = club.name


def logout_club(request: Request) -> None:
    lang = _keep_session_lang(request)
    request.session.clear()
    _restore_session_lang(request, lang)

def current_club_id(request: Request) -> int | None:
    cid = request.session.get("club_id")
    return int(cid) if cid else None


def get_session_club(db: Session, request: Request) -> Club | None:
    cid = current_club_id(request)
    if not cid:
        return None
    return db.get(Club, cid)


def active_season_for_club(db: Session, club_id: int) -> Season | None:
    return (
        db.query(Season)
        .options(joinedload(Season.club))
        .filter(Season.club_id == club_id, Season.is_active.is_(True))
        .order_by(Season.id.desc())
        .first()
        or db.query(Season)
        .options(joinedload(Season.club))
        .filter(Season.club_id == club_id)
        .order_by(Season.id.desc())
        .first()
    )


def season_for_club(db: Session, season_id: int, club_id: int) -> Season | None:
    return (
        db.query(Season)
        .options(joinedload(Season.club))
        .filter(Season.id == season_id, Season.club_id == club_id)
        .first()
    )


def require_club_redirect(request: Request) -> RedirectResponse | None:
    if current_club_id(request) is None:
        return RedirectResponse("/login", status_code=303)
    return None


def ensure_mataro_access(db: Session) -> None:
    """
    Assegura slug del demo CH Mataró.
    Només assigna contrasenya si ATEMPO_DEMO_PASSWORD (o demo local permès).
    En producció no deixa la clau feble «mataro».
    """
    mataro = db.query(Club).filter(Club.name == "CH Mataró").first()
    if mataro:
        changed = False
        if not mataro.slug:
            mataro.slug = "mataro"
            changed = True
        pwd = demo_password()
        if pwd and not mataro.password_hash:
            mataro.password_hash = hash_password(pwd)
            changed = True
        elif (
            is_production()
            and mataro.password_hash
            and verify_password(WEAK_DEMO_PASSWORD, mataro.password_hash)
        ):
            # Força canvi: sense clau demo forta, deixa el club sense accés fins admin
            if pwd and pwd != WEAK_DEMO_PASSWORD:
                mataro.password_hash = hash_password(pwd)
            else:
                mataro.password_hash = None
            changed = True
        if changed:
            db.commit()
    admin_password()


def _slugify(name: str) -> str:
    s = unicodedata.normalize("NFD", name or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.casefold()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:36] or "club"


def unique_slug(db: Session, base: str) -> str:
    root = _slugify(base) or "club"
    candidate = root
    n = 2
    while db.query(Club.id).filter(Club.slug == candidate).first():
        suffix = f"-{n}"
        candidate = (root[: 40 - len(suffix)] + suffix)[:40]
        n += 1
    return candidate


def delete_club(db: Session, club: Club) -> str:
    """Esborra un club i totes les seves dades. Retorna el nom."""
    name = club.name
    season_ids = [s.id for s in db.query(Season).filter(Season.club_id == club.id)]
    team_ids: list[int] = []
    if season_ids:
        team_ids = [
            t.id
            for t in db.query(Team.id).filter(Team.season_id.in_(season_ids)).all()
        ]
        group_ids = [
            g.id
            for g in db.query(TrainingGroup.id)
            .filter(TrainingGroup.season_id.in_(season_ids))
            .all()
        ]
        person_ids = [
            p.id
            for p in db.query(Person.id).filter(Person.season_id.in_(season_ids)).all()
        ]

        if group_ids:
            db.query(Training).filter(
                Training.training_group_id.in_(group_ids)
            ).update({Training.training_group_id: None}, synchronize_session=False)
            db.query(TrainingSolape).filter(
                TrainingSolape.group_a_id.in_(group_ids)
            ).update({TrainingSolape.group_a_id: None}, synchronize_session=False)
            db.query(TrainingSolape).filter(
                TrainingSolape.group_b_id.in_(group_ids)
            ).update({TrainingSolape.group_b_id: None}, synchronize_session=False)
            db.query(TrainingGroupMember).filter(
                TrainingGroupMember.group_id.in_(group_ids)
            ).delete(synchronize_session=False)

        db.query(Training).filter(Training.season_id.in_(season_ids)).delete(
            synchronize_session=False
        )
        db.query(TrainingSolape).filter(
            TrainingSolape.season_id.in_(season_ids)
        ).delete(synchronize_session=False)
        if group_ids:
            db.query(TrainingGroup).filter(TrainingGroup.id.in_(group_ids)).delete(
                synchronize_session=False
            )
        db.query(Match).filter(Match.season_id.in_(season_ids)).delete(
            synchronize_session=False
        )
        db.query(CompetitionSource).filter(
            CompetitionSource.season_id.in_(season_ids)
        ).delete(synchronize_session=False)

        if person_ids:
            db.query(PersonUnavailability).filter(
                PersonUnavailability.person_id.in_(person_ids)
            ).delete(synchronize_session=False)
            db.query(TeamMembership).filter(
                TeamMembership.person_id.in_(person_ids)
            ).delete(synchronize_session=False)
            db.query(Person).filter(Person.id.in_(person_ids)).delete(
                synchronize_session=False
            )
        if team_ids:
            db.query(TeamMembership).filter(TeamMembership.team_id.in_(team_ids)).delete(
                synchronize_session=False
            )
            db.query(TeamExternalName).filter(
                TeamExternalName.team_id.in_(team_ids)
            ).delete(synchronize_session=False)
            db.query(Team).filter(Team.id.in_(team_ids)).delete(
                synchronize_session=False
            )
        db.query(Season).filter(Season.id.in_(season_ids)).delete(
            synchronize_session=False
        )

    venue_ids = [
        v.id for v in db.query(Venue.id).filter(Venue.club_id == club.id).all()
    ]
    if venue_ids:
        db.query(VenueAvailability).filter(
            VenueAvailability.venue_id.in_(venue_ids)
        ).delete(synchronize_session=False)
        db.query(Venue).filter(Venue.id.in_(venue_ids)).delete(
            synchronize_session=False
        )

    db.query(PasswordResetToken).filter(PasswordResetToken.club_id == club.id).delete(
        synchronize_session=False
    )
    db.delete(club)
    db.commit()
    return name


def register_club(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    season_name: str = "2026/27",
) -> tuple[Club | None, str | None]:
    """
    Alta de club. Devuelve (club, None) o (None, error_key i18n).
    """
    n = " ".join((name or "").split())
    mail = normalize_email(email)
    pwd = (password or "").strip()
    if len(n) < 2:
        return None, "register_name_short"
    if not mail or "@" not in mail:
        return None, "register_email_bad"
    if not password_ok(pwd):
        return None, "pwd_too_short"
    if db.query(Club.id).filter(Club.name == n).first():
        return None, "register_name_taken"
    for c in db.query(Club).filter(Club.email.isnot(None)).all():
        if normalize_email(c.email) == mail:
            return None, "register_email_taken"

    slug = unique_slug(db, n)
    club = Club(
        name=n,
        short_name=n[:40],
        slug=slug,
        email=(email or "").strip(),
        password_hash=hash_password(pwd),
    )
    db.add(club)
    db.flush()
    from app.db import default_end_date_for_season
    db.add(
        Season(
            club_id=club.id,
            name=season_name,
            is_active=True,
            end_date=default_end_date_for_season(season_name),
        )
    )
    db.commit()
    db.refresh(club)
    return club, None
