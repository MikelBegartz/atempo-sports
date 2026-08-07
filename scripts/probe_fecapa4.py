"""Fetch FECAPA competition list and a sample calendar."""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.hoqueipatins.fecapa.cat",
    "Referer": "https://www.hoqueipatins.fecapa.cat/",
}


def main() -> None:
    s = requests.Session()
    s.headers.update(HEADERS)

    # Competition list
    url = "https://www.server2.sidgad.es/fecapa/fecapa_ls_1.php"
    for payload in (
        {},
        {"site_lang": "ca"},
        {"temp": "2025"},
        {"temporada": "2025"},
        {"id_temp": "2025"},
        {"temp": "25"},
    ):
        rr = s.post(url, data=payload, timeout=30)
        print("LS", payload, rr.status_code, len(rr.text))
        if len(rr.text) > 500:
            open("scripts/_fecapa_ls.html", "w", encoding="utf-8").write(rr.text)
            ids = sorted({int(x) for x in re.findall(r'\bid=["\']?(\d+)', rr.text)})
            names = re.findall(r'idc_name=["\']([^"\']+)', rr.text)
            print("  ids", ids[:30], "n=", len(ids))
            print("  names", names[:15])
            break

    # Also try scorer menu
    for path in ("fecapa_mc_1.php", "fecapa_mc_1_horizontal.php"):
        rr = s.post(
            f"https://www.server2.sidgad.es/fecapa/{path}",
            data={"site_lang": "ca"},
            timeout=30,
        )
        print("MC", path, rr.status_code, len(rr.text))
        if len(rr.text) > 400:
            open(f"scripts/_{path}.html", "w", encoding="utf-8").write(rr.text)
            ids = sorted({int(x) for x in re.findall(r'\bid=["\']?(\d+)', rr.text)})
            print("  ids sample", ids[:40], "n=", len(ids))

    # If we have ids, fetch one calendar with matches
    html = open("scripts/_fecapa_ls.html", encoding="utf-8").read() if False else ""
    # re-read last successful
    try:
        html = open("scripts/_fecapa_ls.html", encoding="utf-8").read()
    except FileNotFoundError:
        html = ""
    ids = sorted({int(x) for x in re.findall(r'\bid=["\']?(\d+)', html)})
    if not ids:
        # from mc files
        for path in ("scripts/_fecapa_mc_1.php.html", "scripts/_fecapa_mc_1_horizontal.php.html"):
            try:
                html = open(path, encoding="utf-8").read()
                ids = sorted({int(x) for x in re.findall(r'\bid=["\']?(\d+)', html)})
                if ids:
                    break
            except FileNotFoundError:
                pass

    print("using ids", ids[:20])
    for idc in ids[:15]:
        cal_url = f"https://www.server2.sidgad.es/fecapa/fecapa_cal_idc_{idc}_1.php"
        cal = s.post(
            cal_url,
            data={"idc": idc, "tipo_stats": "", "site_lang": "ca"},
            timeout=30,
        )
        soup = BeautifulSoup(cal.text, "lxml")
        rows = soup.select("tr.team_class")
        names = [n.get_text(" ", strip=True) for n in soup.select(".nombre_junto_logo")]
        print(
            "CAL",
            idc,
            "bytes",
            len(cal.text),
            "rows",
            len(rows),
            "names",
            len(names),
            "sample",
            names[:4],
        )
        if rows:
            open("scripts/_fecapa_cal_sample.html", "w", encoding="utf-8").write(cal.text)
            break


if __name__ == "__main__":
    main()
