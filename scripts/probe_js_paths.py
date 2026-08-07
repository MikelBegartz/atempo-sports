import re
from pathlib import Path
text = Path("scripts/_portales.js").read_text(encoding="utf-8")
# extract php endpoint patterns
print("php paths:", sorted(set(re.findall(r"[\w/]+_[\w]+\.php|[\w]+\.php", text)))[:80])
print("---")
for m in re.finditer(r".{0,60}\.php.{0,80}", text):
    print(m.group(0).replace("\n", " ")[:180])
