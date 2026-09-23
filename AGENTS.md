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

## Gestor de persones (fase 1, aquesta sessió)
- Lògica nova a `app/people_ops.py`: `bulk_people`, `build_replace_plan`/`apply_replace`, `export_people_csv`, `parse_sel_pairs` (`"team_id:person_id"`, team 0 = sense equip), `delete_people` (esborra persona + membresies + indisponibilitats + conflictes).
- `/season/{sid}/people`: checkbox per persona (atribut `form="people-bulk"`, sense forms niats), "tot el grup" per equip, filtres línia (`data-branch`) + categoria (`data-cat`) + cerca per nom (`data-name`), barra d'accions massives: `move`/`add`/`remove`/`role`/`delete` → `POST /people/bulk`.
- **Substituir des de fitxer**: `POST /people/replace` (preview, NO escriu) → `people_replace.html` amb `rows_text` (format `equip;categoria;persona;rol`) en `<textarea>` oculta → `POST /people/replace/apply` recalcula i aplica.
  - Abast `team`: el que no és al fitxer surt de l'equip però segueix al club. La columna equip del fitxer s'ignora.
  - Abast `club`: membresies no llistades es treuen; persones que no són al fitxer s'esborren del club. Files sense equip = persona que queda sense equip (no s'esborra).
  - El preview bloqueja si 0 files vàlides (mai substituir per un fitxer buit).
- **Export**: `GET /people/export?scope=club|team&team_id=N` → CSV `equipo;categoria;nombre;rol` (rols en català: jugador/entrenador/reforç/delegat — reimportable via ROLE_MAP). També enllaç "CSV" per equip a la capçalera de cada grup.
- `_get_or_create_team` ara desempata per categoria quan hi ha equips amb el mateix nom.
- `people_groups` a `people_list` porta tuples `(Team|None, members)` (abans `(str, members)`) — el template usa `gteam.name`, `branch_map`, `categories`.
- Claus noves a SYNC_PACKS ×9 idiomes: `people_bulk_*`, `people_rep_*`, `people_replace_*`, `people_export*`, `people_filter_*`, `people_search_ph`, `people_group_all`, `people_tools_title`.
- **Avís "jugador a més d'un equip"**: a `/people`, panell amb persones que tenen rol `player` a 2+ equips (legítim com a coach/reinforce/delegate, sospitós com a jugador). Cada membresia porta select de rol + "treure" inline reutilitzant `teams/memberships/{id}/role|delete` amb `back=people` per tornar a /people.
- `team_update_member_role` ara accepta rol `delegate` (abans el select de teams.html l'oferia però el rebutjava — bug) i `back=people` a ambdós endpoints de membresia.
- Test: `python scripts/test_people_ops.py` (còpia BD: checkboxes, avís multi-equip, move/remove/delete, export, preview no escriu, apply team+club).
- ATENCIÓ: noms de test amb dígits ("TA1") fallen al parser headerless (les columnes amb dígits no són candidata a nom). Fixture usa noms sense dígits.

## Pendent / a vigilar
- Gestor fase 2 (no feta): editar fitxa individual (nom/rols), duplicats "semblants" (fuzzy, no només clau exacta).
- L'avís "jugador a més d'un equip" ja cobreix la neteja de membres duplicats entre equips; vigilar si la llista de conflictes s'alleugera.
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

