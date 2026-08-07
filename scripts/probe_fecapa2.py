"""Deeper FECAPA Sidgad discovery."""
from __future__ import annotations

import re

import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def main() -> None:
    s = requests.Session()
    s.headers.update(UA)

    js = s.get("https://www.server2.sidgad.es/portales.js?v=1784581291", timeout=30)
    print("portales.js", js.status_code, len(js.text))
    for pat in [
        r"cliente\s*[:=]\s*['\"]([^'\"]+)['\"]",
        r"fecapa",
        r"cal_idc",
        r"server2\.sidgad",
        r"sidgad\.cloud",
        r"function\s+\w*cal\w*",
    ]:
        hits = re.findall(pat, js.text, flags=re.I)
        if hits:
            print(pat, hits[:15] if isinstance(hits[0], str) else hits[:5])

    # Snippets around fecapa
    for m in re.finditer(r".{0,80}fecapa.{0,120}", js.text, flags=re.I):
        print("CTX", m.group(0).replace("\n", " ")[:200])
        if m.start() > 500000:
            break

    portal = s.get("https://www.hoqueipatins.fecapa.cat/", timeout=30).text
    # Look for config objects
    for m in re.finditer(r".{0,40}(cliente|idc|id_portal|portal).{0,80}", portal, flags=re.I):
        line = m.group(0).replace("\n", " ")
        if "sidgad" in line.lower() or "cliente" in line.lower() or "idc" in line.lower():
            print("PORTAL", line[:220])

    cloud = s.get("https://sidgad.cloud/fecapa/", timeout=30)
    print("cloud root", cloud.status_code, cloud.headers.get("content-type"), len(cloud.text))
    print(cloud.text[:1500])

    # Try POST like RFEP with cliente fecapa on server2
    idc = 1
    for cliente in ("fecapa", "fcp", "fcpatinatge", "hoqueipatins"):
        path = f"{cliente}_cal_idc_{idc}_1.php"
        url = f"https://www.server2.sidgad.es/{cliente}/{path}"
        try:
            rr = s.post(
                url,
                data={"idc": idc, "tipo_stats": "", "site_lang": "ca"},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://www.hoqueipatins.fecapa.cat",
                    "Referer": "https://www.hoqueipatins.fecapa.cat/",
                },
                timeout=20,
            )
            print("POST", url, rr.status_code, len(rr.text), rr.text[:120].replace("\n", " "))
        except Exception as exc:  # noqa: BLE001
            print("POST fail", url, exc)


if __name__ == "__main__":
    main()
