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

## Autonomia de l'agent
- L'usuari vol que l'agent actuï amb autonomia en tot el tècnic (codi, estructura, ajustos) sense demanar permís pas a pas.
- Sempre avisar abans d'operacions destructives (esborrar fitxers/dades, `rm -rf`, reset, reescriure històric, etc.).
- L'usuari només plantejarà dubtes de concepte o donarà instruccions sobre què fer, no revisarà detalls de codi.

