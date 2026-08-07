from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "main.py"
t = p.read_text(encoding="utf-8")
t = t.replace(
    "_active_context(db, season_id)",
    "_active_context(request, db, season_id)",
)
t = t.replace(
    'return RedirectResponse("/", status_code=303)',
    'return RedirectResponse("/app", status_code=303)',
)
# Fix null ctx access pattern
old = '    ctx = _active_context(request, db, season_id)\n    season = ctx["season"]\n    if not season:\n        return RedirectResponse("/app", status_code=303)'
new = '    ctx = _active_context(request, db, season_id)\n    if not ctx or not ctx.get("season"):\n        return RedirectResponse("/app", status_code=303)\n    season = ctx["season"]'
t = t.replace(old, new)
# season tools pattern
old2 = '    ctx = _active_context(request, db, season_id)\n    if not ctx["season"]:'
new2 = '    ctx = _active_context(request, db, season_id)\n    if not ctx or not ctx.get("season"):'
t = t.replace(old2, new2)
p.write_text(t, encoding="utf-8")
print("old_ctx", t.count("_active_context(db,"))
print("root_redirects", t.count('RedirectResponse("/",'))
print("ok")
