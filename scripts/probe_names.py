import requests
from bs4 import BeautifulSoup

s = requests.Session()
s.headers.update(
    {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.hoqueipatins.fecapa.cat",
        "Referer": "https://www.hoqueipatins.fecapa.cat/",
    }
)
cal = s.post(
    "https://www.server2.sidgad.es/fecapa/fecapa_cal_idc_10_1.php",
    data={"idc": 10, "tipo_stats": "", "site_lang": "ca"},
    timeout=60,
)
cal.encoding = cal.apparent_encoding or "utf-8"
names = sorted(
    {
        n.get_text(" ", strip=True)
        for n in BeautifulSoup(cal.text, "lxml").select(".nombre_junto_logo")
    }
)
for n in names:
    u = n.upper()
    if "MATAR" in u or "SHUM" in u or "MOLIN" in u:
        print(repr(n))
print("total", len(names))
