# Próxima sesión: completar traducciones

## Contexto
- `app/i18n.py` contiene los diccionarios base (`ca`, `es`, `pt`, `fr`, `it`, `en`, `de`).
- `app/i18n_extras.py` aplica `AUTH_PACKS` y luego rellena idiomas distintos de `ca`/`es` con el valor de `en` y, si falta, de `ca`.
- Esto hace que **pt/fr/it/de ahora se vean en inglés** cuando les falta traducción propia, no en catalán.

## Estado actual
| Idioma | Cadenas heredadas de `en` sin traducir |
|--------|----------------------------------------|
| `pt`   | ~538 |
| `fr`   | ~542 |
| `it`   | ~540 |
| `de`   | ~545 |
| `es`   | ~27  |

## Fichero de trabajo
`i18n_missing.csv` tiene todas las claves con las 7 traducciones. Se puede abrir en Excel/Sheets y completar idioma por idioma. El patrón a seguir:
1. Ordenar por idioma.
2. Para cada `key`, si el valor es igual al de `en`, es heredado: falta traducción nativa.
3. Sustituir por la traducción correcta en `app/i18n.py` (formato `"key": "valor",`).

## Recomendación de lotes
No intentar traducir todo de golpe. Sugerencia:
1. `de` (alemán) — las pantallas de usuario más visibles primero.
2. `pt` (portugués).
3. `fr` (francés).
4. `it` (italiano).
5. Revisar `es` (quedan ~27 claves pendientes).

## Verificación rápida
```powershell
python -c "import importlib.util; spec=importlib.util.spec_from_file_location('i18n','app/i18n.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); S=mod.STRINGS; print([k for k in S['de'] if S['de'][k]==S['en'].get(k,None)][:10])"
```

## Nota importante
Si solo se cambian textos en `app/i18n.py`, **no hace falta reiniciar uvicorn**: FastAPI recarga el archivo en cada petición (se importa cada vez). Si se toca `i18n_extras.py` o `i18n.py` estructura, sí reiniciar.
