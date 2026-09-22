# AtempoSports — notes per a agents

## Què és
AtempoSports: app web per a clubs d’esports (hockey) per gestionar calendaris, equips, pistes, entrenaments, partits, disponibilitats i conflictes d’horari. Beta tancada: 3 clubs, gratis aquest any. No obrir registre públic ni pagaments sense acord explícit.

## Idioma i comunicació
- UI per defecte: **català** (`ca`).
- Ordre de llengües actual: `ca`, `eu`, `gl`, `es`, `pt`, `fr`, `it`, `en`, `de`.
- Comunicar en català o castellà segons l’usuari.

## Fitxers clau
- `app/i18n.py` — `STRINGS` i `LANGUAGES`.
- `app/i18n_extras.py` — `AUTH_PACKS` i `apply_auth_packs()`.
- `i18n_missing.csv` — llistat de claus per idioma.
- `PRODUCT.md` i `.cursor/rules/workflow.mdc` — normes i roadmap.

## Estat i18n (actual)
- 9 idiomes actius, 885 claus cadascun.
- `ca` i `es`: originals, de referència.
- `eu`: corregit i complet.
- `gl`, `pt`, `fr`, `it`, `de`: esborranys automàtics (MyMemory / deep_translator); cal revisió humana.
- `en`: base de referència per `apply_auth_packs`.

## How-to i18n
1. Modificar `app/i18n_extras.py` (dins del `AUTH_PACKS` de l’idioma).
2. Verificar que `python -m py_compile app/i18n_extras.py` passi.
3. Importar `app.i18n` perquè `apply_auth_packs` ompli `STRINGS`.
4. Regenerar `i18n_missing.csv` i reiniciar `uvicorn` si no té `--reload`.

## Com arrencar el servidor local
Des del directori `C:\Users\mikel\OneDrive\Hockey\AtempoSports`:
```powershell
python -c "import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port=8002, reload=True)"
```
No usar `python -m uvicorn` des d'aquest directori, perquè altres paquets `app` del OneDrive poden fer ombra.

## Estat guia/help
- ✅ `/guia` pública redissenyada i traduïda als 9 idiomes (contingut a `app/guide_content.py`).
- ✅ `/ajuda` interna amb cerca, 11 seccions i P+R traduïdes als 9 idiomes (contingut a `app/help_content.py`).
- ✅ Etiquetes de UI `help_*` disponibles als 9 idiomes via `HELP_UI_PACKS` a `app/i18n_extras.py`.
- ✅ `i18n_missing.csv` regenerat automàticament.
- ✅ Claus `guide_*` no usades netejades de `app/i18n.py` i `app/i18n_extras.py`; només resten `guide_link` i `guide_title`.

## Resum del dia i pendents per a la propera sessió
- Correu `info@atemposports.com` activat a Cloudflare i enllaçat des de `/guia` i `/privacitat`.
- `ATEMPO_PUBLIC_REGISTER=0` a Render; registre tancat.
- Text de `/register` tancat actualitzat als 9 idiomes: fase beta, registre tancat, aviat al públic.
- Text de `landing` canviat: “membre fundador” → “club pioner/pionero/pioneer...”.
- Pendent principal: reescriure la guia pública `/guia` perquè reflecteixi el flux real i vengui millor el producte.

## Importació de dades (fet, sessió anterior) — commits ee12cea → af39e1b
- **ATENCIÓ: hi ha DOS còpies d'Atempo.** La correcta/desplegada és `C:\Users\mikel\OneDrive\Hockey\Atempo` (GitHub `MikelBegartz/atempo-sports` → Render). La vella `OKLIGA_ENGINE\atempo` és un duplicat antic: no editar-la excepte per mantenir-la sincronitzada si cal.
- `app/import_lists.py` suporta: `.xlsx`/`.xlsm` (openpyxl, totes les fulles, capçalera a qualsevol fila), CSV/text amb `;`/`,`/tabulador, codificacions UTF-8 → cp1252 → **MacRoman** (fitxers exportats des de Mac), files **sense capçalera** amb format `EQUIP|NOM|COGNOM|ROL`, rols `jugador/entrenador/delegat`.
- El fitxer real de l'usuari és `EQUIPS ATEMPO.txt` (MacRoman, TSV, sense capçalera, 279 files) — no confondre amb `Dades Jugadors.xlsx` (fitxer vell del SHUM).
- `import_people_rows` i l'alta manual de persones (`people_create`, `people.html`) ara creen `TeamMembership` si hi ha equip. Rol `delegate` acceptat a memberships.
- Sessió amb `autoflush=False`: els imports porten set `seen` per evitar duplicats `(team,person,role)` dins la mateixa importació.
- Neteja: banner a `/people` per esborrar persones sense equip (`people_delete_unassigned`).
- Equips es matchegen sense accents/majúscules (`find_team` per clau canònica).

## Conflictes (fet, últim commit 2197aed)
- Checkbox per conflicte + "selecciona-ho tot" (panell visible) + botó "Ignora els seleccionats" → `POST /season/{sid}/conflicts/ignore-bulk` marca `Conflict.ignored=True` per `conflict_key` (scope=sèrie, reversible des de la llista d'ignorats).
- Si TOTA la plantilla d'un equip és a l'altre → una sola línia "Tot l'equip X també juga a Y" (`team_shared_all` a `conflicts.py` `_MSGS`), en lloc d'un conflicte per persona. Solapaments parcials segueixen per-persona. Igual a `/overlaps` (`full_overlap_team` + `overlaps_shared_full`).
- `conflict_key` = `kind-person_id-severity-team_ids` (sense data → cada clau és una sèrie; `scope=day` usa `ConflictIgnored`, `scope=series` usa `Conflict.ignored`).
- Claus noves a `i18n_fed_sync.py` (SYNC_PACKS, 9 idiomes): `conflicts_select_all`, `conflicts_ignore_selected`, `conflicts_bulk_hint`, `conflicts_ignored_count`, `overlaps_shared_full`.
- Test: `python scripts/test_conflicts_bulk.py` (fixture propi sobre còpia de la BD: col·lapse, parcial, bulk, unignore, ?unique=1).

## Pendent / a vigilar
- Si la llista de conflictes segueix enorme, pot ser que els equips tinguin membres duplicats entre si per la importació — valorar neteja a l'origen en lloc d'ignorar.
- Verificar amb l'usuari que el redeploy de Render ha agafat els últims commits.
- `data_test*/` i `data/atempo.db.bak` són restes de tests (no commitejats); es poden esborrar.

## Autonomia de l'agent
- L'usuari vol que l'agent actuï amb autonomia en tot el tècnic (codi, estructura, ajustos) sense demanar permís pas a pas.
- Sempre avisar abans d'operacions destructives (esborrar fitxers/dades, `rm -rf`, reset, reescriure històric, etc.).
- L'usuari només plantejarà dubtes de concepte o donarà instruccions sobre què fer, no revisarà detalls de codi.

## Regla d'or: mai desplegar a cegues
- **Abans de cada `git push` cap a producció, executar:** `python scripts/smoke_pages.py`
- L'script arrenca l'app amb una **còpia** de `data/atempo.db` (mai toca la real) i comprova que totes les pàgines principals retornen 200/303, cap 500.
- Si falla → no es desplega fins arreglar-ho.

