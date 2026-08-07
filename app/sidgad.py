"""Cliente Sidgad genérico (RFEP / FECAPA) + parseo de calendario."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup

SIDGAD_BASE = "https://www.server2.sidgad.es"
IDM = "1"

FEDERATIONS = {
    "rfep": {
        "cliente": "rfep",
        "origin": "https://www.hockeypatines.fep.es",
        "referer": "https://www.hockeypatines.fep.es/league/{idc}",
        "site_lang": "es",
    },
    "fecapa": {
        "cliente": "fecapa",
        "origin": "https://www.hoqueipatins.fecapa.cat",
        "referer": "https://www.hoqueipatins.fecapa.cat/",
        "site_lang": "ca",
    },
    "fgp": {
        "cliente": "fgpatinaxe",
        "origin": "https://www.hockeypatines.fgpatinaxe.gal",
        "referer": "https://www.hockeypatines.fgpatinaxe.gal/",
        "site_lang": "es",
    },
    "fap": {
        "cliente": "fap",
        "origin": "https://www.hockeypatines.fapatinaje.org",
        "referer": "https://www.hockeypatines.fapatinaje.org/",
        "site_lang": "es",
    },
    "fmp": {
        "cliente": "fmp",
        "origin": "http://www.hockeypatines.fmp.es",
        "referer": "http://www.hockeypatines.fmp.es/",
        "site_lang": "es",
    },
    "fnp": {
        "cliente": "fnp",
        "origin": "http://hockey.fnp.org",
        "referer": "http://hockey.fnp.org/",
        "site_lang": "es",
    },
    "fpcv": {
        "cliente": "fpcv",
        "origin": "https://www.hockeypatines.fpcv.es",
        "referer": "https://www.hockeypatines.fpcv.es/",
        "site_lang": "es",
        "idm": "1",
    },
}


@dataclass
class CalendarMatch:
    idp: int | None
    idc: int
    jornada: int | None
    fecha: str | None  # DD/MM/YYYY
    hora: str | None  # HH:MM
    local: str
    visitante: str
    gamedate: str | None  # YYYYMMDD
    # Pista / localidad Sidgad (celda junto a fecha-hora; a menudo vacía en RFEP)
    lugar: str | None = None


class SidgadClient:
    def __init__(self, source: str = "rfep", sleep_s: float = 0.25) -> None:
        if source not in FEDERATIONS:
            raise ValueError(f"Fuente Sidgad no soportada: {source}")
        self.source = source
        self.cfg = FEDERATIONS[source]
        self.cliente = self.cfg["cliente"]
        self.idm = self.cfg.get("idm", IDM)
        self.sleep_s = sleep_s
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*",
                "Origin": self.cfg["origin"],
            }
        )

    def _post(self, path: str, idc: int | None, data: dict[str, Any]) -> str:
        url = f"{SIDGAD_BASE}/{self.cliente}/{path}"
        referer = self.cfg["referer"]
        if "{idc}" in referer and idc is not None:
            referer = referer.format(idc=idc)
        headers = {"Referer": referer}
        resp = self.session.post(url, data=data, headers=headers, timeout=90)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        if self.sleep_s:
            time.sleep(self.sleep_s)
        return resp.text

    def fetch_calendar(self, idc: int) -> str:
        path = f"{self.cliente}_cal_idc_{idc}_{self.idm}.php"
        return self._post(
            path,
            idc,
            {
                "idc": idc,
                "tipo_stats": "",
                "site_lang": self.cfg["site_lang"],
            },
        )

    def fetch_competition_list(self) -> str:
        path = f"{self.cliente}_ls_{self.idm}.php"
        return self._post(path, None, {"site_lang": self.cfg["site_lang"]})


def parse_competition_list(html: str, *, latest_only: bool = True) -> list[tuple[int, str]]:
    """Devuelve [(idc, nombre), ...] de la temporada Sidgad más reciente."""
    rows: list[tuple[int, str, int]] = []  # idc, name, temp
    seen: set[int] = set()

    patterns = [
        r'class="([^"]*listado_competiciones_fila[^"]*)"[^>]*\bid=["\']?(\d+)["\'][^>]*idc_name=["\']([^"\']+)',
        r'\bid=["\']?(\d+)["\'][^>]*class="([^"]*listado_competiciones_fila[^"]*)"[^>]*idc_name=["\']([^"\']+)',
    ]
    for idx, pat in enumerate(patterns):
        for m in re.finditer(pat, html, flags=re.I):
            if idx == 0:
                cls, idc_s, name = m.group(1), m.group(2), m.group(3).strip()
            else:
                idc_s, cls, name = m.group(1), m.group(2), m.group(3).strip()
            idc = int(idc_s)
            if idc in seen:
                continue
            tm = re.search(r"temp_(\d+)", cls)
            temp = int(tm.group(1)) if tm else 0
            seen.add(idc)
            rows.append((idc, name, temp))

    if not rows:
        for m in re.finditer(
            r'id=["\']?(\d+)["\'][^>]*idc_name=["\']([^"\']+)',
            html,
            flags=re.I,
        ):
            idc = int(m.group(1))
            if idc in seen:
                continue
            seen.add(idc)
            rows.append((idc, m.group(2).strip(), 0))

    max_temp = max((t for _, _, t in rows), default=0)
    if latest_only and max_temp:
        rows = [r for r in rows if r[2] == max_temp]

    priority = (
        "nacional catalana",
        "primera catalana",
        "segunda catalana",
        "segona catalana",
        "tercera catalana",
        "lliga catalana",
        "ok liga",
    )

    def sort_key(item: tuple[int, str, int]) -> tuple:
        idc, name, _temp = item
        n = name.casefold()
        prio = 99
        for i, key in enumerate(priority):
            if key in n:
                prio = i
                break
        return (prio, n, -idc)

    rows.sort(key=sort_key)
    return [(idc, name) for idc, name, _t in rows]


def _synthetic_idp(
    idc: int, gamedate: str | None, local: str, visitante: str, jornada: int | None
) -> int:
    key = f"{idc}|{gamedate or ''}|{jornada or ''}|{local}|{visitante}"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return -((int(digest[:8], 16) % 1_000_000_000) + 1)


def parse_calendar(html: str, idc: int) -> list[CalendarMatch]:
    soup = BeautifulSoup(html, "lxml")
    out: list[CalendarMatch] = []
    seen_idp: set[int] = set()
    seen_key: set[str] = set()

    rows = soup.select("tr.team_class")
    if not rows:
        rows = [icon.find_parent("tr") for icon in soup.select(".game_report[idp]")]
        rows = [r for r in rows if r is not None]

    for tr in rows:
        names = [d.get_text(" ", strip=True) for d in tr.select(".nombre_junto_logo")]
        if len(names) < 2:
            continue
        local, visitante = names[0], names[1]
        if not local or not visitante:
            continue

        icon = tr.select_one(".game_report[idp]")
        idp = None
        if icon and icon.get("idp"):
            try:
                idp = int(icon.get("idp"))
            except ValueError:
                idp = None

        jornada_el = tr.select_one(".jor_in_games")
        jornada = None
        if jornada_el:
            m = re.search(r"(\d+)", jornada_el.get_text(" ", strip=True))
            jornada = int(m.group(1)) if m else None

        fecha = None
        hora = None
        lugar = None
        less = [td.get_text(" ", strip=True) for td in tr.select("td.tabla_standard_less")]
        for cell in less:
            if not cell:
                continue
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", cell):
                fecha = cell
            elif re.fullmatch(r"\d{1,2}:\d{2}", cell):
                hora = cell
            elif not lugar:
                # Tercera celda less: pista / pabellón / localidad
                lugar = cell

        gamedate = tr.get("gamedate")
        if idp is None:
            idp = _synthetic_idp(idc, gamedate, local, visitante, jornada)

        if idp in seen_idp:
            continue
        key = f"{gamedate}|{local}|{visitante}|{jornada}"
        if key in seen_key:
            continue
        seen_idp.add(idp)
        seen_key.add(key)

        row_idc = idc
        if icon and icon.get("idc"):
            try:
                row_idc = int(icon.get("idc"))
            except ValueError:
                row_idc = idc

        out.append(
            CalendarMatch(
                idp=idp,
                idc=row_idc,
                jornada=jornada,
                fecha=fecha,
                hora=hora,
                local=local,
                visitante=visitante,
                gamedate=gamedate,
                lugar=lugar,
            )
        )

    out.sort(key=lambda m: (m.jornada or 999, m.gamedate or "", abs(m.idp or 0)))
    return out


# Compatibilidad con imports antiguos
class SidgadClientRFEP(SidgadClient):
    def __init__(self, sleep_s: float = 0.25) -> None:
        super().__init__("rfep", sleep_s=sleep_s)
