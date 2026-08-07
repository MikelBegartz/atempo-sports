import re
from pathlib import Path

html = Path("scripts/_fecapa_ls.html").read_text(encoding="utf-8", errors="replace")
temps = sorted(set(re.findall(r"temp_(\d+)", html)))
print("temps", temps[-20:], "n", len(temps))

# Sample rows with temp and idc_name
for m in re.finditer(
    r'class="([^"]*listado_competiciones_fila[^"]*)"[^>]*id="(\d+)"[^>]*idc_name="([^"]+)"',
    html,
):
    cls, idc, name = m.group(1), m.group(2), m.group(3)
    if "NACIONAL CATALANA MASCULINA" in name.upper():
        print(idc, name, cls[:120])

# alternate attr order
for m in re.finditer(
    r'id="(\d+)"[^>]*class="([^"]*listado_competiciones_fila[^"]*)"[^>]*idc_name="([^"]+)"',
    html,
):
    idc, cls, name = m.group(1), m.group(2), m.group(3)
    if "NACIONAL CATALANA MASCULINA" in name.upper():
        print("ALT", idc, name, cls[:120])
