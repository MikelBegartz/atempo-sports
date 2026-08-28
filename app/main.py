from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse
import hmac
import re
import uuid

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from starlette.middleware.sessions import SessionMiddleware

import base64

from app.settings import (
    contact_email,
    https_cookies,
    load_dotenv_file,
    public_register_open,
    smtp_configured,
)
from app.admin_guard import (
    attempt_summary,
    check_recovery,
    clear_lockout,
    client_ip,
    ip_allowed,
    is_diverted,
    mark_diverted,
    recent_attempts,
    record_attempt,
    recovery_configured,
    set_recovery_word,
)

load_dotenv_file()

from app.auth import (
    active_season_for_club,
    admin_password,
    authenticate_club,
    consume_password_reset,
    create_password_reset,
    current_club_id,
    ensure_mataro_access,
    find_valid_reset,
    get_session_club,
    is_admin,
    login_admin,
    login_club,
    logout_admin,
    logout_club,
    password_ok,
    delete_club,
    register_club,
    request_password_reset,
    season_for_club,
    session_secret,
    set_club_password,
    verify_password,
)
from app.calendar_week import build_four_weeks, build_match_draft, relative_week_key
from app.changes import (
    ChangeFrame,
    analyze_change,
    auto_fix_match,
    auto_fix_match_ids,
    evaluate_slot,
    suggest_alternatives,
    suggest_training_merge,
)
from app.names import match_away_name, match_local_name, match_place_label
from app.conflicts import (
    _month_short,
    conflict_key,
    find_conflicts,
    hard_conflicts,
    people_for_team,
    persist_conflicts,
)
from app.db import (
    Club,
    CompetitionSource,
    Conflict,
    ConflictIgnored,
    VenueAvailability,
    FedMatchChange,
    Match,
    Person,
    PersonUnavailability,
    Season,
    SessionLocal,
    Team,
    TeamExternalName,
    TeamMembership,
    Training,
    TrainingGroup,
    TrainingGroupMember,
    Venue,
    VenueAvailability,
    default_end_date_for_season,
    get_db,
    init_db,
)
from app.export_csv import export_filename, export_matches_csv, export_trainings_csv
from app.fed_sync import sync_club_federation_matches

from app.import_lists import (
    PEOPLE_TEMPLATE,
    ROSTER_TEMPLATE,
    TEAMS_TEMPLATE,
    import_people_rows,
    import_roster_rows,
    import_teams_rows,
    parse_csv_text,
)
from app.guide_content import get_guide
from app.help_content import get_help
from app.i18n import get_lang, i18n_context, set_lang, translate, weekdays, weekdays_short
from app.landing_content import get_landing
from app.overlaps import (
    HORIZON_ORDER,
    find_team_overlaps,
    group_conflicts_by_horizon,
    group_overlaps_by_horizon,
)
from app.fvp import import_fvp_matches, search_fvp_club_hits
from app.import_fed import dedup_matches
from app.link_rfep import (
    FED_SOURCES,
    ensure_team_for_fed,
    group_hits_by_team,
    has_rfep_link,
    import_selected_fed_teams,
    load_fed_catalog,
    search_all_federations,
    search_club_in_catalog,
)
from app.season_copy import copy_season
from app.setup import season_setup_status, setup_next_path
from app.teams_meta import (
    group_teams_by_branch,
    normalize_branch,
    team_branch,
)
from app.training_groups import (
    DEFAULT_GROUP_WEEKDAYS,
    clear_draft_group_import,
    create_group,
    delete_group,
    estimate_capacity,
    format_weekdays,
    group_label_for_teams,
    import_draft_groups,
    load_groups,
    parse_weekdays,
    preferred_weekdays_from_drafts,
    propose_groups,
    generate_draft_from_groups,
    refresh_group_labels,
    team_display_label,
    teams_in_groups,
    update_group,
)
from app.training_fit import build_fit_advice, propose_fit, propose_solapes
from app.training_solapes import (
    DEFAULT_SOLAPE_WEEKDAYS,
    OVERLAP_CHOICES as SOLAPE_OVERLAP_CHOICES,
    SideKey,
    create_solape,
    delete_solape,
    load_solapes,
    participant_options,
    solape_display,
    update_solape,
)
from app.training_hours import (
    effective_hours,
    hours_configured,
    parse_hours,
)
from app.training_plan import (
    apply_drafts,
    build_draft_week_chart,
    build_team_week_list,
    can_revert_last_apply,
    default_plan_range,
    discard_drafts,
    draft_team_colors,
    format_time_input,
    generate_draft_plan,
    monday_of,
    revert_last_apply,
    time_from_input,
)
from app.training_series import create_weekly_series


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates"),
    context_processors=[i18n_context],
)
templates.env.filters["match_local"] = match_local_name
templates.env.filters["match_away"] = match_away_name
templates.env.filters["match_place"] = match_place_label
templates.env.filters["time_input"] = format_time_input

app = FastAPI(title="AtempoSports", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        ensure_mataro_access(db)
    finally:
        db.close()


@app.middleware("http")
async def club_auth_guard(request: Request, call_next):
    path = request.url.path
    if (
        path.startswith("/static")
        or path
        in {
            "/",
            "/login",
            "/logout",
            "/forgot",
            "/forgot/done",
            "/register",
            "/privacitat",
            "/guia",
        }
        or path.startswith("/reset/")
        or path.startswith("/admin")
        or path.startswith("/lang/")
        or path.startswith("/favicon")
    ):
        return await call_next(request)

    club_id = current_club_id(request)
    if club_id is None:
        return RedirectResponse("/login", status_code=303)

    if path.startswith("/season/"):
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[1].isdigit():
            season_id = int(parts[1])
            db = SessionLocal()
            try:
                season = db.get(Season, season_id)
                if not season or season.club_id != club_id:
                    return RedirectResponse("/app", status_code=303)
                # Onboarding: asistente + passos de setup
                section = parts[2] if len(parts) >= 3 else ""
                status = season_setup_status(db, season)
                if not status.ready:
                    ok_post = (
                        section
                        in {"venues", "teams", "people", "data", "rfep", "fed"}
                        and request.method == "POST"
                    )
                    # Durante setup: asistente + fichas de club (varias rutas)
                    allowed = {
                        "welcome",
                        "setup",
                        "data",
                        "venues",
                        "teams",
                        "people",
                        "overlaps",
                        "rfep",
                        "fed",
                    }
                    if section not in allowed and not ok_post:
                        return RedirectResponse(
                            setup_next_path(season_id, status), status_code=303
                        )
            finally:
                db.close()

    elif path == "/app":
        db = SessionLocal()
        try:
            season = active_season_for_club(db, club_id)
            status = season_setup_status(db, season) if season else None
            if season and status and not status.ready:
                return RedirectResponse(
                    setup_next_path(season.id, status), status_code=303
                )
        finally:
            db.close()

    return await call_next(request)


def _active_context(
    request: Request, db: Session, season_id: int | None = None
) -> dict | None:
    club = get_session_club(db, request)
    if not club:
        return None
    season = None
    if season_id:
        season = season_for_club(db, season_id, club.id)
    else:
        season = active_season_for_club(db, club.id)
    club_seasons = (
        db.query(Season)
        .options(joinedload(Season.club))
        .filter(Season.club_id == club.id)
        .order_by(Season.id.desc())
        .all()
    )
    setup_status = season_setup_status(db, season) if season else None
    lang = get_lang(request)
    conflicts_count = 0
    conflicts_by_horizon: dict[str, list] = {}
    conflicts_unique_count = 0
    conflicts_unique_by_horizon: dict[str, int] = {}
    if season and setup_status and setup_status.ready:
        raw_conflicts = find_conflicts(db, season.id, lang=lang)
        matches = db.query(Match).filter(Match.season_id == season.id).all()
        trainings = db.query(Training).filter(Training.season_id == season.id).all()
        match_team = {m.id: m.team_id for m in matches}
        training_team = {t.id: t.team_id for t in trainings}
        persist_conflicts(db, season.id, raw_conflicts, match_team, training_team)
        conflicts_by_horizon = group_conflicts_by_horizon(raw_conflicts, matches, trainings)
        for bucket in HORIZON_ORDER:
            if bucket in conflicts_by_horizon:
                conflicts_by_horizon[bucket] = [c for c in conflicts_by_horizon[bucket] if not c.ignored]
        conflicts = []
        for bucket in HORIZON_ORDER:
            conflicts.extend(conflicts_by_horizon.get(bucket, []))
        conflicts_count = len(conflicts)
        first_bucket_by_key: dict[tuple, str] = {}
        for bucket in HORIZON_ORDER:
            for c in conflicts_by_horizon.get(bucket, []):
                teams = {
                    match_team.get(mid) for mid in c.match_ids
                } | {
                    training_team.get(tid) for tid in c.training_ids
                }
                key = (c.kind, c.person_id, c.severity, frozenset(teams))
                if key not in first_bucket_by_key:
                    first_bucket_by_key[key] = bucket
        conflicts_unique_count = len(first_bucket_by_key)
        conflicts_unique_by_horizon = {b: 0 for b in HORIZON_ORDER}
        for bucket in first_bucket_by_key.values():
            conflicts_unique_by_horizon[bucket] += 1
    return {
        "club": club,
        "season": season,
        "club_seasons": club_seasons,
        "setup_status": setup_status,
        "conflicts_count": conflicts_count,
        "conflicts_unique_count": conflicts_unique_count,
        "conflicts_by_horizon": conflicts_by_horizon,
        "conflicts_unique_by_horizon": conflicts_unique_by_horizon,
        "lang": lang,
    }


def _dashboard_data(
    db: Session, season: Season, lang: str | None = None
) -> dict:
    raw_conflicts = find_conflicts(db, season.id, lang=lang)
    matches = (
        db.query(Match)
        .options(joinedload(Match.team), joinedload(Match.venue))
        .filter(Match.season_id == season.id)
        .order_by(Match.match_date.nulls_last(), Match.start_time.nulls_last())
        .all()
    )
    trainings = db.query(Training).filter(Training.season_id == season.id).all()
    match_team = {m.id: m.team_id for m in matches}
    training_team = {t.id: t.team_id for t in trainings}
    persist_conflicts(db, season.id, raw_conflicts, match_team, training_team)
    by_h = group_conflicts_by_horizon(raw_conflicts, matches, trainings)
    for bucket in HORIZON_ORDER:
        if bucket in by_h:
            by_h[bucket] = [c for c in by_h[bucket] if not c.ignored]
    conflicts = []
    for bucket in HORIZON_ORDER:
        conflicts.extend(by_h.get(bucket, []))
    match_team = {m.id: m.team_id for m in matches}
    training_team = {t.id: t.team_id for t in trainings}
    seen_keys = set()
    conflicts_unique = []
    for c in conflicts:
        key = conflict_key(c, match_team, training_team)
        if key not in seen_keys:
            seen_keys.add(key)
            c.key = key
            conflicts_unique.append(c)
    unseen = (
        db.query(FedMatchChange)
        .join(Match)
        .filter(Match.season_id == season.id, FedMatchChange.seen_at.is_(None))
        .order_by(FedMatchChange.created_at.desc())
        .all()
    )
    return {
        "matches": matches[:40],
        "conflicts": conflicts,
        "conflicts_unique": conflicts_unique[:8],
        "match_total": len(matches),
        "fed_unseen": unseen,
        "fed_unseen_count": len(unseen),
        "fed_changes_conflicts": any(c.has_conflict for c in unseen),
    }


def _safe_lang_return(request: Request, next_path: str = "") -> str:
    """Vuelve a la página actual tras cambiar idioma (sin open-redirect)."""
    candidates = [next_path, ""]
    referer = request.headers.get("referer") or ""
    if referer:
        candidates.append(urlparse(referer).path or "")
    for raw in candidates:
        path = (raw or "").strip()
        if not path.startswith("/") or path.startswith("//"):
            continue
        if path.startswith("/lang/"):
            continue
        return path
    return "/login"


@app.get("/lang/{code}")
def change_lang(code: str, request: Request, next: str = ""):
    set_lang(request, code)
    return RedirectResponse(_safe_lang_return(request, next), status_code=303)


def _login_ctx(
    request: Request, *, error: str | None = None, slug: str = ""
) -> dict:
    return {
        "error": error,
        "slug": slug,
        "public_register": public_register_open(),
    }


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    logout_club(request)
    lang = get_lang(request)
    landing = get_landing(lang)
    response = templates.TemplateResponse(
        request, "landing.html", {"landing": landing}
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    logout_club(request)
    response = templates.TemplateResponse(
        request, "login.html", _login_ctx(request)
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/debug/auth")
def debug_auth(code: str, secret: str, db: Session = Depends(get_db)):
    club = authenticate_club(db, code, secret)
    return {
        "code": code,
        "secret": secret,
        "found": bool(club),
        "club_name": club.name if club else None,
    }


@app.post("/login", response_class=HTMLResponse)
def login_post(
    request: Request,
    club_code: str = Form(""),
    club_secret: str = Form(""),
    slug: str = Form(""),  # compat
    password: str = Form(""),  # compat
    db: Session = Depends(get_db),
):
    code = club_code or slug
    secret = club_secret or password
    club = authenticate_club(db, code, secret)
    if not club:
        return templates.TemplateResponse(
            request,
            "login.html",
            _login_ctx(
                request,
                error=translate(get_lang(request), "login_error"),
                slug=(code or "").strip().casefold(),
            ),
            status_code=401,
        )
    login_club(request, club)
    return RedirectResponse("/app", status_code=303)


@app.post("/logout")
@app.get("/logout")
def logout(request: Request):
    logout_club(request)
    return RedirectResponse("/login", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_get(request: Request):
    if not public_register_open():
        return templates.TemplateResponse(
            request,
            "register_closed.html",
            {},
            status_code=403,
        )
    return templates.TemplateResponse(
        request,
        "register.html",
        {
            "error": None,
            "name": "",
            "email": "",
        },
    )


@app.post("/register", response_class=HTMLResponse)
def register_post(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    db: Session = Depends(get_db),
):
    if not public_register_open():
        return templates.TemplateResponse(
            request,
            "register_closed.html",
            {},
            status_code=403,
        )
    lang = get_lang(request)
    draft = {
        "error": None,
        "name": " ".join((name or "").split()),
        "email": (email or "").strip(),
    }
    if (password or "").strip() != (password2 or "").strip():
        draft["error"] = translate(lang, "pwd_mismatch")
        return templates.TemplateResponse(
            request, "register.html", draft, status_code=400
        )
    club, err = register_club(db, name=name, email=email, password=password)
    if err or not club:
        draft["error"] = translate(lang, err or "register_failed")
        return templates.TemplateResponse(
            request, "register.html", draft, status_code=400
        )
    login_club(request, club)
    return RedirectResponse("/app", status_code=303)


# —— Recuperació de contrasenya ——


@app.get("/forgot", response_class=HTMLResponse)
def forgot_get(request: Request):
    return templates.TemplateResponse(
        request,
        "forgot.html",
        {"error": None, "slug": "", "email": "", "done": False},
    )


@app.post("/forgot", response_class=HTMLResponse)
def forgot_post(
    request: Request,
    slug: str = Form(""),
    email: str = Form(""),
    db: Session = Depends(get_db),
):
    base = str(request.base_url).rstrip("/")

    def reset_url(token: str) -> str:
        return f"{base}/reset/{token}"

    # Sempre mateix resultat visible (no filtrar existència)
    request_password_reset(
        db, slug=slug, email=email, reset_url_for_token=reset_url
    )
    done_key = "forgot_done" if smtp_configured() else "forgot_done_local"
    return templates.TemplateResponse(
        request,
        "forgot.html",
        {
            "error": None,
            "slug": (slug or "").strip().casefold(),
            "email": (email or "").strip(),
            "done": True,
            "done_message": translate(get_lang(request), done_key),
        },
    )


@app.get("/reset/{token}", response_class=HTMLResponse)
def reset_get(token: str, request: Request, db: Session = Depends(get_db)):
    row = find_valid_reset(db, token)
    if not row:
        return templates.TemplateResponse(
            request,
            "reset.html",
            {"token": token, "valid": False, "error": None, "done": False},
        )
    return templates.TemplateResponse(
        request,
        "reset.html",
        {
            "token": token,
            "valid": True,
            "error": None,
            "done": False,
            "club_name": row.club.name,
        },
    )


@app.post("/reset/{token}", response_class=HTMLResponse)
def reset_post(
    token: str,
    request: Request,
    password: str = Form(""),
    password2: str = Form(""),
    db: Session = Depends(get_db),
):
    lang = get_lang(request)
    row = find_valid_reset(db, token)
    if not row:
        return templates.TemplateResponse(
            request,
            "reset.html",
            {"token": token, "valid": False, "error": None, "done": False},
        )
    pwd = (password or "").strip()
    if not password_ok(pwd):
        return templates.TemplateResponse(
            request,
            "reset.html",
            {
                "token": token,
                "valid": True,
                "error": translate(lang, "pwd_too_short"),
                "done": False,
                "club_name": row.club.name,
            },
            status_code=400,
        )
    if pwd != (password2 or "").strip():
        return templates.TemplateResponse(
            request,
            "reset.html",
            {
                "token": token,
                "valid": True,
                "error": translate(lang, "pwd_mismatch"),
                "done": False,
                "club_name": row.club.name,
            },
            status_code=400,
        )
    consume_password_reset(db, row, pwd)
    return templates.TemplateResponse(
        request,
        "reset.html",
        {"token": token, "valid": True, "error": None, "done": True},
    )


# —— Admin (operador) ——


def _require_admin(request: Request) -> RedirectResponse | None:
    if not is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return None


def _admin_wrong_place(request: Request, *, reason: str = "diverted"):
    record_attempt(request, ok=False, reason=reason)
    return templates.TemplateResponse(
        request,
        "admin_wrong_place.html",
        {"recovery_configured": recovery_configured()},
        status_code=403,
    )


@app.get("/admin/wrong", response_class=HTMLResponse)
def admin_wrong_get(request: Request):
    return _admin_wrong_place(request, reason="wrong_place")


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_get(request: Request):
    if is_admin(request):
        return RedirectResponse("/admin", status_code=303)

    ip = client_ip(request)
    # Després d’1 error: només paraula de recuperació (recordable, qualsevol PC)
    if is_diverted(ip):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "error": None,
                "recovery_mode": True,
                "recovery_configured": recovery_configured(),
            },
        )

    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {"error": None, "recovery_mode": False, "recovery_configured": True},
    )


@app.get("/admin/recover")
def admin_recover_get():
    """Evita el JSON Not Found si es recarrega o s’obre l’URL a mà."""
    return RedirectResponse("/admin/login", status_code=303)


@app.post("/admin/recover", response_class=HTMLResponse)
def admin_recover_post(
    request: Request,
    recovery_word: str = Form(""),
    recovery_phrase: str = Form(""),
):
    ip = client_ip(request)
    word = (recovery_word or recovery_phrase or "").strip()
    if not recovery_configured():
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "error": "Encara no hi ha paraula de recuperació. Espera o entra si pots.",
                "recovery_mode": True,
                "recovery_configured": False,
            },
            status_code=400,
        )
    if word and check_recovery(word):
        clear_lockout(ip)
        record_attempt(request, ok=True, reason="recovery_ok")
        return RedirectResponse("/admin/login", status_code=303)
    record_attempt(request, ok=False, reason="recovery_bad")
    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {
            "error": "Paraula de recuperació incorrecta. Esborra el camp (si el navegador l’omple) i escriu-la a mà.",
            "recovery_mode": True,
            "recovery_configured": True,
        },
        status_code=401,
    )


@app.post("/admin/login", response_class=HTMLResponse)
def admin_login_post(
    request: Request,
    operator_password: str = Form(""),
):
    lang = get_lang(request)
    ip = client_ip(request)

    if is_diverted(ip):
        return RedirectResponse("/admin/login", status_code=303)

    if not ip_allowed(ip):
        record_attempt(request, ok=False, reason="ip_denied")
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "error": translate(lang, "admin_login_denied"),
                "recovery_mode": False,
            },
            status_code=403,
        )

    expected = admin_password().encode("utf-8")
    got = (operator_password or "").strip().encode("utf-8")
    if expected and len(got) == len(expected) and hmac.compare_digest(got, expected):
        record_attempt(request, ok=True, reason="ok")
        clear_lockout(ip)
        login_admin(request)
        return RedirectResponse("/admin", status_code=303)

    record_attempt(request, ok=False, reason="bad_password")
    # Si hi ha paraula de recuperació: 1 error → lloc equivocat + desbloqueig amb la paraula
    if recovery_configured():
        mark_diverted(ip)
        return _admin_wrong_place(request, reason="bad_password")

    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {
            "error": translate(lang, "admin_login_error"),
            "recovery_mode": False,
        },
        status_code=401,
    )


@app.post("/admin/logout")
@app.get("/admin/logout")
def admin_logout(request: Request):
    logout_admin(request)
    return RedirectResponse("/login", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)):
    if not is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    clubs = db.query(Club).order_by(Club.name).all()
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "clubs": clubs,
            "flash": request.session.pop("admin_flash", None),
            "reset_link": request.session.pop("admin_reset_link", None),
            "created_slug": request.session.pop("admin_created_slug", None),
            "create_error": request.session.pop("admin_create_error", None),
            "create_name": request.session.pop("admin_create_name", ""),
            "create_email": request.session.pop("admin_create_email", ""),
            "access_summary": attempt_summary(),
            "access_log": recent_attempts(25),
            "my_ip": client_ip(request),
            "recovery_configured": recovery_configured(),
            "recovery_error": request.session.pop("admin_recovery_error", None),
        },
    )


@app.get("/admin/clubs/{club_id}/seasons", response_class=HTMLResponse)
def admin_club_seasons(
    request: Request,
    club_id: int,
    db: Session = Depends(get_db),
):
    if not is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    club = db.get(Club, club_id)
    if not club:
        return RedirectResponse("/admin", status_code=303)
    seasons = (
        db.query(Season).filter(Season.club_id == club_id).order_by(Season.name).all()
    )
    return templates.TemplateResponse(
        request,
        "admin_seasons.html",
        {
            "club": club,
            "seasons": seasons,
            "flash": request.session.pop("admin_flash", None),
        },
    )


@app.post("/admin/recovery")
def admin_set_recovery(
    request: Request,
    recovery_phrase: str = Form(""),
    recovery_phrase2: str = Form(""),
    recovery_current: str = Form(""),
):
    if not is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    # Si ja n’hi ha una, cal la actual abans de canviar-la
    if recovery_configured() and not check_recovery(recovery_current):
        request.session["admin_recovery_error"] = (
            "La paraula de recuperació actual no és correcta."
        )
        return RedirectResponse("/admin", status_code=303)
    w1 = recovery_phrase
    w2 = recovery_phrase2
    if (w1 or "").strip() != (w2 or "").strip():
        request.session["admin_recovery_error"] = "Les paraules noves no coincideixen."
        return RedirectResponse("/admin", status_code=303)
    err = set_recovery_word(w1)
    if err == "short":
        request.session["admin_recovery_error"] = (
            "Mínim 6 caràcters (una paraula o frase que recordis)."
        )
        return RedirectResponse("/admin", status_code=303)
    request.session["admin_flash"] = (
        "Paraula de recuperació desada. Recorda-la; no es torna a mostrar."
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/clubs/create")
def admin_create_club(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    db: Session = Depends(get_db),
):
    denied = _require_admin(request)
    if denied:
        return denied
    lang = get_lang(request)
    request.session["admin_create_name"] = " ".join((name or "").split())
    request.session["admin_create_email"] = (email or "").strip()
    if (password or "").strip() != (password2 or "").strip():
        request.session["admin_create_error"] = translate(lang, "pwd_mismatch")
        return RedirectResponse("/admin", status_code=303)
    club, err = register_club(db, name=name, email=email, password=password)
    if err or not club:
        request.session["admin_create_error"] = translate(
            lang, err or "register_failed"
        )
        return RedirectResponse("/admin", status_code=303)
    request.session.pop("admin_create_name", None)
    request.session.pop("admin_create_email", None)
    request.session["admin_created_slug"] = club.slug
    request.session["admin_flash"] = translate(lang, "admin_create_ok").format(
        name=club.name, slug=club.slug
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/clubs/{club_id}/delete")
def admin_delete_club(
    club_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    denied = _require_admin(request)
    if denied:
        return denied
    lang = get_lang(request)
    club = db.get(Club, club_id)
    if not club:
        return RedirectResponse("/admin", status_code=303)
    name = delete_club(db, club)
    request.session["admin_flash"] = translate(lang, "admin_delete_ok").format(
        name=name
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/clubs/{club_id}/password")
def admin_set_password(
    club_id: int,
    request: Request,
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    denied = _require_admin(request)
    if denied:
        return denied
    lang = get_lang(request)
    club = db.get(Club, club_id)
    if not club:
        return RedirectResponse("/admin", status_code=303)
    pwd = (password or "").strip()
    if not password_ok(pwd):
        request.session["admin_flash"] = translate(lang, "pwd_too_short")
        return RedirectResponse("/admin", status_code=303)
    set_club_password(club, pwd)
    db.commit()
    request.session["admin_flash"] = translate(lang, "admin_pwd_ok").format(
        name=club.name
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/clubs/{club_id}/email")
def admin_set_email(
    club_id: int,
    request: Request,
    email: str = Form(""),
    db: Session = Depends(get_db),
):
    denied = _require_admin(request)
    if denied:
        return denied
    club = db.get(Club, club_id)
    if not club:
        return RedirectResponse("/admin", status_code=303)
    club.email = (email or "").strip() or None
    db.commit()
    request.session["admin_flash"] = translate(
        get_lang(request), "admin_email_ok"
    ).format(name=club.name)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/clubs/{club_id}/reset-link")
def admin_reset_link(
    club_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    denied = _require_admin(request)
    if denied:
        return denied
    club = db.get(Club, club_id)
    if not club or not club.password_hash:
        return RedirectResponse("/admin", status_code=303)
    raw = create_password_reset(db, club)
    base = str(request.base_url).rstrip("/")
    request.session["admin_reset_link"] = f"{base}/reset/{raw}"
    request.session["admin_flash"] = translate(
        get_lang(request), "admin_reset_ok"
    ).format(name=club.name)
    return RedirectResponse("/admin", status_code=303)


@app.get("/app", response_class=HTMLResponse)
def app_home(request: Request, db: Session = Depends(get_db)):
    ctx = _active_context(request, db)
    if not ctx or not ctx["season"]:
        logout_club(request)
        return RedirectResponse("/login", status_code=303)
    season = ctx["season"]
    status = season_setup_status(db, season)
    if not status.ready:
        return RedirectResponse(
            setup_next_path(season.id, status), status_code=303
        )
    data = _dashboard_data(db, season, lang=get_lang(request))
    return templates.TemplateResponse(request, "home.html", {**ctx, **data})


@app.get("/season/{season_id}/setup", response_class=HTMLResponse)
def setup_wizard(season_id: int, request: Request, db: Session = Depends(get_db)):
    """Sin hub: redirige al siguiente paso pendiente."""
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    status = season_setup_status(db, ctx["season"])
    return RedirectResponse(
        setup_next_path(season_id, status), status_code=303
    )


@app.get("/season/{season_id}/welcome", response_class=HTMLResponse)
def welcome_page(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    status = season_setup_status(db, season)
    if status.step != "welcome":
        return RedirectResponse(setup_next_path(season_id, status), status_code=303)
    return templates.TemplateResponse(request, "welcome.html", {**ctx})


@app.get("/season/{season_id}/fed", response_class=HTMLResponse)
def fed_chooser(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ask_more: str | None = None,
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    return templates.TemplateResponse(
        request,
        "fed_chooser.html",
        {
            **ctx,
            "ask_more": ask_more in {"1", "true", "yes"},
            "fed_flash": request.session.pop("fed_flash", None),
            "federations": [*FED_SOURCES],
        },
    )


@app.get("/season/{season_id}/rfep", response_class=HTMLResponse)
def rfep_link_page(
    season_id: int,
    request: Request,
    q: str = "",
):
    qs = f"?q={q}" if (q or "").strip() else ""
    return RedirectResponse(
        f"/season/{season_id}/fed/rfep{qs}", status_code=303
    )


@app.get("/season/{season_id}/fed/search")
def fed_search_redirect(
    season_id: int,
    request: Request,
    source: str = "",
    q: str = "",
):
    """Redirigeix la cerca del formulari cap a la federació triada."""
    source = (source or "global").strip().lower()
    if source not in FED_SOURCES and source != "global":
        source = "global"
    query = (q or "").strip()
    qs = f"?q={quote(query)}" if query else ""
    return RedirectResponse(
        f"/season/{season_id}/fed/{source}{qs}", status_code=303
    )


@app.get("/season/{season_id}/fed/{source}", response_class=HTMLResponse)
def fed_link_page(
    season_id: int,
    source: str,
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    source = (source or "").strip().lower()
    if source not in FED_SOURCES and source != "global":
        return RedirectResponse(f"/season/{season_id}/fed", status_code=303)

    status = season_setup_status(db, ctx["season"])
    # Onboarding RFEP: si ya hay vínculo y aún no está ready, seguir al siguiente paso
    if (
        source == "rfep"
        and has_rfep_link(db, season_id)
        and not status.ready
        and not (q or "").strip()
    ):
        return RedirectResponse(
            setup_next_path(season_id, status), status_code=303
        )

    hits = []
    error = None
    q = (q or "").strip()
    if q:
        try:
            if source == "global":
                hits = search_all_federations(q)
            elif source == "fvp":
                hits = search_fvp_club_hits(q)
            else:
                catalog = load_fed_catalog(source)
                hits = search_club_in_catalog(catalog, q, source=source)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
    hit_groups = group_hits_by_team(hits)
    internal_teams = (
        db.query(Team.name)
        .filter(Team.season_id == season_id)
        .order_by(Team.name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "fed_link.html",
        {
            **ctx,
            "source": source,
            "q": q,
            "hits": hits,
            "hit_groups": hit_groups,
            "internal_teams": [t[0] for t in internal_teams],
            "error": error,
        },
    )


@app.post("/season/{season_id}/fed/{source}/import", response_class=HTMLResponse)
@app.post("/season/{season_id}/rfep/import", response_class=HTMLResponse)
async def fed_link_import(
    season_id: int,
    request: Request,
    source: str = "rfep",
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    # Compat: POST antiguo /rfep/import
    path = request.url.path.rstrip("/")
    if path.endswith("/rfep/import"):
        source = "rfep"
    source = (source or "rfep").strip().lower()
    if source not in FED_SOURCES and source != "global":
        return RedirectResponse(f"/season/{season_id}/fed", status_code=303)

    form = await request.form()
    q = str(form.get("q") or "")
    picks = form.getlist("pick")
    selections_by_source: dict[str, list[tuple[int, str, str, str]]] = {}
    for raw in picks:
        parts = str(raw).split("||", 4)
        if len(parts) != 5:
            continue
        src, idc_s, name, comp, idx = [p.strip() for p in parts]
        try:
            idc = int(idc_s)
        except ValueError:
            continue
        internal_name = str(form.get(f"internal_name_{idx}") or "").strip()
        selections_by_source.setdefault(src, []).append((idc, name, comp, internal_name))

    def _fed_error(msg: str):
        return templates.TemplateResponse(
            request,
            "fed_link.html",
            {
                **ctx,
                "source": source,
                "q": q,
                "hits": [],
                "hit_groups": [],
                "error": msg,
            },
        )

    if not selections_by_source:
        return _fed_error(translate(get_lang(request), "rfep_need_pick"))

    reports: list[ImportReport] = []
    try:
        for src, sels in selections_by_source.items():
            if src == "fvp":
                reports.extend(
                    import_fvp_matches(db, season_id, [(idc, n, c) for idc, n, c, _ in sels])
                )
            elif src in FED_SOURCES:
                reports.extend(
                    import_selected_fed_teams(db, season_id, sels, source=src)
                )
    except Exception as exc:  # noqa: BLE001
        return _fed_error(str(exc))

    errors = []
    for r in reports:
        if r.error:
            errors.append(f"{r.source.upper()} {r.idc}: {r.error}")
    if errors:
        return _fed_error(" · ".join(errors))

    lang = get_lang(request)
    n = sum(len(s) for s in selections_by_source.values())
    request.session["fed_flash"] = translate(lang, "fed_import_ok").format(n=n)
    # Després d’una federació: preguntar si cal importar-ne una altra
    return RedirectResponse(
        f"/season/{season_id}/fed?ask_more=1", status_code=303
    )


@app.get("/season/{season_id}/club", response_class=HTMLResponse)
def club_hub(season_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    return templates.TemplateResponse(
        request,
        "club.html",
        {
            **ctx,
            "counts": {
                "venues": (
                    db.query(Venue).filter(Venue.club_id == season.club_id).count()
                ),
                "teams": db.query(Team).filter(Team.season_id == season_id).count(),
                "people": (
                    db.query(Person).filter(Person.season_id == season_id).count()
                ),
            },
            "pwd_flash": request.session.pop("pwd_flash", None),
            "pwd_error": request.session.pop("pwd_error", None),
        },
    )


@app.post("/season/{season_id}/club/password")
def club_change_password(
    season_id: int,
    request: Request,
    current_password: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    lang = get_lang(request)
    club = ctx["club"]
    if not verify_password(current_password, club.password_hash):
        request.session["pwd_error"] = translate(lang, "pwd_current_bad")
        return RedirectResponse(f"/season/{season_id}/club", status_code=303)
    pwd = (password or "").strip()
    if not password_ok(pwd):
        request.session["pwd_error"] = translate(lang, "pwd_too_short")
        return RedirectResponse(f"/season/{season_id}/club", status_code=303)
    if pwd != (password2 or "").strip():
        request.session["pwd_error"] = translate(lang, "pwd_mismatch")
        return RedirectResponse(f"/season/{season_id}/club", status_code=303)
    set_club_password(club, pwd)
    db.commit()
    request.session["pwd_flash"] = translate(lang, "pwd_changed_ok")
    return RedirectResponse(f"/season/{season_id}/club", status_code=303)


@app.post("/season/{season_id}/club/email")
def club_change_email(
    season_id: int,
    request: Request,
    email: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    club = ctx["club"]
    club.email = (email or "").strip() or None
    db.commit()
    request.session["pwd_flash"] = translate(
        get_lang(request), "club_email_ok"
    )
    return RedirectResponse(f"/season/{season_id}/club", status_code=303)


@app.get("/season/{season_id}/data", response_class=HTMLResponse)
def data_import_page(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    status = ctx.get("setup_status")
    return templates.TemplateResponse(
        request,
        "data.html",
        {
            **ctx,
            "report": None,
            "roster_template": ROSTER_TEMPLATE,
            "teams_template": TEAMS_TEMPLATE,
            "people_template": PEOPLE_TEMPLATE,
            "next_setup": bool(status and not status.complete),
        },
    )


@app.post("/season/{season_id}/data", response_class=HTMLResponse)
async def data_import_run(
    season_id: int,
    request: Request,
    kind: str = Form("roster"),
    paste: str = Form(""),
    next: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)

    raw = (paste or "").strip()
    if file and file.filename:
        content = await file.read()
        raw = content.decode("utf-8-sig", errors="replace")

    rows = parse_csv_text(raw)
    if kind == "teams":
        report = import_teams_rows(db, season_id, rows)
    elif kind == "people":
        report = import_people_rows(db, season_id, rows)
    else:
        report = import_roster_rows(db, season_id, rows)

    status = season_setup_status(db, ctx["season"])
    if next.strip() == "setup" and status.complete:
        return RedirectResponse(f"/season/{season_id}/setup", status_code=303)

    return templates.TemplateResponse(
        request,
        "data.html",
        {
            **ctx,
            "setup_status": status,
            "report": report,
            "roster_template": ROSTER_TEMPLATE,
            "teams_template": TEAMS_TEMPLATE,
            "people_template": PEOPLE_TEMPLATE,
            "next_setup": not status.complete,
        },
    )


@app.get("/season/{season_id}", response_class=HTMLResponse)
def season_home(season_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx["season"]:
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    status = season_setup_status(db, season)
    if not status.ready:
        return RedirectResponse(setup_next_path(season_id, status), status_code=303)
    data = _dashboard_data(db, season, lang=get_lang(request))
    return templates.TemplateResponse(request, "home.html", {**ctx, **data})


@app.get("/season/{season_id}/people", response_class=HTMLResponse)
def people_list(season_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    people = (
        db.query(Person)
        .options(joinedload(Person.unavailabilities))
        .filter(Person.season_id == season_id)
        .order_by(Person.full_name)
        .all()
    )
    teams = (
        db.query(Team)
        .filter(Team.season_id == season_id)
        .order_by(Team.name)
        .all()
    )
    paste_result = None
    q = request.query_params
    if "created" in q or "skipped" in q or "linked" in q or "already" in q or "team_created" in q:
        paste_result = {
            "created": int(q.get("created") or 0),
            "skipped": int(q.get("skipped") or 0),
            "linked": int(q.get("linked") or 0),
            "already": int(q.get("already") or 0),
            "team_created": int(q.get("team_created") or 0),
        }
    return templates.TemplateResponse(
        request, "people.html", {**ctx, "people": people, "teams": teams, "paste_result": paste_result}
    )


@app.post("/season/{season_id}/people")
def people_create(
    season_id: int,
    full_name: str = Form(...),
    is_player: str | None = Form(None),
    is_coach: str | None = Form(None),
    db: Session = Depends(get_db),
):
    name = full_name.strip()
    if name:
        existing = (
            db.query(Person)
            .filter(Person.season_id == season_id, Person.full_name == name)
            .first()
        )
        if not existing:
            db.add(
                Person(
                    season_id=season_id,
                    full_name=name,
                    is_player=bool(is_player),
                    is_coach=bool(is_coach),
                )
            )
            db.commit()
    return RedirectResponse(f"/season/{season_id}/people", status_code=303)


@app.post("/season/{season_id}/people/batch")
def people_create_batch(
    season_id: int,
    names: str = Form(...),
    is_player: str | None = Form(None),
    is_coach: str | None = Form(None),
    team_id: str = Form(""),
    new_team_name: str = Form(""),
    new_team_branch: str = Form(""),
    db: Session = Depends(get_db),
):
    raw = names or ""
    all_names: list[str] = []
    for line in raw.splitlines():
        for part in line.split(","):
            name = part.strip()
            if name and name not in all_names:
                all_names.append(name)
    existing_people = {
        p.full_name: p for p in db.query(Person).filter(Person.season_id == season_id).all()
    }
    target_team_id: int | None = None
    if new_team_name.strip():
        team = Team(
            season_id=season_id,
            name=new_team_name.strip(),
            branch=new_team_branch or None,
        )
        db.add(team)
        db.flush()
        target_team_id = team.id
    elif team_id:
        team = db.query(Team).filter(Team.id == int(team_id), Team.season_id == season_id).first()
        if team:
            target_team_id = team.id
    linked_ids: set[int] = set()
    if target_team_id:
        linked_ids = {
            m.person_id for m in db.query(TeamMembership).filter(TeamMembership.team_id == target_team_id).all()
        }
    created = 0
    skipped = 0
    linked = 0
    already = 0
    team_created = 1 if target_team_id and new_team_name.strip() else 0
    for name in all_names:
        person = existing_people.get(name)
        if person is None:
            person = Person(
                season_id=season_id,
                full_name=name,
                is_player=bool(is_player),
                is_coach=bool(is_coach),
            )
            db.add(person)
            db.flush()
            existing_people[name] = person
            created += 1
        else:
            skipped += 1
        if target_team_id and person.id not in linked_ids:
            db.add(TeamMembership(team_id=target_team_id, person_id=person.id))
            linked_ids.add(person.id)
            linked += 1
        elif target_team_id and person.id in linked_ids:
            already += 1
    db.commit()
    return RedirectResponse(
        f"/season/{season_id}/people?created={created}&skipped={skipped}&linked={linked}&already={already}&team_created={team_created}",
        status_code=303,
    )


@app.post("/season/{season_id}/people/{person_id}/unavailability")
def people_add_unavailability(
    season_id: int,
    person_id: int,
    mode: str = Form("weekday"),
    weekday: str = Form(""),
    specific_date: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    person = (
        db.query(Person)
        .filter(Person.id == person_id, Person.season_id == season_id)
        .first()
    )
    if not person:
        return RedirectResponse(f"/season/{season_id}/people", status_code=303)

    wd = None
    sd = None
    if mode == "date" and specific_date:
        sd = date.fromisoformat(specific_date)
    elif weekday != "":
        try:
            wd = int(weekday)
        except ValueError:
            wd = None

    if wd is None and sd is None:
        return RedirectResponse(f"/season/{season_id}/people", status_code=303)

    st = time_from_input(start_time) if start_time else None
    et = time_from_input(end_time) if end_time else None
    db.add(
        PersonUnavailability(
            person_id=person_id,
            weekday=wd,
            specific_date=sd,
            start_time=st,
            end_time=et,
            reason=reason.strip() or None,
        )
    )
    db.commit()
    return RedirectResponse(f"/season/{season_id}/people", status_code=303)


@app.post("/season/{season_id}/people/unavailability/{unav_id}/delete")
def people_delete_unavailability(
    season_id: int,
    unav_id: int,
    db: Session = Depends(get_db),
):
    u = db.get(PersonUnavailability, unav_id)
    if u and u.person and u.person.season_id == season_id:
        db.delete(u)
        db.commit()
    elif u:
        # load person if not eager
        p = db.get(Person, u.person_id)
        if p and p.season_id == season_id:
            db.delete(u)
            db.commit()
    return RedirectResponse(f"/season/{season_id}/people", status_code=303)


@app.get("/season/{season_id}/teams", response_class=HTMLResponse)
@app.get("/season/{season_id}/teams/", response_class=HTMLResponse)
def teams_list(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    t: int | None = None,
    new: str | None = None,
):
    panel = None
    if new in {"equip", "edit"}:
        panel = new
    return _teams_page(season_id, request, db, panel=panel, selected_id=t)


def _backfill_team_branches(db: Session, teams: list[Team]) -> None:
    changed = False
    for team in teams:
        want = team_branch(team)
        if team.branch != want:
            team.branch = want
            changed = True
    if changed:
        db.commit()


def _teams_page(
    season_id: int,
    request: Request,
    db: Session,
    *,
    panel: str | None = None,
    selected_id: int | None = None,
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    teams = (
        db.query(Team)
        .options(joinedload(Team.memberships).joinedload(TeamMembership.person))
        .filter(Team.season_id == season_id)
        .order_by(Team.name)
        .all()
    )
    _backfill_team_branches(db, teams)
    for team in teams:
        team.memberships.sort(key=lambda m: (m.role, m.person.full_name.lower()))
    selected = None
    if selected_id:
        selected = next((x for x in teams if x.id == selected_id), None)
    people = (
        db.query(Person)
        .filter(Person.season_id == season_id)
        .order_by(Person.full_name)
        .all()
    )
    lang = get_lang(request)
    groups = load_groups(db, season_id)
    team_group_label: dict[int, str] = {}
    for g in groups:
        label = g.label or translate(lang, "tr_groups_unnamed")
        for m in g.members:
            team_group_label[m.team_id] = label
    solapes = load_solapes(db, season_id)
    team_in_solape: set[int] = set()
    for s in solapes:
        if s.team_a_id:
            team_in_solape.add(s.team_a_id)
        if s.team_b_id:
            team_in_solape.add(s.team_b_id)
        for g in (s.group_a, s.group_b):
            if not g:
                continue
            for m in g.members:
                team_in_solape.add(m.team_id)
    q = request.query_params
    teams_result = None
    if "created" in q or "skipped" in q:
        teams_result = {
            "created": int(q.get("created") or 0),
            "skipped": int(q.get("skipped") or 0),
        }
    return templates.TemplateResponse(
        request,
        "teams.html",
        {
            **ctx,
            "teams": teams,
            "teams_by_branch": group_teams_by_branch(teams),
            "selected": selected,
            "panel": panel,
            "people": people,
            "team_group_label": team_group_label,
            "team_in_solape": team_in_solape,
            "teams_delete_label": translate(lang, "teams_delete"),
            "teams_delete_confirm": translate(lang, "teams_delete_confirm"),
            "teams_result": teams_result,
            "branch_labels": {
                "base_mixed": translate(lang, "teams_branch_base_mixed"),
                "base_female": translate(lang, "teams_branch_base_female"),
                "senior_male": translate(lang, "teams_branch_senior_male"),
                "senior_female": translate(lang, "teams_branch_senior_female"),
            },
        },
    )


@app.post("/season/{season_id}/teams")
def teams_create(
    season_id: int,
    name: str = Form(...),
    branch: str = Form("base_mixed"),
    category: str = Form(""),
    not_before: str = Form(""),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    n = name.strip()
    if n:
        nb = time_from_input(not_before) if not_before else None
        team = Team(
            season_id=season_id,
            name=n,
            category=category.strip() or None,
            branch=normalize_branch(branch),
            not_before=nb,
        )
        db.add(team)
        db.commit()
        db.refresh(team)
        if next.strip() == "setup":
            return RedirectResponse(f"/season/{season_id}/setup", status_code=303)
        return RedirectResponse(
            f"/season/{season_id}/teams?t={team.id}", status_code=303
        )
    if next.strip() == "setup":
        return RedirectResponse(f"/season/{season_id}/setup", status_code=303)
    return RedirectResponse(f"/season/{season_id}/teams?new=equip", status_code=303)


@app.post("/season/{season_id}/teams/batch")
def teams_create_batch(
    season_id: int,
    names: str = Form(...),
    branch: str = Form("base_mixed"),
    db: Session = Depends(get_db),
):
    raw = names or ""
    all_names: list[str] = []
    for line in raw.splitlines():
        for part in line.split(","):
            name = part.strip()
            if name and name not in all_names:
                all_names.append(name)
    existing = {
        t.name for t in db.query(Team).filter(Team.season_id == season_id).all()
    }
    created = 0
    skipped = 0
    norm_branch = normalize_branch(branch)
    for name in all_names:
        if name in existing:
            skipped += 1
            continue
        db.add(
            Team(
                season_id=season_id,
                name=name,
                branch=norm_branch,
                category=None,
            )
        )
        existing.add(name)
        created += 1
    db.commit()
    return RedirectResponse(
        f"/season/{season_id}/teams?created={created}&skipped={skipped}",
        status_code=303,
    )


@app.get("/season/{season_id}/teams/link", response_class=HTMLResponse)
def teams_link(
    season_id: int,
    request: Request,
    q: str = "",
    club_id: int | None = None,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    q = (q or request.query_params.get("q") or "").strip()
    try:
        club_id = int(request.query_params.get("club_id")) if request.query_params.get("club_id") else None
    except ValueError:
        club_id = None
    teams = (
        db.query(Team)
        .options(joinedload(Team.external_names))
        .filter(Team.season_id == season_id)
        .order_by(Team.name)
        .all()
    )
    club_teams = [
        t for t in teams if not t.source or t.source not in FED_SOURCES
    ]
    existing_names = {
        (e.source, e.external_name, e.competition)
        for t in club_teams
        for e in t.external_names
    }
    active_club = next((t for t in club_teams if t.id == club_id), None)
    hits = []
    error = None
    if active_club and q:
        try:
            hits = search_all_federations(q)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
    hits = [h for h in hits if (h.source, h.team.full_name, h.competition) not in existing_names]
    hit_groups = group_hits_by_team(hits)
    return templates.TemplateResponse(
        request,
        "teams_link.html",
        {
            **ctx,
            "q": q,
            "club_teams": club_teams,
            "active_club": active_club,
            "hit_groups": hit_groups,
            "error": error,
        },
    )


@app.post("/season/{season_id}/teams/link/update")
async def teams_link_update(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    form = await request.form()
    q = str(form.get("q") or "").strip()
    try:
        club_id = int(form.get("club_id") or 0)
    except ValueError:
        club_id = 0
    club = db.get(Team, club_id)
    if not club or club.season_id != season_id or club.source in FED_SOURCES:
        return RedirectResponse(f"/season/{season_id}/teams/link", status_code=303)
    picks = form.getlist("pick")
    for raw in picks:
        parts = str(raw).split("||", 3)
        if len(parts) != 4:
            continue
        source, _idc, external_name, competition = [p.strip() for p in parts]
        if source not in FED_SOURCES:
            continue
        exists = (
            db.query(TeamExternalName)
            .filter(
                TeamExternalName.team_id == club.id,
                TeamExternalName.source == source,
                TeamExternalName.external_name == external_name,
                TeamExternalName.competition == competition,
            )
            .first()
        )
        if not exists:
            db.add(
                TeamExternalName(
                    team_id=club.id,
                    source=source,
                    external_name=external_name,
                    competition=competition,
                )
            )
    db.commit()
    return RedirectResponse(
        f"/season/{season_id}/teams/link?club_id={club.id}&q={q}",
        status_code=303,
    )


@app.post("/season/{season_id}/teams/{team_id}/update")
def teams_update(
    season_id: int,
    team_id: int,
    name: str = Form(...),
    branch: str = Form("base_mixed"),
    category: str = Form(""),
    not_before: str = Form(""),
    db: Session = Depends(get_db),
):
    team = (
        db.query(Team)
        .filter(Team.id == team_id, Team.season_id == season_id)
        .first()
    )
    if not team:
        return RedirectResponse(f"/season/{season_id}/teams", status_code=303)
    n = name.strip()
    if n:
        team.name = n
        team.branch = normalize_branch(branch)
        team.category = category.strip() or None
        team.not_before = time_from_input(not_before) if not_before else None
        db.commit()
    return RedirectResponse(f"/season/{season_id}/teams?t={team_id}", status_code=303)


@app.post("/season/{season_id}/teams/{team_id}/delete")
def teams_delete(
    season_id: int,
    team_id: int,
    db: Session = Depends(get_db),
):
    team = (
        db.query(Team)
        .filter(Team.id == team_id, Team.season_id == season_id)
        .first()
    )
    if not team:
        return RedirectResponse(f"/season/{season_id}/teams", status_code=303)
    has_matches = db.query(Match.id).filter(Match.team_id == team_id).first()
    has_trainings = db.query(Training.id).filter(Training.team_id == team_id).first()
    if has_matches or has_trainings:
        return RedirectResponse(
            f"/season/{season_id}/teams?t={team_id}", status_code=303
        )
    db.query(TeamMembership).filter(TeamMembership.team_id == team_id).delete()
    db.query(TeamExternalName).filter(TeamExternalName.team_id == team_id).delete()
    db.delete(team)
    db.commit()
    return RedirectResponse(f"/season/{season_id}/teams", status_code=303)


@app.post("/season/{season_id}/teams/bulk-delete")
def teams_bulk_delete(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    team_ids: list[int] = Form([]),
):
    ctx = _active_context(request, db, season_id)
    if not ctx:
        return RedirectResponse("/app", status_code=303)
    for tid in team_ids:
        team = db.query(Team).filter(Team.id == tid, Team.season_id == season_id).first()
        if not team:
            continue
        has_matches = db.query(Match.id).filter(Match.team_id == tid).first()
        has_trainings = db.query(Training.id).filter(Training.team_id == tid).first()
        if has_matches or has_trainings:
            continue
        db.query(TeamMembership).filter(TeamMembership.team_id == tid).delete()
        db.query(TeamExternalName).filter(TeamExternalName.team_id == tid).delete()
        db.delete(team)
    db.commit()
    return RedirectResponse(f"/season/{season_id}/teams", status_code=303)


@app.post("/season/{season_id}/teams/{team_id}/members")
def team_add_member(
    season_id: int,
    team_id: int,
    person_name: str = Form(""),
    person_id: str = Form(""),
    names: str = Form(""),
    role: str = Form("player"),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    if role not in {"player", "reinforce", "coach"}:
        role = "player"

    team = (
        db.query(Team)
        .filter(Team.id == team_id, Team.season_id == season_id)
        .first()
    )
    if not team:
        return RedirectResponse(f"/season/{season_id}/teams", status_code=303)

    # Recopilar nombres de la entrada individual o del lote
    to_link: list[str] = []
    if person_name.strip():
        to_link.append(person_name.strip())
    if names.strip():
        to_link.extend(
            ln.strip() for ln in names.splitlines() if ln.strip()
        )

    added = 0
    for name in to_link:
        person = (
            db.query(Person)
            .filter(Person.season_id == season_id, Person.full_name == name)
            .first()
        )
        if not person:
            person = Person(
                season_id=season_id,
                full_name=name,
                is_player=role != "coach",
                is_coach=role == "coach",
            )
            db.add(person)
            db.flush()

        exists = (
            db.query(TeamMembership)
            .filter(
                TeamMembership.team_id == team_id,
                TeamMembership.person_id == person.id,
                TeamMembership.role == role,
            )
            .first()
        )
        if not exists:
            db.add(TeamMembership(team_id=team_id, person_id=person.id, role=role))
            added += 1
        db.commit()
    if next.strip() == "setup":
        return RedirectResponse(f"/season/{season_id}/setup", status_code=303)
    return RedirectResponse(f"/season/{season_id}/teams?t={team_id}", status_code=303)


@app.post("/season/{season_id}/teams/memberships/{membership_id}/delete")
def team_remove_member(
    season_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
):
    m = db.get(TeamMembership, membership_id)
    if not m:
        return RedirectResponse(f"/season/{season_id}/teams", status_code=303)
    team = db.get(Team, m.team_id)
    if not team or team.season_id != season_id:
        return RedirectResponse(f"/season/{season_id}/teams", status_code=303)
    tid = team.id
    db.delete(m)
    db.commit()
    return RedirectResponse(f"/season/{season_id}/teams?t={tid}", status_code=303)


@app.post("/season/{season_id}/teams/memberships/{membership_id}/role")
def team_update_member_role(
    season_id: int,
    membership_id: int,
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    m = db.get(TeamMembership, membership_id)
    if not m:
        return RedirectResponse(f"/season/{season_id}/teams", status_code=303)
    team = db.get(Team, m.team_id)
    if not team or team.season_id != season_id:
        return RedirectResponse(f"/season/{season_id}/teams", status_code=303)
    if role in ("player", "coach", "reinforce"):
        m.role = role
        db.commit()
    return RedirectResponse(f"/season/{season_id}/teams?t={team.id}", status_code=303)


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _venue_schedule_bars(
    availabilities,
    *,
    day_start_h: int = 0,
    day_end_h: int = 24,
) -> list[list[dict]]:
    """Bars for a Mon–Sun strip; each bar is left/width % within the day window."""
    window_start = day_start_h * 60
    window_end = day_end_h * 60
    span = max(window_end - window_start, 1)
    days: list[list[dict]] = [[] for _ in range(7)]
    for a in availabilities:
        if a.weekday < 0 or a.weekday > 6:
            continue
        start_m = max(_minutes(a.start_time), window_start)
        end_m = min(_minutes(a.end_time), window_end)
        if end_m <= start_m:
            continue
        days[a.weekday].append(
            {
                "left": round((start_m - window_start) / span * 100, 2),
                "width": round((end_m - start_m) / span * 100, 2),
                "label": (
                    f"{a.start_time.strftime('%H:%M')}–{a.end_time.strftime('%H:%M')}"
                ),
            }
        )
    return days


def _venues_page(
    season_id: int,
    request: Request,
    db: Session,
    *,
    venue_error: str | None = None,
    draft_name: str = "",
    draft_share: bool = False,
    panel: str | None = None,
    selected_id: int | None = None,
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    venues = (
        db.query(Venue)
        .options(joinedload(Venue.availabilities))
        .filter(Venue.club_id == season.club_id)
        .order_by(Venue.name)
        .all()
    )
    for venue in venues:
        venue.availabilities.sort(key=lambda a: (a.weekday, a.start_time))
    selected = None
    if selected_id:
        selected = next((v for v in venues if v.id == selected_id), None)
    lang = get_lang(request)
    schedule_bars = {v.id: _venue_schedule_bars(v.availabilities) for v in venues}
    return templates.TemplateResponse(
        request,
        "venues.html",
        {
            **ctx,
            "venues": venues,
            "selected": selected,
            "panel": panel,
            "weekday_names": weekdays(lang),
            "weekday_short": weekdays_short(lang),
            "schedule_bars": schedule_bars,
            "venues_delete_label": translate(lang, "venues_delete"),
            "venues_delete_confirm": translate(lang, "venues_delete_confirm"),
            "venue_error": venue_error,
            "draft_name": draft_name,
            "draft_share": draft_share,
        },
    )


@app.get("/season/{season_id}/venues", response_class=HTMLResponse)
@app.get("/season/{season_id}/venues/", response_class=HTMLResponse)
def venues_list(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    v: int | None = None,
    new: str | None = None,
):
    panel = None
    if new in {"pista", "franja"}:
        panel = new
    return _venues_page(
        season_id, request, db, panel=panel, selected_id=v
    )


def _parse_slot(weekday_raw: str, start_raw: str, end_raw: str) -> tuple[int, time, time] | None:
    try:
        weekday = int(weekday_raw)
        start = time_from_input(start_raw)
        end = time_from_input(end_raw)
    except (TypeError, ValueError):
        return None
    if weekday < 0 or weekday > 6 or end <= start:
        return None
    return weekday, start, end


@app.post("/season/{season_id}/venues")
async def venues_create(
    season_id: int,
    request: Request,
    name: str = Form(...),
    allows_share: str | None = Form(None),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    if not season:
        return RedirectResponse("/app", status_code=303)
    n = name.strip()
    form = await request.form()
    slots: list[tuple[int, time, time]] = []
    # Semana completa lun–dom (sin saltar fin de semana)
    for i in range(7):
        if not form.get(f"day_{i}_on"):
            continue
        parsed = _parse_slot(
            str(i),
            str(form.get(f"day_{i}_start") or ""),
            str(form.get(f"day_{i}_end") or ""),
        )
        if parsed:
            slots.append(parsed)
    # Franjas extra (horario partido)
    for wd, st, en in zip(
        form.getlist("slot_weekday"),
        form.getlist("slot_start"),
        form.getlist("slot_end"),
    ):
        parsed = _parse_slot(str(wd), str(st), str(en))
        if parsed:
            slots.append(parsed)

    # Setup sin formulario de semana: semana completa 17–22
    if not slots and next.strip() == "setup":
        slots = [(i, time(17, 0), time(22, 0)) for i in range(7)]

    if not n or not slots:
        lang = get_lang(request)
        return _venues_page(
            season_id,
            request,
            db,
            venue_error=translate(lang, "venues_need_hours"),
            draft_name=n,
            draft_share=bool(allows_share),
            panel="pista",
        )

    venue = Venue(
        club_id=season.club_id,
        name=n,
        allows_share_default=bool(allows_share),
    )
    db.add(venue)
    db.flush()
    for weekday, start, end in slots:
        db.add(
            VenueAvailability(
                venue_id=venue.id,
                weekday=weekday,
                start_time=start,
                end_time=end,
            )
        )
    db.commit()
    status = season_setup_status(db, season)
    # Primera pista (o next=setup): salir al app si ya hay RFEP+equipos
    if next.strip() == "setup" or (status.ready and status.venue_count == 1):
        return RedirectResponse(
            setup_next_path(season_id, status), status_code=303
        )
    return RedirectResponse(
        f"/season/{season_id}/venues?v={venue.id}", status_code=303
    )


@app.post("/season/{season_id}/venues/{venue_id}/rename")
def venues_rename(
    season_id: int,
    venue_id: int,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    venue = db.get(Venue, venue_id)
    if not season or not venue or venue.club_id != season.club_id:
        return RedirectResponse(f"/season/{season_id}/venues", status_code=303)
    n = name.strip()
    if n:
        venue.name = n
        db.commit()
    return RedirectResponse(f"/season/{season_id}/venues?v={venue_id}", status_code=303)


@app.post("/season/{season_id}/venues/availability")
def venues_add_availability_pick(
    season_id: int,
    venue_id: int = Form(...),
    weekday: int = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    db: Session = Depends(get_db),
):
    return venues_add_availability(
        season_id, venue_id, weekday, start_time, end_time, db
    )


@app.post("/season/{season_id}/venues/{venue_id}/availability")
def venues_add_availability(
    season_id: int,
    venue_id: int,
    weekday: int = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    venue = db.get(Venue, venue_id)
    if not season or not venue or venue.club_id != season.club_id:
        return RedirectResponse(f"/season/{season_id}/venues", status_code=303)
    parsed = _parse_slot(str(weekday), start_time, end_time)
    if not parsed:
        return RedirectResponse(f"/season/{season_id}/venues?v={venue_id}", status_code=303)
    wd, start, end = parsed
    db.add(
        VenueAvailability(
            venue_id=venue.id,
            weekday=wd,
            start_time=start,
            end_time=end,
        )
    )
    db.commit()
    return RedirectResponse(f"/season/{season_id}/venues?v={venue_id}", status_code=303)


@app.post("/season/{season_id}/venues/availability/{avail_id}/update")
def venues_update_availability(
    season_id: int,
    avail_id: int,
    weekday: int = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    return_venue: str = Form(""),
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    avail = db.get(VenueAvailability, avail_id)
    if not season or not avail:
        return RedirectResponse(f"/season/{season_id}/venues", status_code=303)
    venue = db.get(Venue, avail.venue_id)
    if not venue or venue.club_id != season.club_id:
        return RedirectResponse(f"/season/{season_id}/venues", status_code=303)
    parsed = _parse_slot(str(weekday), start_time, end_time)
    dest_id = venue.id
    if return_venue.strip().isdigit():
        dest_id = int(return_venue.strip())
    if not parsed:
        return RedirectResponse(f"/season/{season_id}/venues?v={dest_id}", status_code=303)
    wd, start, end = parsed
    avail.weekday = wd
    avail.start_time = start
    avail.end_time = end
    db.commit()
    return RedirectResponse(f"/season/{season_id}/venues?v={dest_id}", status_code=303)


@app.post("/season/{season_id}/venues/availability/{avail_id}/delete")
def venues_delete_availability(
    season_id: int,
    avail_id: int,
    return_venue: str = Form(""),
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    avail = db.get(VenueAvailability, avail_id)
    if not season or not avail:
        return RedirectResponse(f"/season/{season_id}/venues", status_code=303)
    venue = db.get(Venue, avail.venue_id)
    if not venue or venue.club_id != season.club_id:
        return RedirectResponse(f"/season/{season_id}/venues", status_code=303)
    dest_id = venue.id
    if return_venue.strip().isdigit():
        dest_id = int(return_venue.strip())
    db.delete(avail)
    db.commit()
    return RedirectResponse(f"/season/{season_id}/venues?v={dest_id}", status_code=303)


@app.post("/season/{season_id}/venues/{venue_id}/delete")
@app.post("/season/{season_id}/venues/{venue_id}/delete/")
def venues_delete(
    season_id: int,
    venue_id: int,
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    venue = db.get(Venue, venue_id)
    if not season or not venue or venue.club_id != season.club_id:
        return RedirectResponse(url=f"/season/{season_id}/venues", status_code=303)

    db.query(VenueAvailability).filter(VenueAvailability.venue_id == venue_id).delete()
    db.query(Match).filter(Match.venue_id == venue_id).update(
        {Match.venue_id: None}, synchronize_session=False
    )
    db.query(Training).filter(Training.venue_id == venue_id).update(
        {Training.venue_id: None}, synchronize_session=False
    )
    db.query(Team).filter(Team.only_venue_id == venue_id).update(
        {Team.only_venue_id: None}, synchronize_session=False
    )
    db.delete(venue)
    db.commit()
    return RedirectResponse(url=f"/season/{season_id}/venues", status_code=303)


def _query_int(raw: str | int | None) -> int | None:
    """Query opcional: '' o None → None (evita 422 en selects vacíos)."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _filter_matches(
    matches: list[Match],
    *,
    q: str = "",
    team_id: int | None = None,
    day: date | None = None,
) -> list[Match]:
    qn = " ".join((q or "").casefold().split())
    out: list[Match] = []
    for m in matches:
        if team_id is not None and m.team_id != team_id:
            continue
        if day is not None and m.match_date != day:
            continue
        if qn:
            blob = " ".join(
                [
                    m.team.name if m.team else "",
                    m.opponent or "",
                    m.team.category or "",
                    match_local_name(m),
                    match_away_name(m),
                    match_place_label(m),
                ]
            ).casefold()
            if qn not in blob:
                continue
        out.append(m)
    return out


def _matches_page(
    request: Request,
    db: Session,
    ctx: dict,
    *,
    m: int | None = None,
    q: str = "",
    team_id: int | None = None,
    day: str = "",
    horizon: str = "m1",
    result: dict | None = None,
    conflict: str | None = None,
):
    season = ctx["season"]
    season_id = season.id
    all_matches = (
        db.query(Match)
        .options(joinedload(Match.team), joinedload(Match.venue))
        .filter(Match.season_id == season_id)
        .order_by(Match.match_date.nulls_last(), Match.start_time.nulls_last())
        .all()
    )
    day_d = date.fromisoformat(day) if day else None
    filtered = _filter_matches(
        all_matches, q=q, team_id=team_id, day=day_d
    )
    searching = bool((q or "").strip() or team_id or day)
    selected = None
    if m is not None:
        selected = next((x for x in all_matches if x.id == m), None)
    elif searching and len(filtered) == 1:
        selected = filtered[0]
        # Redirigir a URL canónica con m=
        qs = [f"m={selected.id}"]
        if (q or "").strip():
            qs.append(f"q={q.strip()}")
        if team_id:
            qs.append(f"team_id={team_id}")
        if day:
            qs.append(f"day={day}")
        return RedirectResponse(
            f"/season/{season_id}/matches?" + "&".join(qs) + "#fitxa",
            status_code=303,
        )

    teams = (
        db.query(Team).filter(Team.season_id == season_id).order_by(Team.name).all()
    )
    venues = (
        db.query(Venue)
        .filter(Venue.club_id == season.club_id)
        .order_by(Venue.name)
        .all()
    )
    list_matches = filtered if searching else all_matches
    fq = (q or "").strip()
    back_parts: list[str] = []
    if fq:
        back_parts.append(f"q={quote(fq)}")
    if team_id:
        back_parts.append(f"team_id={team_id}")
    if day:
        back_parts.append(f"day={day}")
    list_back_href = f"/season/{season_id}/matches"
    if back_parts:
        list_back_href += "?" + "&".join(back_parts)
    conflict_back_href = (
        f"/season/{season_id}/conflict/{conflict}" if conflict else ""
    )

    # Calendari de partits (dies files, hores columnes)
    lang = get_lang(request)
    focus = date.today()

    # Conflictes i propostes del partit seleccionat
    match_conflicts = []
    clean_alternatives = []
    if selected:
        all_conflicts = find_conflicts(db, season_id)
        match_conflicts = [c for c in all_conflicts if selected.id in c.match_ids]
        if not selected.locked and not selected.team.immovable:
            alt_frame = ChangeFrame(
                window_start=focus,
                window_end=focus + timedelta(days=30),
                allowed_weekdays=[],
                time_from=time(9, 0),
                time_to=time(21, 0),
            )
            clean_alternatives = suggest_alternatives(db, selected, alt_frame, limit=5)

    draft_days, draft_hours, draft_grid, draft_start, draft_end = build_match_draft(
        db, season_id, focus, today=focus, horizon=horizon
    )

    return templates.TemplateResponse(
        request,
        "matches.html",
        {
            **ctx,
            "matches": list_matches,
            "teams": teams,
            "venues": venues,
            "selected": selected,
            "result": result,
            "filter_q": fq,
            "filter_team_id": team_id,
            "filter_day": day or "",
            "search_empty": searching and not list_matches,
            "list_back_href": list_back_href,
            "conflict_back_href": conflict_back_href,
            "draft_days": draft_days,
            "draft_hours": draft_hours,
            "draft_grid": draft_grid,
            "draft_start": draft_start,
            "draft_end": draft_end,
            "horizon": horizon,
            "today": focus,
            "weekday_names": weekdays(lang),
            "match_conflicts": match_conflicts,
            "clean_alternatives": clean_alternatives,
            "all_matches": all_matches,
            "matches_flash": request.session.pop("matches_flash", None),
        },
    )


@app.get("/season/{season_id}/matches", response_class=HTMLResponse)
def matches_list(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    m: str | None = None,
    q: str = "",
    team_id: str | None = None,
    day: str = "",
    horizon: str = "m1",
    conflict: str | None = None,
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    return _matches_page(
        request,
        db,
        ctx,
        m=_query_int(m),
        q=q,
        team_id=_query_int(team_id),
        day=day or "",
        horizon=horizon,
        conflict=conflict,
    )


@app.get("/season/{season_id}/matches/create", response_class=HTMLResponse)
def match_create_page(
    season_id: int,
    request: Request,
    type: str = "official",
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    teams = (
        db.query(Team)
        .filter(Team.season_id == season.id)
        .order_by(Team.name)
        .all()
    )
    venues = (
        db.query(Venue)
        .filter(Venue.club_id == season.club_id)
        .order_by(Venue.name)
        .all()
    )
    create_type = type if type in {"official", "friendly"} else "official"
    return templates.TemplateResponse(
        request,
        "match_create.html",
        {
            **ctx,
            "teams": teams,
            "venues": venues,
            "create_type": create_type,
        },
    )


@app.post("/season/{season_id}/matches/create")
def match_create(
    season_id: int,
    request: Request,
    type: str = "official",
    team_id: int = Form(...),
    opponent: str = Form(...),
    match_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    is_home: str = Form("1"),
    venue_id: str = Form(""),
    place_name: str = Form(""),
    jornada: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    create_type = type if type in {"official", "friendly"} else "official"
    md = date.fromisoformat(match_date)
    st = time_from_input(start_time)
    et = time_from_input(end_time)
    home = is_home in ("1", "true", "on", "True")
    vid = int(venue_id) if venue_id else None
    place = place_name.strip() or None
    j = int(jornada) if jornada.strip() else None
    source = "manual" if create_type == "official" else "amistoso"
    db.add(
        Match(
            season_id=season_id,
            team_id=team_id,
            opponent=opponent.strip(),
            is_home=home,
            match_date=md,
            start_time=st,
            end_time=et,
            venue_id=vid if home else None,
            place_name=place,
            jornada=j,
            source=source,
            official_date=md if create_type == "official" else None,
            official_start_time=st if create_type == "official" else None,
            official_end_time=et if create_type == "official" else None,
            official_venue_id=vid if (create_type == "official" and home) else None,
        )
    )
    db.commit()
    return RedirectResponse(f"/season/{season_id}/matches", status_code=303)


@app.get("/season/{season_id}/trainings", response_class=HTMLResponse)
def trainings_list(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    created: str | None = None,
    series: str | None = None,
    draft_week: str | None = None,
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    teams = (
        db.query(Team).filter(Team.season_id == season_id).order_by(Team.name).all()
    )
    if teams and not hours_configured(season):
        return templates.TemplateResponse(
            request,
            "trainings_hours_setup.html",
            {
                **ctx,
                "teams": teams,
                "team_count": len(teams),
                "error": None,
                "draft_hours": "4.5",
            },
        )

    trainings = (
        db.query(Training)
        .options(joinedload(Training.team), joinedload(Training.venue))
        .filter(
            Training.season_id == season_id,
            Training.is_draft.is_(False),
        )
        .order_by(Training.session_date, Training.start_time)
        .all()
    )
    _draft_opts = (
        joinedload(Training.team),
        joinedload(Training.venue),
        joinedload(Training.training_group),
    )
    drafts = (
        db.query(Training)
        .options(*_draft_opts)
        .filter(
            Training.season_id == season_id,
            Training.is_draft.is_(True),
        )
        .order_by(Training.session_date, Training.start_time)
        .all()
    )
    # No es regenera automàticament el borrador. L'usuari ho fa manualment.
    if hours_configured(season) and not drafts and teams:
        drafts = (
            db.query(Training)
            .options(*_draft_opts)
            .filter(
                Training.season_id == season_id,
                Training.is_draft.is_(True),
            )
            .order_by(Training.session_date, Training.start_time)
            .all()
        )
    venues = (
        db.query(Venue)
        .options(joinedload(Venue.availabilities))
        .filter(Venue.club_id == season.club_id)
        .order_by(Venue.name)
        .all()
    )
    series_counts: dict[str, int] = {}
    for t in trainings:
        if t.series_id:
            series_counts[t.series_id] = series_counts.get(t.series_id, 0) + 1

    hours_rows = [
        {
            "team": tm,
            "hours": effective_hours(tm, season),
            "is_override": tm.training_hours_week is not None,
        }
        for tm in teams
    ]
    people_missing = [
        tm
        for tm in teams
        if not db.query(TeamMembership.id)
        .filter(TeamMembership.team_id == tm.id)
        .first()
    ]
    plan_start, plan_end = default_plan_range()

    focus_mon = None
    if draft_week:
        try:
            focus_mon = monday_of(date.fromisoformat(draft_week))
        except ValueError:
            focus_mon = None

    # Gràfica: borrador si n’hi ha; si no, sessions confirmades; si no, setmana buida
    chart_sessions = drafts if drafts else trainings
    chart_source = "draft" if drafts else ("live" if trainings else "empty")
    if not focus_mon:
        focus_mon = monday_of(plan_start)
    if chart_sessions:
        draft_colors = draft_team_colors(chart_sessions)
    else:
        class _Fake:
            def __init__(self, team_id, team):
                self.team_id = team_id
                self.team = team

        draft_colors = draft_team_colors([_Fake(t.id, t) for t in teams])

    lang = get_lang(request)
    day_names = weekdays(lang)
    draft_chart = build_draft_week_chart(
        chart_sessions,
        venues=venues,
        focus_monday=focus_mon,
        team_colors=draft_colors or None,
        source=chart_source,
        weekday_names=day_names,
        tip_solape=translate(lang, "tr_chart_tip_solape"),
    )
    team_week_list = build_team_week_list(
        chart_sessions,
        teams=teams,
        monday=draft_chart.monday,
        colors=draft_colors or None,
        weekday_names=day_names,
    )
    draft_week_count = sum(
        1
        for t in drafts
        if draft_chart.monday <= t.session_date <= draft_chart.sunday
    )
    capacity = estimate_capacity(db, season)
    fit = build_fit_advice(db, season)

    return templates.TemplateResponse(
        request,
        "trainings.html",
        {
            **ctx,
            "trainings": trainings,
            "drafts": drafts,
            "draft_week_count": draft_week_count,
            "draft_chart": draft_chart,
            "team_week_list": team_week_list,
            "chart_source": chart_source,
            "draft_colors": draft_colors,
            "weekday_short": weekdays_short(lang),
            "teams": teams,
            "venues": venues,
            "series_counts": series_counts,
            "flash_created": created,
            "flash_series": series,
            "hours_rows": hours_rows,
            "default_hours": season.default_training_hours,
            "people_missing": people_missing,
            "hours_flash": request.session.pop("hours_flash", None),
            "plan_flash": request.session.pop("plan_flash", None),
            "plan_warnings": request.session.pop("plan_warnings", None),
            "plan_start": plan_start.isoformat(),
            "plan_end": plan_end.isoformat(),
            "capacity": capacity,
            "fit": fit,
            "groups_count": fit.groups_count,
            "solapes_count": fit.solapes_count,
            "draft_explain": request.session.pop("draft_explain", None),
            "can_revert_apply": can_revert_last_apply(db, season_id),
        },
    )


@app.get("/season/{season_id}/trainings/by-team", response_class=HTMLResponse)
def trainings_by_team_page(
    season_id: int, request: Request, db: Session = Depends(get_db)
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    teams = (
        db.query(Team)
        .filter(Team.season_id == season_id)
        .order_by(Team.name)
        .all()
    )
    venues = db.query(Venue).filter(Venue.club_id == season.club_id).all()
    start, _ = default_plan_range()
    end = start + timedelta(days=4)
    rows = (
        db.query(Training)
        .options(joinedload(Training.team), joinedload(Training.venue))
        .filter(
            Training.season_id == season_id,
            Training.is_draft.is_(True),
            Training.session_date >= start,
            Training.session_date <= end,
        )
        .order_by(Training.team_id, Training.session_date, Training.start_time)
        .all()
    )
    last_training = (
        db.query(Training)
        .filter(
            Training.season_id == season_id,
            Training.is_draft.is_(True),
        )
        .order_by(Training.created_at.desc())
        .first()
    )
    last_end_time = (
        last_training.end_time.strftime("%H:%M")
        if last_training and last_training.end_time
        else "19:00"
    )
    avail = (
        db.query(VenueAvailability)
        .filter(VenueAvailability.venue_id.in_([v.id for v in venues]))
        .all()
    )
    venue_day_ids: dict[int, set[int]] = {v.id: set() for v in venues}
    day_venue_ids: dict[int, set[int]] = {d: set() for d in range(7)}
    for a in avail:
        venue_day_ids.setdefault(a.venue_id, set()).add(a.weekday)
        day_venue_ids.setdefault(a.weekday, set()).add(a.venue_id)
    venues_for_day: dict[int, list[Venue]] = {
        d: [v for v in venues if v.id in day_venue_ids.get(d, set())] for d in range(7)
    }
    by_team: dict[int, list[Training]] = {}
    for t in rows:
        by_team.setdefault(t.team_id, []).append(t)
    return templates.TemplateResponse(
        request,
        "trainings_by_team.html",
        {
            **ctx,
            "teams": teams,
            "venues": venues,
            "by_team": by_team,
            "weekdays": weekdays(lang),
            "weekday_short": weekdays_short(lang),
            "last_end_time": last_end_time,
            "venues_for_day": venues_for_day,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "flash": request.session.pop("by_team_flash", None),
        },
    )


@app.post("/season/{season_id}/trainings/by-team")
async def trainings_by_team_add(
    season_id: int, request: Request, db: Session = Depends(get_db)
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    team_ids = [int(x) for x in form.getlist("team_ids") if str(x).isdigit()]
    active_days = [int(x) for x in form.getlist("active_days") if str(x).isdigit()]
    group_teams = form.get("group_teams") in ("1", "on")
    from_d = form.get("start_date") or None
    to_d = form.get("end_date") or None
    if not team_ids:
        request.session["by_team_flash"] = translate(lang, "tr_by_team_error")
        return RedirectResponse(f"/season/{season_id}/trainings/by-team", status_code=303)
    valid_teams = (
        db.query(Team.id)
        .filter(Team.season_id == season_id, Team.id.in_(team_ids))
        .count()
    )
    if valid_teams != len(team_ids):
        request.session["by_team_flash"] = translate(lang, "tr_by_team_error")
        return RedirectResponse(f"/season/{season_id}/trainings/by-team", status_code=303)
    if not active_days:
        request.session["by_team_flash"] = translate(lang, "tr_by_team_error")
        return RedirectResponse(f"/season/{season_id}/trainings/by-team", status_code=303)
    start = date.fromisoformat(from_d) if from_d else default_plan_range()[0]
    end = date.fromisoformat(to_d) if to_d else default_plan_range()[1]

    created = 0
    for d in sorted(active_days):
        start_t = form.get(f"start_{d}") or "19:00"
        end_t = form.get(f"end_{d}") or "20:30"
        venue_id = int(form.get(f"venue_{d}") or 0) or None
        st = time_from_input(start_t)
        et = time_from_input(end_t)
        if not st or not et or not venue_id:
            continue

        dates: list[date] = []
        current = start
        while current <= end:
            if current.weekday() == d:
                dates.append(current)
            current += timedelta(days=1)
        if not dates:
            continue

        group_id: int | None = None
        if group_teams and len(team_ids) > 1:
            g = create_group(
                db,
                season_id=season_id,
                team_ids=team_ids,
                mode="shared",
                overlap_minutes=0,
                weekdays=format_weekdays([d]),
                start_date=dates[0],
                end_date=dates[-1],
                start_time=st,
                end_time=et,
                venue_id=venue_id,
                is_draft=True,
            )
            if g:
                group_id = g.id

        if group_id:
            db.query(Training).filter(
                Training.season_id == season_id,
                Training.team_id.in_(team_ids),
                Training.session_date.in_(dates),
                Training.start_time == st,
                Training.end_time == et,
                Training.venue_id == venue_id,
                Training.is_draft.is_(True),
            ).update(
                {Training.training_group_id: group_id, Training.allows_share: True},
                synchronize_session=False,
            )

        for tid in team_ids:
            series = f"bt{tid}-{uuid.uuid4().hex[:6]}"
            for cur in dates:
                exists = (
                    db.query(Training.id)
                    .filter(
                        Training.season_id == season_id,
                        Training.team_id == tid,
                        Training.session_date == cur,
                        Training.start_time == st,
                        Training.end_time == et,
                        Training.venue_id == venue_id,
                    )
                    .first()
                )
                if not exists:
                    db.add(
                        Training(
                            season_id=season_id,
                            team_id=tid,
                            session_date=cur,
                            start_time=st,
                            end_time=et,
                            venue_id=venue_id,
                            is_draft=True,
                            is_manual=True,
                            series_id=series,
                            training_group_id=group_id,
                            allows_share=bool(group_id),
                        )
                    )
                    created += 1
    db.commit()
    import_draft_groups(db, season)
    request.session["by_team_flash"] = translate(lang, "tr_by_team_added")
    return RedirectResponse(f"/season/{season_id}/trainings/by-team", status_code=303)


@app.post("/season/{season_id}/trainings/by-team/batch-delete")
async def trainings_by_team_batch_delete(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    ids = [int(x) for x in form.getlist("training_ids") if str(x).isdigit()]
    count = 0
    for tid in ids:
        t = db.get(Training, tid)
        if t and t.season_id == season_id and t.is_draft:
            db.delete(t)
            count += 1
    if count:
        db.commit()
        import_draft_groups(db, season)
    request.session["by_team_flash"] = translate(lang, "tr_by_team_deleted_n").format(n=count)
    return RedirectResponse(f"/season/{season_id}/trainings/by-team", status_code=303)


@app.post("/season/{season_id}/trainings/batch/delete")
async def trainings_batch_delete(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    ids = [int(x) for x in form.getlist("training_ids") if str(x).isdigit()]
    if not ids:
        request.session["plan_flash"] = translate(lang, "tr_bulk_no_selection")
        return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)
    delete_series = form.get("delete_series") in ("1", "on", "true", "True")
    selected = db.query(Training).filter(Training.id.in_(ids), Training.season_id == season_id).all()
    to_delete = {t.id for t in selected}
    if delete_series and selected:
        series_ids = {t.series_id for t in selected if t.series_id}
        is_draft = selected[0].is_draft
        if series_ids:
            extra = db.query(Training).filter(
                Training.season_id == season_id,
                Training.series_id.in_(series_ids),
                Training.is_draft.is_(is_draft),
            ).all()
            to_delete.update(t.id for t in extra)
    for tid in to_delete:
        t = db.get(Training, tid)
        if t:
            db.delete(t)
    if to_delete:
        db.commit()
        import_draft_groups(db, season)
    request.session["plan_flash"] = translate(lang, "tr_bulk_deleted")
    return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)


@app.post("/season/{season_id}/trainings/batch/edit")
async def trainings_batch_edit(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    ids = [int(x) for x in form.getlist("training_ids") if str(x).isdigit()]
    if not ids:
        request.session["plan_flash"] = translate(lang, "tr_bulk_no_selection")
        return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)
    start = form.get("start_time", "").strip()
    end = form.get("end_time", "").strip()
    venue_raw = form.get("venue_id", "").strip()
    new_start = time_from_input(start) if start else None
    new_end = time_from_input(end) if end else None
    new_venue = int(venue_raw) if venue_raw else None
    rows = db.query(Training).filter(Training.id.in_(ids), Training.season_id == season_id).all()
    for t in rows:
        if start and new_start is not None:
            t.start_time = new_start
        if end and new_end is not None:
            t.end_time = new_end
        if venue_raw:
            t.venue_id = new_venue
    if rows:
        db.commit()
        import_draft_groups(db, season)
    request.session["plan_flash"] = translate(lang, "tr_bulk_edited")
    return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)


def _translate_plan_warnings(lang: str, warnings) -> list[str]:
    out: list[str] = []
    for w in warnings or []:
        code = w.code if hasattr(w, "code") else w.get("code")
        params = w.params if hasattr(w, "params") else w.get("params", {})
        key = f"tr_plan_warn_{code}"
        msg = translate(lang, key)
        if msg == key:
            out.append(f"{code}: {params}")
        else:
            try:
                out.append(msg.format(**params))
            except (KeyError, ValueError):
                out.append(msg)
    return out


@app.post("/season/{season_id}/trainings/plan/generate")
def trainings_plan_generate(
    season_id: int,
    request: Request,
    range_start: str = Form(...),
    draft_weeks: int = Form(1),
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    if not hours_configured(season):
        return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)
    try:
        start = date.fromisoformat(range_start)
        weeks = max(1, min(4, int(draft_weeks)))
        end = start + timedelta(days=7 * weeks - 1)
    except (ValueError, TypeError):
        request.session["plan_flash"] = translate(lang, "tr_plan_bad_dates")
        return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)

    result = generate_draft_plan(db, season=season, start=start, end=end)
    warn_msgs = _translate_plan_warnings(lang, result.warnings)
    if result.created:
        flash = translate(lang, "tr_plan_generated").format(
            n=result.created, discarded=result.discarded
        )
    elif result.warnings:
        flash = translate(lang, "tr_plan_none")
    else:
        flash = translate(lang, "tr_plan_none")
    request.session["plan_flash"] = flash
    if warn_msgs:
        request.session["plan_warnings"] = warn_msgs
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings/plan/apply")
async def trainings_plan_apply(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    form = await request.form()
    until_str = str(form.get("until") or "").strip()
    season = ctx["season"]
    until = date.fromisoformat(until_str) if until_str else (
        season.end_date or default_end_date_for_season(season.name)
    )
    lang = get_lang(request)
    n, _batch = apply_drafts(db, season_id, until=until)
    request.session["plan_flash"] = translate(lang, "tr_plan_applied").format(n=n)
    return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)


@app.post("/season/{season_id}/trainings/plan/revert-apply")
def trainings_plan_revert_apply(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    lang = get_lang(request)
    n = revert_last_apply(db, season_id)
    if n:
        request.session["plan_flash"] = translate(lang, "tr_plan_reverted").format(n=n)
    else:
        request.session["plan_flash"] = translate(lang, "tr_plan_revert_none")
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings/plan/discard")
def trainings_plan_discard(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    lang = get_lang(request)
    n = discard_drafts(db, season_id)
    request.session["plan_flash"] = translate(lang, "tr_plan_discarded").format(n=n)
    return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)


@app.post("/season/{season_id}/trainings/clear")
def trainings_clear_all(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    lang = get_lang(request)
    from app.db import Training

    n = (
        db.query(Training)
        .filter(Training.season_id == season_id, Training.is_draft.is_(False))
        .delete(synchronize_session=False)
    )
    db.commit()
    request.session["plan_flash"] = translate(lang, "tr_plan_cleared").format(n=n)
    return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)


@app.post("/season/{season_id}/matches/clear")
def matches_clear_all(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    lang = get_lang(request)
    from app.db import Match

    n = db.query(Match).filter(Match.season_id == season_id).delete(
        synchronize_session=False
    )
    db.commit()
    request.session["matches_flash"] = translate(lang, "matches_cleared").format(n=n)
    return RedirectResponse(f"/season/{season_id}/matches", status_code=303)


@app.get("/season/{season_id}/trainings/groups", response_class=HTMLResponse)
def trainings_groups_page(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    edit: str | None = None,
    propose: int | None = None,
    t_ids: str = "",
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    if not hours_configured(season):
        return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)
    lang = get_lang(request)
    refresh_group_labels(db, season_id)
    groups = load_groups(db, season_id)
    for g in groups:
        g.weekday_list = parse_weekdays(g.weekdays)
        g.member_labels = [
            team_display_label(m.team, season.club.name if season.club else None)
            for m in g.members
        ]
        g.member_team_ids = [m.team_id for m in g.members]
        g.member_entries = list(zip(g.member_labels, g.member_team_ids))
        g.venue_name = g.venue.name if g.venue else "—"
        g.time_label = (
            f"{g.start_time.strftime('%H:%M')}–{g.end_time.strftime('%H:%M')}"
            if g.start_time and g.end_time
            else "—"
        )
        g.date_label = (
            f"{g.start_date.strftime('%d/%m/%Y')} – {g.end_date.strftime('%d/%m/%Y')}"
            if g.start_date and g.end_date
            else "—"
        )
    taken = teams_in_groups(groups)
    teams = (
        db.query(Team)
        .filter(Team.season_id == season_id)
        .order_by(Team.branch.nulls_last(), Team.category.nulls_last(), Team.name)
        .all()
    )
    club_name = season.club.name if season.club else None
    for t in teams:
        t.display_label = team_display_label(t, club_name)

    edit_group = None
    edit_id = None
    if edit and str(edit).isdigit():
        edit_id = int(edit)
        edit_group = next((g for g in groups if g.id == edit_id), None)

    if edit_group:
        edit_member_ids = {m.team_id for m in edit_group.members}
        pick_teams = [t for t in teams]
        form_weekdays = edit_group.weekday_list
        form_selected = edit_member_ids
        edit_start = edit_group.start_date or default_plan_range()[0]
        edit_end = edit_group.end_date or default_plan_range()[1]
        edit_start_time = edit_group.start_time or time(9, 0)
        edit_end_time = edit_group.end_time or time(10, 30)
        edit_venue_id = edit_group.venue_id
    else:
        pick_teams = [t for t in teams]
        form_weekdays = preferred_weekdays_from_drafts(db, season_id)
        form_selected = set()
        edit_start, edit_end = default_plan_range()
        edit_start_time = time(9, 0)
        edit_end_time = time(10, 30)
        edit_venue_id = None

    class _Fake:
        def __init__(self, team_id, team):
            self.team_id = team_id
            self.team = team

    fake = [_Fake(t.id, t) for t in teams]
    colors = draft_team_colors(fake)
    venues = db.query(Venue).filter(Venue.club_id == season.club_id).all()
    propose_mode = bool(propose)
    draft_group_id = request.session.pop("group_propose_draft", None)
    training_ids = [int(x) for x in t_ids.split(",") if x.strip().isdigit()]
    propose_trainings = (
        db.query(Training)
        .filter(Training.id.in_(training_ids), Training.season_id == season_id)
        .all()
    )
    propose_team_ids = sorted({tr.team_id for tr in propose_trainings})
    venues = db.query(Venue).filter(Venue.club_id == season.club_id).all()
    start, end = default_plan_range()
    propose_weekdays = sorted({tr.weekday for tr in propose_trainings if tr.weekday is not None}) or [0]
    return templates.TemplateResponse(
        request,
        "trainings_groups.html",
        {
            **ctx,
            "groups": groups,
            "pick_teams": pick_teams,
            "free_teams": pick_teams,
            "edit_group": edit_group,
            "form_weekdays": form_weekdays,
            "form_selected": form_selected,
            "edit_start_date": edit_start.isoformat(),
            "edit_end_date": edit_end.isoformat(),
            "edit_start_time": edit_start_time.strftime("%H:%M"),
            "edit_end_time": edit_end_time.strftime("%H:%M"),
            "edit_venue_id": edit_venue_id,
            "capacity": estimate_capacity(db, season),
            "draft_colors": colors,
            "weekdays": weekdays(lang),
            "venues": venues,
            "flash": request.session.pop("groups_flash", None),
            "error": request.session.pop("groups_error", None),
            "propose_mode": propose_mode,
            "propose_training_ids": ",".join(str(x) for x in training_ids),
            "propose_team_ids": propose_team_ids,
            "propose_venues": venues,
            "propose_start_date": start.isoformat(),
            "propose_end_date": end.isoformat(),
            "propose_weekdays": propose_weekdays,
            "propose_draft_created": bool(draft_group_id),
            "propose_draft_message": translate(lang, "tr_groups_planning_updated") if draft_group_id else "",
            "propose_group_id": draft_group_id,
        },
    )


def _generate_group_draft(db: Session, season, group: TrainingGroup, team_ids: list[int]):
    """Crea sessions de borrador per a un TrainingGroup nou dins del seu període."""
    start = group.start_date or default_plan_range()[0]
    end = group.end_date or default_plan_range()[1]
    wds = parse_weekdays(group.weekdays)
    series = f"g{group.id}-{uuid.uuid4().hex[:8]}"
    current = start
    while current <= end:
        if current.weekday() in wds:
            for tid in team_ids:
                exists = (
                    db.query(Training.id)
                    .filter(
                        Training.season_id == season.id,
                        Training.team_id == tid,
                        Training.session_date == current,
                        Training.start_time == group.start_time,
                        Training.end_time == group.end_time,
                        Training.venue_id == group.venue_id,
                    )
                    .first()
                )
                if not exists:
                    db.add(
                        Training(
                            season_id=season.id,
                            team_id=tid,
                            session_date=current,
                            start_time=group.start_time,
                            end_time=group.end_time,
                            venue_id=group.venue_id,
                            allows_share=True,
                            is_draft=True,
                            is_manual=True,
                            training_group_id=group.id,
                            series_id=series,
                        )
                    )
        current += timedelta(days=1)
    db.commit()


def _refresh_training_draft(db: Session, season):
    """Recalcula el borrador amb les plantilles actuals (no toca el calendari oficial)."""
    start, _ = default_plan_range()
    end = min(
        default_plan_range()[1],
        season.end_date or default_end_date_for_season(season.name),
    )
    gen = generate_draft_plan(db, season=season, start=start, end=end)
    db.commit()
    import_draft_groups(db, season)
    return gen


@app.api_route(
    "/season/{season_id}/trainings/propose",
    methods=["GET", "POST"],
)
def trainings_propose_fit(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Proposar grups (sense solapes) + regenerar borrador."""
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    if not hours_configured(season):
        return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)

    result = propose_fit(db, season, with_solapes=False)
    gen = _refresh_training_draft(db, season)
    warn_msgs = _translate_plan_warnings(lang, gen.warnings)
    if warn_msgs:
        request.session["plan_warnings"] = warn_msgs

    if result.puzzle_ok and gen.created:
        request.session["plan_flash"] = translate(lang, "tr_fit_proposed_puzzle").format(
            sessions=gen.created,
            solo=result.solo_slots,
            shared=result.shared_slots,
        )
        request.session["draft_explain"] = "proposed_puzzle"
    elif not gen.created:
        request.session["plan_flash"] = translate(lang, "tr_fit_puzzle_impossible")
        request.session["draft_explain"] = "solo_empty"
    else:
        request.session["plan_flash"] = translate(lang, "tr_fit_propose_none")
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.api_route(
    "/season/{season_id}/trainings/propose-solapes",
    methods=["GET", "POST"],
)
def trainings_propose_solapes(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Pas 2: proposar solapes + regenerar borrador."""
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    if not hours_configured(season):
        return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)

    advice = build_fit_advice(db, season)
    want = max(advice.suggest_solapes, 4) if advice.needs_action else 0
    created = propose_solapes(db, season, max_solapes=want) if want else []
    gen = _refresh_training_draft(db, season)
    warn_msgs = _translate_plan_warnings(lang, gen.warnings)
    if warn_msgs:
        request.session["plan_warnings"] = warn_msgs
    if created:
        request.session["plan_flash"] = translate(lang, "tr_fit_proposed_solapes_detail").format(
            n=len(created),
            sessions=gen.created,
        )
        request.session["draft_explain"] = "proposed_solapes"
    else:
        request.session["plan_flash"] = translate(lang, "tr_fit_propose_solapes_none")
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings/groups")
async def trainings_groups_create(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    team_ids = [int(x) for x in form.getlist("team_ids") if str(x).isdigit()]
    wds = [int(x) for x in form.getlist("weekdays") if str(x).isdigit()]
    start_date = form.get("start_date") or None
    end_date = form.get("end_date") or None
    start_time = form.get("start_time") or "09:00"
    end_time = form.get("end_time") or "10:30"
    venue_id = int(form.get("venue_id") or 0) or None
    edit_raw = str(form.get("edit_group_id") or "").strip()
    if edit_raw.isdigit():
        g = update_group(
            db,
            season_id=season_id,
            group_id=int(edit_raw),
            team_ids=team_ids,
            weekdays=wds,
            start_date=date.fromisoformat(start_date) if start_date else None,
            end_date=date.fromisoformat(end_date) if end_date else None,
            start_time=time_from_input(start_time),
            end_time=time_from_input(end_time),
            venue_id=venue_id,
        )
        if not g:
            request.session["groups_error"] = translate(lang, "tr_groups_create_error")
            return RedirectResponse(
                f"/season/{season_id}/trainings/groups?edit={edit_raw}",
                status_code=303,
            )
        db.query(Training).filter(Training.training_group_id == g.id).delete(synchronize_session=False)
        db.commit()
        _generate_group_draft(db, season, g, [m.team_id for m in g.members])
        _refresh_training_draft(db, season)
        request.session["plan_flash"] = translate(lang, "tr_groups_planning_updated")
        return RedirectResponse(
            f"/season/{season_id}/trainings#draft", status_code=303
        )

    start_d = date.fromisoformat(start_date) if start_date else default_plan_range()[0]
    end_d = date.fromisoformat(end_date) if end_date else default_plan_range()[1]
    g = create_group(
        db,
        season_id=season_id,
        team_ids=team_ids,
        mode="shared",
        overlap_minutes=0,
        weekdays=wds,
        start_date=start_d,
        end_date=end_d,
        start_time=time_from_input(start_time),
        end_time=time_from_input(end_time),
        venue_id=venue_id,
        is_draft=True,
    )
    if not g:
        request.session["groups_error"] = translate(lang, "tr_groups_create_error")
        return RedirectResponse(f"/season/{season_id}/trainings/groups", status_code=303)
    _generate_group_draft(db, season, g, team_ids)
    _refresh_training_draft(db, season)
    request.session["plan_flash"] = translate(lang, "tr_groups_planning_updated")
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings/groups/propose")
def trainings_groups_propose(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    created = propose_groups(db, season, mode="shared")
    if created:
        _refresh_training_draft(db, season)
        request.session["plan_flash"] = translate(
            lang, "tr_groups_created_n"
        ).format(n=len(created))
        return RedirectResponse(
            f"/season/{season_id}/trainings#draft", status_code=303
        )
    request.session["groups_flash"] = translate(lang, "tr_groups_created_n").format(
        n=0
    )
    return RedirectResponse(f"/season/{season_id}/trainings/groups", status_code=303)


@app.post("/season/{season_id}/trainings/groups/generate-draft")
def trainings_groups_generate_draft(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    n = generate_draft_from_groups(db, season)
    request.session["plan_flash"] = translate(lang, "tr_groups_draft_generated").format(n=n)
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings/groups/import-draft")
def trainings_groups_import_draft(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    result = import_draft_groups(db, season)
    msg = translate(lang, "tr_draft_import_done")
    if msg:
        request.session["plan_flash"] = msg.format(
            created=result["created"], linked=result["linked"]
        )
    else:
        request.session["plan_flash"] = f"Creats {result['created']} grups, {result['linked']} sessions vinculades"
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings/groups/clear-import")
def trainings_groups_clear_import(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    result = clear_draft_group_import(db, season)
    msg = translate(lang, "tr_draft_import_cleared")
    if msg:
        request.session["plan_flash"] = msg.format(
            deleted=result["deleted"], unlinked=result["unlinked"]
        )
    else:
        request.session["plan_flash"] = f"Esborrats {result['deleted']} grups, {result['unlinked']} sessions desvinculades"
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings/groups/{group_id}/delete")
def trainings_groups_delete(
    season_id: int,
    group_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    if delete_group(db, season_id, group_id):
        _refresh_training_draft(db, season)
        request.session["plan_flash"] = translate(lang, "tr_groups_deleted_planning")
        return RedirectResponse(
            f"/season/{season_id}/trainings#draft", status_code=303
        )
    return RedirectResponse(f"/season/{season_id}/trainings/groups", status_code=303)


@app.post("/season/{season_id}/trainings/groups/{group_id}/remove-team/{team_id}")
def trainings_groups_remove_team(
    season_id: int,
    group_id: int,
    team_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    g = db.get(TrainingGroup, group_id)
    if not g or g.season_id != season_id:
        return RedirectResponse(f"/season/{season_id}/trainings/groups", status_code=303)
    remaining_ids = [m.team_id for m in g.members if m.team_id != team_id]
    # Convertir les sessions de l'equip eliminat a manuals individuals
    db.query(Training).filter(
        Training.season_id == season_id,
        Training.training_group_id == group_id,
        Training.team_id == team_id,
        Training.is_draft.is_(True),
    ).update(
        {
            Training.training_group_id: None,
            Training.is_manual: True,
            Training.allows_share: False,
        },
        synchronize_session=False,
    )
    if len(remaining_ids) < 2:
        # Es desfà el grup perquè queda un sol equip
        db.query(Training).filter(
            Training.season_id == season_id,
            Training.training_group_id == group_id,
            Training.is_draft.is_(True),
        ).update(
            {
                Training.training_group_id: None,
                Training.is_manual: True,
                Training.allows_share: False,
            },
            synchronize_session=False,
        )
        db.delete(g)
        db.commit()
        _refresh_training_draft(db, season)
        request.session["groups_flash"] = translate(lang, "tr_group_broken")
        return RedirectResponse(f"/season/{season_id}/trainings/groups", status_code=303)
    g = update_group(
        db,
        season_id=season_id,
        group_id=group_id,
        team_ids=remaining_ids,
        weekdays=parse_weekdays(g.weekdays),
        start_date=g.start_date,
        end_date=g.end_date,
        start_time=g.start_time,
        end_time=g.end_time,
        venue_id=g.venue_id,
    )
    if g:
        db.query(Training).filter(Training.training_group_id == group_id).delete(synchronize_session=False)
        db.commit()
        _generate_group_draft(db, season, g, remaining_ids)
        _refresh_training_draft(db, season)
        request.session["groups_flash"] = translate(lang, "tr_group_team_removed")
    return RedirectResponse(f"/season/{season_id}/trainings/groups", status_code=303)


@app.post("/season/{season_id}/trainings/groups/{group_id}/break")
def trainings_groups_break(
    season_id: int,
    group_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    g = db.get(TrainingGroup, group_id)
    if not g or g.season_id != season_id:
        return RedirectResponse(f"/season/{season_id}/trainings/groups", status_code=303)
    db.query(Training).filter(
        Training.season_id == season_id,
        Training.training_group_id == group_id,
        Training.is_draft.is_(True),
    ).update(
        {
            Training.training_group_id: None,
            Training.is_manual: True,
            Training.allows_share: False,
        },
        synchronize_session=False,
    )
    db.delete(g)
    db.commit()
    _refresh_training_draft(db, season)
    request.session["groups_flash"] = translate(lang, "tr_group_broken")
    return RedirectResponse(f"/season/{season_id}/trainings/groups", status_code=303)


@app.get("/season/{season_id}/trainings/merge", response_class=HTMLResponse)
def trainings_merge_page(
    season_id: int,
    request: Request,
    t1: int,
    t2: int,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    t_a = db.get(Training, t1)
    t_b = db.get(Training, t2)
    if not t_a or not t_b or t_a.season_id != season_id or t_b.season_id != season_id:
        return RedirectResponse(f"/season/{season_id}/conflicts", status_code=303)
    people_a = people_for_team(db, t_a.team_id)
    people_b = people_for_team(db, t_b.team_id)
    shared = [p for p in people_a if p.id in {p.id for p in people_b}]
    proposals = suggest_training_merge(db, t_a, t_b)
    lang = get_lang(request)
    return templates.TemplateResponse(
        request,
        "trainings_merge.html",
        {
            **ctx,
            "t_a": t_a,
            "t_b": t_b,
            "shared_people": shared,
            "t_a_people": people_a,
            "t_b_people": people_b,
            "proposals": proposals,
            "weekdays": weekdays(lang),
        },
    )


@app.post("/season/{season_id}/trainings/merge/apply")
async def trainings_merge_apply(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    t1 = int(form.get("t1") or 0)
    t2 = int(form.get("t2") or 0)
    wds_raw = form.getlist("weekdays")
    wds = [int(x) for x in wds_raw if str(x).isdigit()]
    session_date = str(form.get("session_date") or "")
    start_time = str(form.get("start_time") or "")
    end_time = str(form.get("end_time") or "")
    venue_id = str(form.get("venue_id") or "")
    t_a = db.get(Training, t1)
    t_b = db.get(Training, t2)
    if not t_a or not t_b or t_a.season_id != season_id or t_b.season_id != season_id:
        return RedirectResponse(f"/season/{season_id}/conflicts", status_code=303)

    # Si ve d'una proposta concreta, usem el dia de la proposta com a setmana del grup
    if session_date and wds_raw and wds_raw[0].isdigit():
        wds = [int(wds_raw[0])]

    g = create_group(
        db,
        season_id=season_id,
        team_ids=[t_a.team_id, t_b.team_id],
        mode="shared",
        overlap_minutes=0,
        weekdays=wds,
    )
    if not g:
        request.session["groups_error"] = translate(lang, "tr_groups_create_error")
        return RedirectResponse(f"/season/{season_id}/trainings/merge?t1={t1}&t2={t2}", status_code=303)
    _refresh_training_draft(db, season)
    request.session["plan_flash"] = translate(lang, "tr_groups_planning_updated")
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.get("/season/{season_id}/trainings/solapes", response_class=HTMLResponse)
def trainings_solapes_page(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    edit: str | None = None,
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    if not hours_configured(season):
        return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)
    lang = get_lang(request)
    club_name = season.club.name if season.club else None
    solapes_raw = load_solapes(db, season_id)
    solapes = [solape_display(s, club_name) for s in solapes_raw]
    options = participant_options(db, season_id, club_name)

    edit_solape = None
    edit_id = None
    if edit and str(edit).isdigit():
        edit_id = int(edit)
        edit_solape = next((s for s in solapes if s["id"] == edit_id), None)

    if edit_solape:
        form_weekdays = edit_solape["weekdays"]
        form_code_a = edit_solape["code_a"]
        form_code_b = edit_solape["code_b"]
        form_overlap = edit_solape["overlap_minutes"]
    else:
        form_weekdays = preferred_weekdays_from_drafts(db, season_id) or list(
            DEFAULT_SOLAPE_WEEKDAYS
        )
        form_code_a = ""
        form_code_b = ""
        form_overlap = 0

    return templates.TemplateResponse(
        request,
        "trainings_solapes.html",
        {
            **ctx,
            "solapes": solapes,
            "options": options,
            "edit_solape": edit_solape,
            "form_weekdays": form_weekdays,
            "form_code_a": form_code_a,
            "form_code_b": form_code_b,
            "form_overlap": form_overlap,
            "overlap_choices": SOLAPE_OVERLAP_CHOICES,
            "capacity": estimate_capacity(db, season),
            "weekdays": weekdays(lang),
            "flash": request.session.pop("solapes_flash", None),
            "error": request.session.pop("solapes_error", None),
        },
    )


@app.post("/season/{season_id}/trainings/solapes")
async def trainings_solapes_create(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    side_a = SideKey.parse(str(form.get("side_a") or ""))
    side_b = SideKey.parse(str(form.get("side_b") or ""))
    try:
        overlap = int(str(form.get("overlap_minutes") or "0"))
    except ValueError:
        overlap = -1
    wds = [int(x) for x in form.getlist("weekdays") if str(x).isdigit()]
    edit_raw = str(form.get("edit_solape_id") or "").strip()

    if not side_a or not side_b:
        request.session["solapes_error"] = translate(lang, "tr_solapes_create_error")
        dest = (
            f"/season/{season_id}/trainings/solapes?edit={edit_raw}"
            if edit_raw.isdigit()
            else f"/season/{season_id}/trainings/solapes"
        )
        return RedirectResponse(dest, status_code=303)

    if edit_raw.isdigit():
        row = update_solape(
            db,
            season_id=season_id,
            solape_id=int(edit_raw),
            side_a=side_a,
            side_b=side_b,
            overlap_minutes=overlap,
            weekdays=wds,
        )
        if not row:
            request.session["solapes_error"] = translate(lang, "tr_solapes_create_error")
            return RedirectResponse(
                f"/season/{season_id}/trainings/solapes?edit={edit_raw}",
                status_code=303,
            )
        _refresh_training_draft(db, season)
        request.session["plan_flash"] = translate(lang, "tr_solapes_planning_updated")
        return RedirectResponse(
            f"/season/{season_id}/trainings#draft", status_code=303
        )

    row = create_solape(
        db,
        season_id=season_id,
        side_a=side_a,
        side_b=side_b,
        overlap_minutes=overlap,
        weekdays=wds,
    )
    if not row:
        request.session["solapes_error"] = translate(lang, "tr_solapes_create_error")
        return RedirectResponse(f"/season/{season_id}/trainings/solapes", status_code=303)
    _refresh_training_draft(db, season)
    request.session["plan_flash"] = translate(lang, "tr_solapes_planning_updated")
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings/solapes/{solape_id}/delete")
def trainings_solapes_delete(
    season_id: int,
    solape_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    if delete_solape(db, season_id, solape_id):
        _refresh_training_draft(db, season)
        request.session["plan_flash"] = translate(lang, "tr_solapes_deleted_planning")
        return RedirectResponse(
            f"/season/{season_id}/trainings#draft", status_code=303
        )
    return RedirectResponse(f"/season/{season_id}/trainings/solapes", status_code=303)


@app.post("/season/{season_id}/trainings/hours/default")
def trainings_hours_default(
    season_id: int,
    request: Request,
    hours: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    teams = (
        db.query(Team).filter(Team.season_id == season_id).order_by(Team.name).all()
    )
    value = parse_hours(hours)
    if value is None:
        return templates.TemplateResponse(
            request,
            "trainings_hours_setup.html",
            {
                **ctx,
                "teams": teams,
                "team_count": len(teams),
                "error": translate(lang, "tr_hours_invalid"),
                "draft_hours": hours or "4.5",
            },
            status_code=400,
        )
    season.default_training_hours = value
    db.commit()
    _refresh_training_draft(db, season)
    request.session["hours_flash"] = translate(lang, "tr_hours_default_ok").format(
        hours=value, n=len(teams)
    )
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.get("/season/{season_id}/trainings/hours", response_class=HTMLResponse)
def trainings_hours_edit(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    if not hours_configured(season):
        return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)
    teams = (
        db.query(Team)
        .filter(Team.season_id == season_id)
        .order_by(Team.branch.nulls_last(), Team.category.nulls_last(), Team.name)
        .all()
    )
    rows = [
        {
            "team": tm,
            "hours": effective_hours(tm, season),
            "is_override": tm.training_hours_week is not None,
        }
        for tm in teams
    ]
    return templates.TemplateResponse(
        request,
        "trainings_hours.html",
        {
            **ctx,
            "rows": rows,
            "default_hours": season.default_training_hours,
            "error": None,
            "flash": request.session.pop("hours_flash", None),
        },
    )


@app.post("/season/{season_id}/trainings/hours")
async def trainings_hours_save(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    default_raw = str(form.get("default_hours") or "")
    default_val = parse_hours(default_raw)
    if default_val is None:
        request.session["hours_flash"] = translate(lang, "tr_hours_invalid")
        return RedirectResponse(
            f"/season/{season_id}/trainings/hours", status_code=303
        )
    season.default_training_hours = default_val

    teams = db.query(Team).filter(Team.season_id == season_id).all()
    for tm in teams:
        key = f"hours_{tm.id}"
        use_default = form.get(f"use_default_{tm.id}")
        if use_default:
            tm.training_hours_week = None
            continue
        raw = str(form.get(key) or "")
        if not raw.strip():
            tm.training_hours_week = None
            continue
        val = parse_hours(raw)
        if val is None:
            continue
        if abs(val - default_val) < 1e-6:
            tm.training_hours_week = None
        else:
            tm.training_hours_week = val
    db.commit()
    _refresh_training_draft(db, season)
    request.session["hours_flash"] = translate(lang, "tr_hours_saved")
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings")
def trainings_create(
    season_id: int,
    request: Request,
    team_id: int = Form(...),
    session_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    venue_id: str = Form(""),
    allows_share: str | None = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    season = ctx.get("season") if ctx else None
    lang = get_lang(request)
    session_d = date.fromisoformat(session_date)
    st = time_from_input(start_time)
    et = time_from_input(end_time)
    venue = int(venue_id) if venue_id else None
    exists = (
        db.query(Training.id)
        .filter(
            Training.season_id == season_id,
            Training.team_id == team_id,
            Training.session_date == session_d,
            Training.start_time == st,
            Training.end_time == et,
            Training.venue_id == venue,
            Training.is_draft.is_(True),
        )
        .first()
    )
    if not exists:
        db.add(
            Training(
                season_id=season_id,
                team_id=team_id,
                session_date=session_d,
                start_time=st,
                end_time=et,
                venue_id=venue,
                allows_share=bool(allows_share),
                notes=notes.strip() or None,
                is_draft=True,
                is_manual=True,
            )
        )
        db.commit()
    if season:
        import_draft_groups(db, season)
    request.session["plan_flash"] = translate(lang, "tr_manual_added_draft")
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.post("/season/{season_id}/trainings/recurring")
def trainings_create_recurring(
    season_id: int,
    request: Request,
    team_id: int = Form(...),
    weekday: int = Form(...),
    range_start: str = Form(...),
    range_end: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    venue_id: str = Form(""),
    allows_share: str | None = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    lang = get_lang(request)
    series_id, n = create_weekly_series(
        db,
        season_id=season_id,
        team_id=team_id,
        weekday=weekday,
        start_date=date.fromisoformat(range_start),
        end_date=date.fromisoformat(range_end),
        start_time=time_from_input(start_time),
        end_time=time_from_input(end_time),
        venue_id=int(venue_id) if venue_id else None,
        allows_share=bool(allows_share),
        notes=notes.strip() or None,
        is_draft=True,
        is_manual=True,
    )
    if n and season:
        import_draft_groups(db, season)
    request.session["plan_flash"] = translate(lang, "tr_manual_series_draft").format(
        n=n
    )
    return RedirectResponse(
        f"/season/{season_id}/trainings?created={n}&series={series_id}#draft",
        status_code=303,
    )


@app.post("/season/{season_id}/trainings/{training_id}/delete")
def trainings_delete(
    season_id: int, training_id: int, db: Session = Depends(get_db)
):
    t = db.get(Training, training_id)
    if t and t.season_id == season_id:
        db.delete(t)
        db.commit()
        season = db.get(Season, season_id)
        if season:
            import_draft_groups(db, season)
    return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)


@app.post("/season/{season_id}/trainings/series/{series_id}/delete")
def trainings_delete_series(
    season_id: int, series_id: str, db: Session = Depends(get_db)
):
    rows = (
        db.query(Training)
        .filter(Training.season_id == season_id, Training.series_id == series_id)
        .all()
    )
    for t in rows:
        db.delete(t)
    if rows:
        db.commit()
        season = db.get(Season, season_id)
        if season:
            import_draft_groups(db, season)
    return RedirectResponse(f"/season/{season_id}/trainings", status_code=303)


@app.get("/season/{season_id}/conflicts", response_class=HTMLResponse)
def conflicts_page(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    auto_ok: int | None = None,
    auto_fail: int | None = None,
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    lang = get_lang(request)
    show_unique = request.query_params.get("unique") == "1"
    conflicts = find_conflicts(db, season_id, lang=lang)
    matches = (
        db.query(Match)
        .filter(Match.season_id == season_id)
        .all()
    )
    trainings = db.query(Training).filter(Training.season_id == season_id).all()
    match_team = {m.id: m.team_id for m in matches}
    training_team = {t.id: t.team_id for t in trainings}
    persist_conflicts(db, season_id, conflicts, match_team, training_team)
    by_h = group_conflicts_by_horizon(conflicts, matches, trainings)
    for bucket in HORIZON_ORDER:
        if bucket in by_h:
            by_h[bucket] = [c for c in by_h[bucket] if not c.ignored]
    match_team = {m.id: m.team_id for m in matches}
    training_team = {t.id: t.team_id for t in trainings}
    for bucket in HORIZON_ORDER:
        for c in by_h.get(bucket, []):
            c.key = conflict_key(c, match_team, training_team)
    if show_unique:
        seen_keys: set[str] = set()
        for bucket in HORIZON_ORDER:
            unique_bucket: list = []
            for c in by_h.get(bucket, []):
                if c.key not in seen_keys:
                    seen_keys.add(c.key)
                    unique_bucket.append(c)
            by_h[bucket] = unique_bucket
    conflicts_count = sum(len(by_h.get(b, [])) for b in HORIZON_ORDER)
    auto_report = None
    if auto_ok is not None:
        auto_report = translate(lang, "conflicts_auto_report").format(
            ok=auto_ok, fail=auto_fail or 0
        )
    conflict_flash = request.session.pop("conflict_flash", None)
    ignored_conflicts = (
        db.query(Conflict)
        .filter(Conflict.season_id == season_id, Conflict.ignored.is_(True))
        .order_by(Conflict.ignored_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "conflicts.html",
        {
            **ctx,
            "conflicts": conflicts,
            "conflicts_by_horizon": by_h,
            "conflicts_count": conflicts_count,
            "show_unique": show_unique,
            "ignored_conflicts": ignored_conflicts,
            "conflict_flash": conflict_flash,
            "horizon_order": HORIZON_ORDER,
            "horizon_labels": {
                "m1": translate(lang, "horizon_m1"),
                "m2": translate(lang, "horizon_m2"),
                "later": translate(lang, "horizon_later"),
                "undated": translate(lang, "horizon_undated"),
            },
        },
    )


@app.get("/season/{season_id}/conflict/{conflict_key_str}", response_class=HTMLResponse)
def conflict_detail(
    season_id: int,
    conflict_key_str: str,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    lang = get_lang(request)
    conflicts = find_conflicts(db, season_id, lang=lang)
    matches = db.query(Match).filter(Match.season_id == season_id).all()
    trainings = db.query(Training).filter(Training.season_id == season_id).all()
    match_team = {m.id: m.team_id for m in matches}
    training_team = {t.id: t.team_id for t in trainings}
    persist_conflicts(db, season_id, conflicts, match_team, training_team)
    all_confs = []
    for bucket in HORIZON_ORDER:
        all_confs.extend(group_conflicts_by_horizon(conflicts, matches, trainings).get(bucket, []))
    selected = None
    related = []
    for c in all_confs:
        if conflict_key(c, match_team, training_team) == conflict_key_str:
            c.key = conflict_key_str
            if selected is None:
                selected = c
            related.append(c)
    if not selected:
        request.session["conflict_flash"] = translate(lang, "conflict_already_resolved")
        return RedirectResponse(f"/season/{season_id}/conflicts", status_code=303)
    row = db.get(Conflict, selected.id) if selected.id else None
    ignored_dates = {i.ignored_date for i in (row.ignored_dates if row else [])}
    is_ignored_day = selected.d in ignored_dates if selected.d else False

    conflict_events: list[dict[str, object]] = []
    for mid in selected.match_ids:
        m = next((x for x in matches if x.id == mid), None)
        if not m or not m.start_time or not m.end_time:
            continue
        conflict_events.append(
            {
                "start_min": m.start_time.hour * 60 + m.start_time.minute,
                "end_min": m.end_time.hour * 60 + m.end_time.minute,
                "start": m.start_time,
                "end": m.end_time,
                "kind_label": "Partit",
                "label": m.team.name,
                "subtitle": f"vs {m.opponent or '?'} {'(local)' if m.is_home else '(fora)'}",
                "venue": m.venue.name if m.venue else "",
                "kind": "match",
            }
        )

    by_training_key: dict[int | tuple[time, time, int], list[Training]] = {}
    for tid in selected.training_ids:
        t = next((x for x in trainings if x.id == tid), None)
        if not t or not t.start_time or not t.end_time:
            continue
        key: int | tuple[time, time, int] = t.training_group_id or (t.start_time, t.end_time, t.venue_id or 0)
        by_training_key.setdefault(key, []).append(t)

    for cl in by_training_key.values():
        t0 = cl[0]
        team_names = [t.team.name for t in cl]
        categories = [t.team.category or "" for t in cl]
        if t0.training_group_id:
            kind_label = "Grup"
            label = (t0.training_group.label or ", ".join(team_names)) if t0.training_group else ", ".join(team_names)
        else:
            kind_label = "Entrenament"
            label = ", ".join(team_names)
        subtitle = ", ".join(c for c in categories if c)
        conflict_events.append(
            {
                "start_min": t0.start_time.hour * 60 + t0.start_time.minute,
                "end_min": t0.end_time.hour * 60 + t0.end_time.minute,
                "start": t0.start_time,
                "end": t0.end_time,
                "kind_label": kind_label,
                "label": label,
                "subtitle": subtitle,
                "venue": t0.venue.name if t0.venue else "",
                "kind": "training",
            }
        )
    conflict_events.sort(key=lambda x: x["start_min"])

    if selected.d:
        conflict_day_label = (
            f"{weekdays(lang)[selected.d.weekday()]}, "
            f"{selected.d.day} "
            f"{_month_short(lang, selected.d.month)} "
            f"{selected.d.strftime('%y')}"
        )
    else:
        conflict_day_label = ""
    return templates.TemplateResponse(
        request,
        "conflict_detail.html",
        {
            **ctx,
            "conflict": selected,
            "conflict_day": selected.d,
            "conflict_day_label": conflict_day_label,
            "conflict_events": conflict_events,
            "related": related,
            "matches": {m.id: m for m in matches},
            "trainings": {t.id: t for t in trainings},
            "ignored_series": row.ignored if row else False,
            "is_ignored_day": is_ignored_day,
        },
    )


@app.post("/season/{season_id}/conflict/{conflict_key}/ignore")
async def conflict_ignore(
    season_id: int,
    conflict_key: str,
    request: Request,
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    if not season:
        return RedirectResponse("/app", status_code=303)
    form = await request.form()
    scope = str(form.get("scope") or "").strip()
    row = (
        db.query(Conflict)
        .filter(Conflict.season_id == season_id, Conflict.conflict_key == conflict_key)
        .first()
    )
    if not row:
        return RedirectResponse(f"/season/{season_id}/conflicts", status_code=303)
    if scope == "series":
        row.ignored = True
        row.ignored_at = datetime.utcnow()
    elif scope == "day":
        day_str = str(form.get("day") or "").strip()
        if day_str:
            try:
                day = date.fromisoformat(day_str)
            except ValueError:
                day = None
            if day:
                exists = (
                    db.query(ConflictIgnored)
                    .filter(
                        ConflictIgnored.conflict_id == row.id,
                        ConflictIgnored.ignored_date == day,
                    )
                    .first()
                )
                if not exists:
                    db.add(ConflictIgnored(conflict_id=row.id, ignored_date=day))
    db.commit()
    return RedirectResponse(f"/season/{season_id}/conflict/{conflict_key}", status_code=303)


@app.post("/season/{season_id}/conflict/{conflict_key}/unignore")
async def conflict_unignore(
    season_id: int,
    conflict_key: str,
    request: Request,
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    if not season:
        return RedirectResponse("/app", status_code=303)
    form = await request.form()
    scope = str(form.get("scope") or "").strip()
    row = (
        db.query(Conflict)
        .filter(Conflict.season_id == season_id, Conflict.conflict_key == conflict_key)
        .first()
    )
    if not row:
        return RedirectResponse(f"/season/{season_id}/conflicts", status_code=303)
    if scope == "series":
        row.ignored = False
        row.ignored_at = None
    elif scope == "day":
        day_str = str(form.get("day") or "").strip()
        if day_str:
            try:
                day = date.fromisoformat(day_str)
            except ValueError:
                day = None
            if day:
                db.query(ConflictIgnored).filter(
                    ConflictIgnored.conflict_id == row.id,
                    ConflictIgnored.ignored_date == day,
                ).delete()
    db.commit()
    return RedirectResponse(f"/season/{season_id}/conflict/{conflict_key}", status_code=303)


@app.get("/season/{season_id}/trainings/group-propose")
def training_group_propose_redirect(
    season_id: int,
    request: Request,
    t: str = "",
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    return RedirectResponse(f"/season/{season_id}/trainings/groups?propose=1&t={t}#propose", status_code=303)


@app.post("/season/{season_id}/trainings/group-propose")
async def training_group_propose_submit(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    training_ids = [int(x) for x in str(form.get("training_ids", "")).split(",") if x.strip().isdigit()]
    trainings = db.query(Training).filter(Training.id.in_(training_ids), Training.season_id == season_id).all()
    team_ids = sorted({tr.team_id for tr in trainings})
    wds_raw = form.getlist("weekdays")
    wds = [int(x) for x in wds_raw if str(x).isdigit()]
    start_date = form.get("start_date") or None
    end_date = form.get("end_date") or None
    start_time = form.get("start_time") or "09:00"
    end_time = form.get("end_time") or "10:30"
    venue_id = int(form.get("venue_id") or 0) or None
    keep_originals = bool(form.get("keep_originals"))
    g = TrainingGroup(
        season_id=season_id,
        mode="shared",
        overlap_minutes=0,
        weekdays=format_weekdays(wds) if wds else "0",
        start_date=date.fromisoformat(start_date) if start_date else None,
        end_date=date.fromisoformat(end_date) if end_date else None,
        start_time=time_from_input(start_time),
        end_time=time_from_input(end_time),
        venue_id=venue_id,
        is_draft=True,
        label=group_label_for_teams([t.team for t in trainings]),
    )
    db.add(g)
    db.flush()
    for i, tid in enumerate(team_ids):
        db.add(TrainingGroupMember(group_id=g.id, team_id=tid, sort_order=i))
    db.commit()
    _generate_group_draft(db, season, g, team_ids)
    _refresh_training_draft(db, season)
    request.session["group_propose_draft"] = g.id
    return RedirectResponse(
        f"/season/{season_id}/trainings/groups?propose=1&t={','.join(str(x) for x in training_ids)}#propose",
        status_code=303,
    )


@app.post("/season/{season_id}/trainings/group-apply")
async def training_group_apply(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    lang = get_lang(request)
    form = await request.form()
    group_id = int(form.get("group_id") or 0)
    g = db.get(TrainingGroup, group_id)
    if g and g.season_id == season_id:
        g.is_draft = False
        db.query(Training).filter(
            Training.training_group_id == g.id,
            Training.is_draft.is_(True),
        ).update({"is_draft": False}, synchronize_session=False)
        db.commit()
        _refresh_training_draft(db, season)
        request.session["plan_flash"] = translate(lang, "tr_groups_planning_updated")
    return RedirectResponse(f"/season/{season_id}/trainings#draft", status_code=303)


@app.get("/season/{season_id}/federation-changes", response_class=HTMLResponse)
def federation_changes_page(
    season_id: int, request: Request, db: Session = Depends(get_db)
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    unseen = (
        db.query(FedMatchChange)
        .join(Match)
        .filter(
            Match.season_id == season_id,
            FedMatchChange.seen_at.is_(None),
        )
        .all()
    )
    now = datetime.utcnow()
    for fc in unseen:
        fc.seen_at = now
    if unseen:
        db.commit()
    changes = (
        db.query(FedMatchChange)
        .join(Match)
        .filter(Match.season_id == season_id)
        .order_by(FedMatchChange.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "federation_changes.html",
        {
            **ctx,
            "changes": changes,
            "changes_count": len(changes),
            "changes_with_conflicts": sum(1 for c in changes if c.has_conflict),
            "changes_locked": sum(1 for c in changes if c.is_locked),
        },
    )


@app.get("/season/{season_id}/overlaps", response_class=HTMLResponse)
def overlaps_page(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
    teams: str = "",
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    raw_ids = [x.strip() for x in teams.split(",") if x.strip().isdigit()]
    team_ids = [int(x) for x in raw_ids]
    selected_teams = (
        db.query(Team)
        .filter(Team.season_id == season_id, Team.id.in_(team_ids))
        .order_by(Team.name)
        .all()
        if team_ids
        else []
    )
    overlaps = find_team_overlaps(db, season_id, [t.id for t in selected_teams])
    lang = get_lang(request)
    return templates.TemplateResponse(
        request,
        "overlaps.html",
        {
            **ctx,
            "selected_teams": selected_teams,
            "overlaps": overlaps,
            "overlaps_by_horizon": group_overlaps_by_horizon(overlaps),
            "horizon_order": HORIZON_ORDER,
            "horizon_labels": {
                "m1": translate(lang, "horizon_m1"),
                "m2": translate(lang, "horizon_m2"),
                "m3": translate(lang, "horizon_m3"),
                "later": translate(lang, "horizon_later"),
                "undated": translate(lang, "horizon_undated"),
            },
        },
    )


def _parse_weekdays(raw: list[str] | None) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except ValueError:
            continue
    return out


@app.get("/season/{season_id}/matches/{match_id}/change", response_class=HTMLResponse)
def change_form(season_id: int, match_id: int):
    """Compat: la ficha vive en /matches?m=."""
    return RedirectResponse(
        f"/season/{season_id}/matches?m={match_id}#fitxa", status_code=303
    )


@app.post("/season/{season_id}/matches/{match_id}/change", response_class=HTMLResponse)
async def change_analyze(
    season_id: int,
    match_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)

    form = await request.form()
    proposed_date = str(form.get("proposed_date") or "")
    proposed_start = str(form.get("proposed_start") or "")
    proposed_venue_id = str(form.get("proposed_venue_id") or "")

    frame = ChangeFrame(
        window_start=date.today() - timedelta(days=7),
        window_end=date.today() + timedelta(days=30),
        allowed_weekdays=[],
        time_from=time(9, 0),
        time_to=time(21, 0),
        proposed_date=date.fromisoformat(proposed_date) if proposed_date else None,
        proposed_start=(
            time_from_input(proposed_start) if proposed_start else None
        ),
        proposed_venue_id=int(proposed_venue_id) if proposed_venue_id else None,
    )
    _match, concrete, alts, block_reason = analyze_change(db, match_id, frame)
    return _matches_page(
        request,
        db,
        ctx,
        m=match_id,
        result={
            "concrete": concrete,
            "alternatives": alts,
            "block_reason": block_reason,
            "frame": frame,
        },
    )


@app.post("/season/{season_id}/matches/{match_id}/apply")
def change_apply(
    season_id: int,
    match_id: int,
    match_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    venue_id: str = Form(""),
    force: str = Form(""),
    make_official: str = Form(""),
    db: Session = Depends(get_db),
):
    match = (
        db.query(Match)
        .options(joinedload(Match.team))
        .filter(Match.id == match_id, Match.season_id == season_id)
        .first()
    )
    if not match or match.locked or match.team.immovable:
        return RedirectResponse(f"/season/{season_id}/matches", status_code=303)

    md = date.fromisoformat(match_date)
    st = time_from_input(start_time)
    et = time_from_input(end_time)
    vid = int(venue_id) if venue_id else None

    opt = evaluate_slot(db, match, md, st, et, vid)
    if opt.hard and not force:
        return RedirectResponse(
            f"/season/{season_id}/matches?m={match_id}#fitxa", status_code=303
        )

    match.snapshot_official_from_current()
    match.match_date = md
    match.start_time = st
    match.end_time = et
    if match.is_home:
        match.venue_id = vid
    if make_official:
        match.set_official(
            md,
            st,
            et,
            match.venue_id if match.is_home else match.official_venue_id,
        )
    db.commit()
    return RedirectResponse(
        f"/season/{season_id}/matches?m={match_id}#fitxa", status_code=303
    )


@app.post("/season/{season_id}/conflicts/auto/{match_id}")
def conflicts_auto_one(
    season_id: int,
    match_id: int,
    db: Session = Depends(get_db),
):
    match = db.get(Match, match_id)
    if not match or match.season_id != season_id:
        return RedirectResponse(f"/season/{season_id}/conflicts", status_code=303)
    auto_fix_match(db, match_id)
    return RedirectResponse(f"/season/{season_id}/conflicts", status_code=303)


@app.post("/season/{season_id}/conflicts/auto-all")
def conflicts_auto_all(season_id: int, db: Session = Depends(get_db)):
    conflicts = find_conflicts(db, season_id)
    mids: list[int] = []
    for c in conflicts:
        if c.severity != "hard":
            continue
        mids.extend(c.match_ids or [])
    ok, fail, _failed = auto_fix_match_ids(db, mids)
    return RedirectResponse(
        f"/season/{season_id}/conflicts?auto_ok={ok}&auto_fail={fail}",
        status_code=303,
    )

@app.get("/season/{season_id}/import", response_class=HTMLResponse)
def import_page(
    season_id: int,
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    q = (q or request.query_params.get("q") or "").strip()
    hits = []
    error = None
    if q:
        try:
            hits = search_all_federations(q)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
    hit_groups = group_hits_by_team(hits)
    internal_teams = (
        db.query(Team.name)
        .filter(Team.season_id == season_id)
        .order_by(Team.name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "import.html",
        {
            **ctx,
            "source": "global",
            "q": q,
            "hits": hits,
            "hit_groups": hit_groups,
            "internal_teams": [t[0] for t in internal_teams],
            "error": error,
            "import_flash": request.session.pop("import_flash", None),
            "import_error": request.session.pop("import_error", None),
        },
    )


@app.post("/season/{season_id}/import/alias")
def import_add_alias(
    season_id: int,
    team_id: int = Form(...),
    external_name: str = Form(...),
    source: str = Form("rfep"),
    db: Session = Depends(get_db),
):
    name = external_name.strip()
    if name and source in FED_SOURCES:
        exists = (
            db.query(TeamExternalName)
            .filter(
                TeamExternalName.team_id == team_id,
                TeamExternalName.source == source,
                TeamExternalName.external_name == name,
            )
            .first()
        )
        if not exists:
            db.add(
                TeamExternalName(
                    team_id=team_id, source=source, external_name=name
                )
            )
            db.commit()
    return RedirectResponse(f"/season/{season_id}/import", status_code=303)


@app.get("/season/{season_id}/import/preview", response_class=HTMLResponse)
def import_preview(
    season_id: int,
    request: Request,
    source: str = "",
    idc: str = "",
    label: str = "",
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    try:
        idc_int = int(idc.strip())
    except ValueError:
        idc_int = 0
    if not idc_int or source not in FED_SOURCES:
        return RedirectResponse(f"/season/{season_id}/import", status_code=303)

    from app.import_fed import fetch_official_teams
    try:
        external_teams = fetch_official_teams(source, idc_int)
    except Exception as exc:  # noqa: BLE001
        request.session["import_error"] = str(exc)
        return RedirectResponse(f"/season/{season_id}/import", status_code=303)

    internal_teams = (
        db.query(Team)
        .filter(Team.season_id == season_id)
        .order_by(Team.name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "import_link.html",
        {
            **ctx,
            "source": source,
            "idc": idc,
            "label": label,
            "external_teams": external_teams,
            "internal_teams": internal_teams,
        },
    )


@app.post("/season/{season_id}/import/run", response_class=HTMLResponse)
async def import_run(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    form = await request.form()
    q = str(form.get("q") or "").strip()
    picks = form.getlist("pick")
    if not picks:
        request.session["import_error"] = translate(
            get_lang(request), "rfep_need_pick"
        )
        return RedirectResponse(f"/season/{season_id}/import?q={q}", status_code=303)

    selections_by_source: dict[str, list[tuple[int, str, str, str]]] = {}
    for raw in picks:
        parts = str(raw).split("||", 4)
        if len(parts) != 5:
            continue
        src, idc_s, ext_name, comp, idx = [p.strip() for p in parts]
        if src not in FED_SOURCES:
            continue
        try:
            idc = int(idc_s)
        except ValueError:
            continue
        internal_name = str(form.get(f"internal_name_{idx}") or "").strip()
        selections_by_source.setdefault(src, []).append(
            (idc, ext_name, comp, internal_name)
        )

    if not selections_by_source:
        request.session["import_error"] = translate(
            get_lang(request), "rfep_need_pick"
        )
        return RedirectResponse(f"/season/{season_id}/import?q={q}", status_code=303)

    reports: list[ImportReport] = []
    for src, sels in selections_by_source.items():
        reports.extend(
            import_selected_fed_teams(db, season_id, sels, source=src)
        )

    errors = [r.error for r in reports if r.error]
    if errors:
        request.session["import_error"] = " · ".join(errors)
        return RedirectResponse(f"/season/{season_id}/import?q={q}", status_code=303)

    lang = get_lang(request)
    n = len(picks)
    request.session["import_flash"] = translate(lang, "fed_import_ok").format(n=n)
    return RedirectResponse(f"/season/{season_id}/import?q={q}", status_code=303)


@app.post("/season/{season_id}/matches/dedup")
def dedup_matches_route(
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    if not is_admin(request):
        return RedirectResponse(f"/season/{season_id}", status_code=303)
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    n = dedup_matches(db, season_id)
    lang = get_lang(request)
    request.session["import_flash"] = translate(lang, "matches_cleared").format(n=n)
    return RedirectResponse(f"/season/{season_id}/calendar", status_code=303)


@app.post("/season/{season_id}/import/sources/{source_id}/delete")
def import_source_delete(
    season_id: int,
    source_id: int,
    db: Session = Depends(get_db),
):
    s = db.get(CompetitionSource, source_id)
    if not s:
        return RedirectResponse(f"/season/{season_id}/import", status_code=303)
    season = db.get(Season, season_id)
    if not season or s.season_id != season_id:
        return RedirectResponse(f"/season/{season_id}/import", status_code=303)
    db.delete(s)
    db.commit()
    return RedirectResponse(f"/season/{season_id}/import", status_code=303)


@app.get("/season/{season_id}/calendar", response_class=HTMLResponse)
def calendar_week(
    season_id: int,
    request: Request,
    day: str | None = None,
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    season = ctx["season"]
    focus = date.fromisoformat(day) if day else date.today()
    today = date.today()
    from app.calendar_week import build_global_draft
    from app.db import Training
    (
        draft_days,
        draft_hours,
        draft_grid,
        draft_start,
        draft_end,
        day_start_min,
        day_range,
        day_max_lanes,
    ) = build_global_draft(db, season_id, focus, today=today)
    has_live_trainings = (
        db.query(Training)
        .filter(Training.season_id == season_id, Training.is_draft.is_(False))
        .first()
        is not None
    )
    lang = get_lang(request)

    # Etiquetas de navegación (locales, sin depender de claves i18n nuevas)
    _nav = {
        "ca": ("Setmana", "anterior", "següent"),
        "es": ("Semana", "anterior", "siguiente"),
        "en": ("Week", "previous", "next"),
        "pt": ("Semana", "anterior", "seguinte"),
        "fr": ("Semaine", "précédente", "suivante"),
        "it": ("Settimana", "precedente", "successiva"),
        "de": ("Woche", "vorherige", "nächste"),
    }
    nav_week, nav_prev, nav_next = _nav.get(lang, _nav["ca"])

    return templates.TemplateResponse(
        request,
        "calendar.html",
        {
            **ctx,
            "draft_days": draft_days,
            "draft_hours": draft_hours,
            "draft_grid": draft_grid,
            "draft_start": draft_start,
            "draft_end": draft_end,
            "day_start_min": day_start_min,
            "day_range": day_range,
            "day_max_lanes": day_max_lanes,
            "today": today,
            "weekday_names": weekdays(lang),
            "focus_day": focus.isoformat(),
            "prev_day": (focus - timedelta(days=7)).isoformat(),
            "next_day": (focus + timedelta(days=7)).isoformat(),
            "has_live_trainings": has_live_trainings,
            "nav_week": nav_week,
            "nav_prev": nav_prev,
            "nav_next": nav_next,
        },
    )


@app.get("/season/{season_id}/season", response_class=HTMLResponse)
def season_tools(season_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    return templates.TemplateResponse(
        request, "season.html", {**ctx, "error": None}
    )


@app.post("/season/{season_id}/copy", response_class=HTMLResponse)
def season_copy_post(
    season_id: int,
    request: Request,
    new_name: str = Form(...),
    copy_unavailability: str | None = Form(None),
    copy_aliases: str | None = Form(None),
    db: Session = Depends(get_db),
):
    ctx = _active_context(request, db, season_id)
    if not ctx or not ctx.get("season"):
        return RedirectResponse("/app", status_code=303)
    try:
        dst = copy_season(
            db,
            season_id,
            new_name,
            copy_unavailability=bool(copy_unavailability),
            copy_aliases=bool(copy_aliases),
        )
        return RedirectResponse(f"/season/{dst.id}", status_code=303)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "season.html",
            {**ctx, "error": str(exc)},
            status_code=400,
        )


@app.get("/season/{season_id}/export/matches")
def export_matches(season_id: int, db: Session = Depends(get_db)):
    season = db.get(Season, season_id)
    if not season:
        return RedirectResponse("/app", status_code=303)
    content = export_matches_csv(db, season_id)
    data = ("\ufeff" + content).encode("utf-8")
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{export_filename("partidos", season.name)}"'
            )
        },
    )


@app.get("/season/{season_id}/export/trainings")
def export_trainings(season_id: int, db: Session = Depends(get_db)):
    season = db.get(Season, season_id)
    if not season:
        return RedirectResponse("/app", status_code=303)
    content = export_trainings_csv(db, season_id)
    data = ("\ufeff" + content).encode("utf-8")
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{export_filename("entrenos", season.name)}"'
            )
        },
    )


@app.get("/privacitat", response_class=HTMLResponse)
def privacy_page(request: Request):
    email = contact_email()
    return templates.TemplateResponse(
        request,
        "privacy.html",
        {
            "contact_email": email,
            "contact_email_b64": base64.b64encode(email.encode("utf-8")).decode("ascii"),
        },
    )


@app.get("/guia", response_class=HTMLResponse)
def guide_page(request: Request):
    g = get_guide(get_lang(request))
    email = contact_email()
    return templates.TemplateResponse(
        request,
        "guide.html",
        {
            "g": g,
            "contact_email": email,
            "contact_email_b64": base64.b64encode(email.encode("utf-8")).decode("ascii"),
        },
    )


@app.get("/ajuda", response_class=HTMLResponse)
def help_page(request: Request, db: Session = Depends(get_db)):
    ctx = _active_context(request, db)
    if not ctx:
        return RedirectResponse("/login", status_code=303)
    sections = get_help(get_lang(request))
    return templates.TemplateResponse(request, "help.html", {**ctx, "sections": sections})


# Session debe ejecutarse antes que el guard de club
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    same_site="lax",
    https_only=https_cookies(),
)
