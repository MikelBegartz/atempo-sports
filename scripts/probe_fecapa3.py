"""Find real FECAPA competition idc values and parse a calendar."""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_cal(s: requests.Session, idc: int) -> str:
    url = f"https://www.server2.sidgad.es/fecapa/fecapa_cal_idc_{idc}_1.php"
    rr = s.post(
        url,
        data={"idc": idc, "tipo_stats": "", "site_lang": "ca"},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.hoqueipatins.fecapa.cat",
            "Referer": f"https://www.hoqueipatins.fecapa.cat/",
        },
        timeout=30,
    )
    rr.raise_for_status()
    rr.encoding = rr.apparent_encoding or "utf-8"
    return rr.text


def main() -> None:
    s = requests.Session()
    s.headers.update(UA)
    portal = s.get("https://www.hoqueipatins.fecapa.cat/", timeout=30).text

    # Extract idc attributes from portal markup
    idcs = sorted({int(x) for x in re.findall(r'\bidc=["\']?(\d+)', portal)})
    print("idcs in portal html", idcs[:50], "count", len(idcs))

    name_idcs = sorted(set(re.findall(r'name=["\']([^"\']*idc[^"\']*)["\']', portal, flags=re.I)))
    print("name attrs", name_idcs[:40])

    # Also search data attributes / onclick
    for pat in [r"abrir_comp\((\d+)\)", r"carga\w*\((\d+)\)", r"idc=(\d+)"]:
        vals = sorted({int(x) for x in re.findall(pat, portal)})
        if vals:
            print(pat, vals[:40])

    # Dump interesting chunks with numbers that look like competition ids
    soup = BeautifulSoup(portal, "lxml")
    for el in soup.select("[idc], [name*='idc'], .div_titulo_fase_idc, a[onclick]"):
        print("EL", el.name, el.attrs, el.get_text(" ", strip=True)[:80])

    # Brute a range around typical values if portal has few
    if len(idcs) < 3:
        print("Scanning idc range...")
        hits = []
        for idc in list(range(2500, 2800)) + list(range(3500, 3800)) + list(range(1, 50)):
            html = fetch_cal(s, idc)
            rows = len(BeautifulSoup(html, "lxml").select("tr.team_class"))
            names = BeautifulSoup(html, "lxml").select(".nombre_junto_logo")
            if rows or len(names) >= 2:
                hits.append((idc, rows, len(names), len(html)))
                print("HIT", idc, "rows", rows, "names", len(names), "bytes", len(html))
                if len(hits) >= 8:
                    break
        print("hits", hits)
    else:
        for idc in idcs[:10]:
            html = fetch_cal(s, idc)
            rows = len(BeautifulSoup(html, "lxml").select("tr.team_class"))
            print("idc", idc, "bytes", len(html), "rows", rows)


if __name__ == "__main__":
    main()
