"""Probe FECAPA Sidgad endpoints."""
from __future__ import annotations

import re

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def main() -> None:
    r = requests.get(
        "https://www.hoqueipatins.fecapa.cat/",
        timeout=30,
        headers=HEADERS,
    )
    print("portal", r.status_code, len(r.text))
    urls = sorted(set(re.findall(r"https?://[^\"'\s<>]+sidgad[^\"'\s<>]*", r.text)))
    print("sidgad urls", urls[:30])
    scripts = re.findall(r"src=[\"']([^\"']+)[\"']", r.text)
    print("scripts", scripts[:40])
    # inline mentions
    for pat in ["fecapa_cal", "server2", "sidgad.cloud", "idc", "cliente"]:
        if pat in r.text:
            print("found inline", pat)

    # Try common calendar endpoints with a guessed idc
    candidates = []
    for base in (
        "https://sidgad.cloud/fecapa",
        "https://www.server2.sidgad.es/fecapa",
    ):
        for idc in (1, 100, 1000, 2000, 3000):
            for path in (
                f"fecapa_cal_idc_{idc}_1.php",
                f"fecapa_cal_idc_{idc}_2.php",
            ):
                candidates.append((f"{base}/{path}", idc))

    session = requests.Session()
    session.headers.update(
        {
            **HEADERS,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.hoqueipatins.fecapa.cat",
            "Referer": "https://www.hoqueipatins.fecapa.cat/",
        }
    )

    # First hit portal assets that might list competitions
    for url in [
        "https://sidgad.cloud/fecapa/",
        "https://www.hoqueipatins.fecapa.cat/ag/",
    ]:
        try:
            rr = session.get(url, timeout=20)
            print("GET", url, rr.status_code, len(rr.text), rr.url)
            if "cal_idc" in rr.text or "idc" in rr.text:
                hits = set(re.findall(r"[a-z]+_cal_idc_\d+_\d+\.php", rr.text))
                print("  cal paths", list(hits)[:20])
                idcs = set(re.findall(r"idc[=\"']+(\d+)", rr.text))
                print("  idcs sample", list(idcs)[:30])
        except Exception as exc:  # noqa: BLE001
            print("GET fail", url, exc)


if __name__ == "__main__":
    main()
