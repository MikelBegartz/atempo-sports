"""Metadatos de equipos: secciones base/senior × mixt/femenino/masculino."""

from __future__ import annotations

from app.db import Team

BRANCH_BASE_MIXED = "base_mixed"
BRANCH_BASE_FEMALE = "base_female"
BRANCH_SENIOR_MALE = "senior_male"
BRANCH_SENIOR_FEMALE = "senior_female"

BRANCHES = (
    BRANCH_BASE_MIXED,
    BRANCH_BASE_FEMALE,
    BRANCH_SENIOR_MALE,
    BRANCH_SENIOR_FEMALE,
)

# Orden típico hockey / patín (más joven → más senior)
_CATEGORY_RANK = [
    "prebenjami",
    "prebenjamí",
    "benjami",
    "benjamí",
    "alevi",
    "aleví",
    "infantil",
    "cadet",
    "juvenil",
    "minifem",
    "mini fem",
    "fem 11",
    "fem11",
    "fem 13",
    "fem13",
    "fem 15",
    "fem15",
    "fem 17",
    "fem17",
    "fem 19",
    "fem19",
    "femení",
    "femeni",
    "sènior",
    "senior",
]


def normalize_branch(raw: str | None) -> str:
    v = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "base_mixed": BRANCH_BASE_MIXED,
        "base_mixte": BRANCH_BASE_MIXED,
        "base_mixta": BRANCH_BASE_MIXED,
        "mixed": BRANCH_BASE_MIXED,
        "mixte": BRANCH_BASE_MIXED,
        "mixt": BRANCH_BASE_MIXED,
        "mixto": BRANCH_BASE_MIXED,
        "base_female": BRANCH_BASE_FEMALE,
        "base_femenina": BRANCH_BASE_FEMALE,
        "base_femeni": BRANCH_BASE_FEMALE,
        "female": BRANCH_BASE_FEMALE,
        "femeni": BRANCH_BASE_FEMALE,
        "femení": BRANCH_BASE_FEMALE,
        "femenino": BRANCH_BASE_FEMALE,
        "senior_male": BRANCH_SENIOR_MALE,
        "senior_masculino": BRANCH_SENIOR_MALE,
        "senior_masculi": BRANCH_SENIOR_MALE,
        "male": BRANCH_SENIOR_MALE,
        "masculi": BRANCH_SENIOR_MALE,
        "masculí": BRANCH_SENIOR_MALE,
        "masculino": BRANCH_SENIOR_MALE,
        "senior_female": BRANCH_SENIOR_FEMALE,
        "senior_femenino": BRANCH_SENIOR_FEMALE,
        "senior_femeni": BRANCH_SENIOR_FEMALE,
        "senior_fem": BRANCH_SENIOR_FEMALE,
    }
    return aliases.get(v, BRANCH_BASE_MIXED)


def infer_branch(name: str = "", category: str | None = None) -> str:
    text = f"{category or ''} {name}".lower()
    is_female = any(
        x in text
        for x in (
            "femen",
            "femení",
            "femeni",
            "minifem",
            "mini fem",
            "fem 1",
            "fem1",
            "dona",
        )
    )
    is_senior = any(x in text for x in ("sènior", "senior", "absolut"))
    is_mixed = any(x in text for x in ("mixte", "mixt", "mixed", "mixto"))

    if is_senior and is_female:
        return BRANCH_SENIOR_FEMALE
    if is_senior:
        return BRANCH_SENIOR_MALE
    if is_female:
        return BRANCH_BASE_FEMALE
    if is_mixed:
        return BRANCH_BASE_MIXED
    # Por defecto: base mixta (prebenjamí, benjamí, aleví…)
    return BRANCH_BASE_MIXED


def team_branch(team: Team) -> str:
    stored = getattr(team, "branch", None)
    if stored in BRANCHES:
        return stored
    # Compatibilidad con valores antiguos
    if stored == "mixed":
        return BRANCH_BASE_MIXED
    if stored == "female":
        return BRANCH_BASE_FEMALE
    if stored == "male":
        return BRANCH_SENIOR_MALE
    return infer_branch(team.name, team.category)


def _rank(text: str) -> int:
    t = text.lower()
    for i, key in enumerate(_CATEGORY_RANK):
        if key in t:
            return i
    return len(_CATEGORY_RANK)


def team_sort_key(team: Team) -> tuple:
    blob = f"{team.category or ''} {team.name}"
    return (_rank(blob), (team.name or "").lower())


def group_teams_by_branch(teams: list[Team]) -> dict[str, list[Team]]:
    groups = {b: [] for b in BRANCHES}
    for t in teams:
        groups[team_branch(t)].append(t)
    for b in BRANCHES:
        groups[b].sort(key=team_sort_key)
    return groups
