# AtempoSports

Organízate sin líos. / Organitza't sense embolics.

Producto: cada club entra con **código + contraseña**. Nadie ve otros clubs ni datos globales.

**Beta tancada:** registre públic tancat; tu crees els clubs des de `/admin`. Detalls a [`PRODUCT.md`](PRODUCT.md) i [`docs/BETA_OPS.md`](docs/BETA_OPS.md).

## Arranque (local)

```bash
cd atempo
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.seed
uvicorn app.main:app --reload
```

Abre http://127.0.0.1:8000

## Acceso

- Club: **código + contraseña** (campos vacíos ya no entran).
- Demo local Mataró: por defecto `mataro` / `mataro` (solo desarrollo). En producción usa `ATEMPO_DEMO_PASSWORD` o desactívalo.
- Operador: `/admin` — contraseña en `ATEMPO_ADMIN_PASSWORD` o `data/.admin_password`.
- Guía coordinador: `/guia` · Privacidad: `/privacitat`

## Idioma

Por defecto **catalán**. Marcas: **CAT · ESP · POR · FRA · ITA · ENG · DEU**.

## Qué incluye

- Acceso aislado por club
- Personas, equipos, pistas, partidos, entrenos (series / puzle semanal)
- Conflictos + cambios + import RFEP/FECAPA
- Calendario semanal, copiar temporada, export CSV

Base de datos: `data/atempo.db`
