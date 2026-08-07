import re
from pathlib import Path

html = Path("scripts/_fecapa_ls.html").read_text(encoding="utf-8", errors="replace")
for m in re.finditer(r".{0,40}MATAR.{0,80}", html, flags=re.I):
    print(m.group(0).replace("\n", " ")[:160])
    break

# Find competition rows that mention mataro in nearby club list - hard.
# Search idc_name rows containing mataro - unlikely.
# Look for club name text nodes
hits = re.findall(r">([^<]*MATAR[^<]*)<", html, flags=re.I)
print("text hits", hits[:20])
