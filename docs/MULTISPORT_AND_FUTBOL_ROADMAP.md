# AtempoSports — Arquitectura multi-deporte y plan para el fútbol (v4.1 - FINAL)

> Estado: **CERRADO**. Prohibido tocar código de producción hasta orden explícita de inicio de la Fase 0.  
> Objetivo: permitir que `AtempoSports` soporte múltiples deportes, países y sub-espacios bajo un único programa y dominio, empezando por el fútbol 11 en España, sin perder datos ni romper la beta de hockey.

---

## 1. Resumen ejecutivo

- **Núcleo genérico + plugins**: `app/core/*` no conoce los deportes. Cada deporte es un plugin en `app/sports/*` que se descubre dinámicamente.
- **Polideportividad real**: un `Club` puede tener varias `Section` deportivas. Cada sección tiene sus propias temporadas, equipos, coordinadores y permisos.
- **Personas globales, afiliaciones por sección**: `Person` vive en el `Club`; `SectionMembership` vincula a la persona con una sección/temporada y guarda los datos deportivos.
- **Sub-espacios**: `Venue` soporta una jerarquía padre-hijo (campo completo, media pista, sub-campo), para gestionar solapamientos entre equipos que comparten una instalación.
- **Conflictos duros y blandos**: el motor distingue bloqueos físicos/personales de advertencias operativas que el club puede autorizar.
- **Deportes separados**: `football_11` y `futsal` son plugins distintos. El fútbol femenino es una **rama de género**, no un deporte aparte.
- **Estrategia "White Glove"**: el MVP de fútbol se valida con CSV. El equipo de Atempo carga el calendario del club piloto para generar el "efecto Wow" inmediato; el scraper federativo se desarrolla en paralelo.
- **Sincronización federativa**: una vez importado un calendario, `sync.py` vuelve a consultar la federación, detecta cambios oficiales y los presenta al coordinador para aceptar/rechazar. Las decisiones manuales del club prevalecen sobre la federación.

---

## 2. Visión final

`AtempoSports` = un único programa, un único dominio, que gestiona clubs de deportes con:

- clubs, secciones, temporadas, equipos, personas, pistas/campos, partidos, entrenamientos, solapamientos.
- diferentes deportes como conectores (`hockey`, `football_11`, `futsal`...).
- diferentes países como configuraciones de federaciones, idioma, calendario y formato.
- sub-espacios y gestión real de instalaciones compartidas.
- conflictos duros que bloquean y conflictos blandos que advierten.
- sincronización automática de cambios federativos con respeto a las decisiones del club.

La web final verá:

- una landing común.
- un selector de sección/deporte.
- la misma estructura de calendario, setup, entrenamientos y conflictos, adaptada a cada deporte.

---

## 3. Estructura de paquetes

```
app/
├── core/                          # dominio genérico, sin dependencias de deporte
│   ├── db.py                      # modelos del core
│   ├── plugin_loader.py           # descubre y carga app/sports/*
│   ├── calendar_week.py
│   ├── conflicts.py
│   ├── overlaps.py
│   ├── training_plan.py
│   ├── training_puzzle.py
│   ├── training_fit.py
│   ├── i18n.py                    # cadenas comunes + mecanismo de packs
│   ├── sync.py                    # motor de sincronización federativa
│   └── routers/                   # main.py desmontado aquí
│
├── countries/                     # perfiles por país
│   └── spain.py
│
├── sports/                        # un paquete por deporte, cargado dinámicamente
│   ├── hockey/                    # todo el hockey, migrado desde app/*.py
│   ├── football_11/               # fútbol 11
│   └── futsal/                    # fútbol sala
│
├── main.py                        # agregador: carga plugins, monta routers, inicia app
├── static/                        # común
└── templates/                     # común + overrides por deporte
```

---

## 4. Modelo de datos (core)

Añadir/modificar en `app/core/db.py` con columnas `Nullable` primero y backfill seguro.

### 4.1 Estructura

- `Sport`: `id`, `slug` (`hockey`, `football_11`, `futsal`), `name_i18n_key`, `is_active`.
- `Country`: `id`, `code` (`ES`, `FR`, ...), `default_lang`, `date_format`, `timezone`.
- `Federation`: `id`, `sport_id`, `country_id`, `slug`, `name`, `url`, `importer_class`, `is_active`, `extra_config`.
- `Section`: `id`, `club_id`, `sport_id`, `country_id`, `name`, `is_default`.
- `Season`: añadir `section_id`. El deporte y el país se heredan de la sección.
- `Team`: añadir `federation_id` y `competition_id`.

### 4.2 Espacios y sub-espacios (Venue)

`Venue` pertenece siempre al `Club`, nunca a la sección. Se añade una jerarquía autorreferencial:

- `parent_id` (FK a `Venue`, nullable): si es `None`, es una instalación completa.
- `capacity_percentage` (Int, default 100): fracción del padre que ocupa este sub-espacio.

Ejemplos:

- `Campo Central` (padre, `capacity_percentage = 100`).
- `Campo Central - Mitad Norte` (hijo, `parent_id = Campo Central`, `capacity_percentage = 50`).
- `Campo Central - Mitad Sur` (hijo, `parent_id = Campo Central`, `capacity_percentage = 50`).
- `Pista Hockey 1` (padre).
- `Pista Hockey 1 - Media Pista A` (hijo, `capacity_percentage = 50`).

**Regla de ocupación**:

1. Cualquier `Venue` (padre o hijo) es una unidad **indivisible** para un evento. Dos eventos no pueden ocupar el mismo hijo a la misma hora. Si lo intentan, es un **conflicto duro**.
2. Si un evento reserva un `Venue` **padre**, todos sus **hijos** quedan ocupados.
3. Si un evento reserva un `Venue` **hijo**, el **padre** queda ocupado, pero los **hermanos** del hijo siguen libres.
4. La `capacity_percentage` se utiliza para agrupar sub-espacios y calcular si el padre está saturado, no para permitir múltiples eventos simultáneos en el mismo hijo.

### 4.3 Personas y afiliaciones

- `Person`: datos personales invariables del humano. Pertenece al `Club`.
  - `full_name`, `dni`, `email`, `birth_date`, `phone`, etc.
- `SectionMembership`: vincula `Person` + `Section` + `Season`.
  - `role`: `player`, `head_coach`, `assistant_coach`, `delegate`, `physio`, `coordinator`.
  - `sports_data` (JSON/Text): datos dinámicos por rol. Ejemplo:
    - `player`: `dorsal`, `position`, `medical_notes`.
    - `head_coach`: `license_type`.
- `TeamMembership` sigue existiendo para vincular `Person` ↔ `Team` en una temporada, con `role`.
- `PersonUnavailability` permanece vinculada a `Person` y afecta a todas las secciones.

Los coordinadores editan `SectionMembership`, no `Person`, salvo en campos personales que se consideren editables.

---

## 5. Modelo de competiciones (Adjacency List)

`Competition` es un árbol puro, sin columnas rígidas:

```
Competition
- id
- parent_id
- federation_id
- sport_id
- name
- node_type           # federation | category | division | group | phase | cup
- external_id
- season_temp
- url
- is_active
```

El `SportPlugin` define qué `node_type` utiliza y cómo se pinta el árbol. Esto permite añadir fases, copas, subgrupos o cualquier nivel que invente una federación sin tocar el `core`.

---

## 6. Contrato de un SportPlugin

```python
class SportPlugin:
    slug: str
    name_i18n_key: str
    default_match_duration_min: int
    field_term_key: str
    branches: list[str]
    competition_levels: list[str]
    federation_importers: dict[str, FederationImporter]
    i18n_pack: dict[str, dict[str, str]]
    template_overrides: Path | None
    ui_config: dict

    def list_federations(country: str) -> list[Federation]: ...
    def search_teams(query, country, federation) -> list[TeamHit]: ...
    def import_competition(season_id, competition_id) -> ImportReport: ...
    def get_ui_config() -> dict: ...
```

---

## 7. Lógica de conflictos y solapamientos

El motor de `conflicts.py` / `overlaps.py` es agnóstico al deporte y evalúa dos ejes: **espacio** y **persona**.

### 7.1 Solapamientos de espacios

Reglas de la jerarquía `Venue`:

1. Un `Venue` (padre o hijo) puede albergar **como máximo un evento** en una franja horaria, salvo que el deporte defina explícitamente compartición (`allows_share`).
2. Si un evento reserva un `Venue` **padre** (instalación completa), todos sus **hijos** quedan ocupados.
3. Si un evento reserva un `Venue` **hijo** (sub-espacio), el **padre** queda ocupado, pero los **hermanos** del hijo siguen libres.
4. Si dos eventos intentan reservar el **mismo hijo** a la misma hora, es un **conflicto duro**.

Ejemplo: si un benjamín usa `Campo Central - Mitad Norte`, otro benjamín puede usar `Campo Central - Mitad Sur`, pero nadie puede reservar `Campo Central` completo a la misma hora. Dos equipos en `Mitad Norte` al mismo tiempo = imposible.

### 7.2 Conflictos duros (bloqueantes / rojo)

Hacen imposible ejecutar la actividad:

1. **Espacio ya ocupado**: dos eventos se solapan en el mismo `Venue` (padre o hijo) sin posibilidad de compartir.
2. **Entrenador principal duplicado**: un `Person` con rol `head_coach` está asignado a dos equipos con eventos concurrentes.

### 7.3 Conflictos blandos (advertencias / amarillo)

Operativamente complejos, pero posibles si la dirección deportiva los autoriza:

1. **Personal técnico secundario duplicado**: asistentes, fisios o delegados con dos eventos concurrentes.
2. **Jugador convocado en dos categorías**: un `player` tiene partidos o entrenamientos muy seguidos o solapados en dos equipos distintos (p. ej. un cadete sube a ayudar al juvenil).
3. **Entrenador en dos eventos con margen ajustado**: un coach tiene dos sesiones con poco tiempo de transición.

Los conflictos blandos se muestran, se pueden ignorar por el coordinador y no impiden aplicar cambios.

---

## 8. Asignación de personal

### 8.1 Entrenador principal (head_coach): automatizado

- Se vincula al `Team` en `TeamMembership` con `role = head_coach`.
- Al importar un partido (CSV o scraper), el sistema inyecta automáticamente al `head_coach` del equipo.
- Si el entrenador tiene otro evento a la misma hora, salta un **conflicto duro**.

### 8.2 Delegados, ayudantes, fisios: flexibilidad vía UI

- El CSV de rescate **no incluye** estos roles.
- Tras la importación, el coordinador los asigna manualmente en la web.
- Si el asignado ya tiene otro evento, el sistema muestra un **conflicto blando** en tiempo real, pero permite confirmar o buscar otro.

---

## 9. Importador CSV de fútbol 11

### 9.1 Formato

```csv
equipo,jornada,fecha,hora,local,visitante,escenario,notas
```

O, si se sube desde la ficha del equipo:

```csv
jornada,fecha,hora,local,visitante,escenario,notas
```

| Columna | Requerido | Descripción |
|---|---|---|
| `equipo` | Sí* | Nombre del equipo en Atempo. Si se sube desde la ficha del equipo, se puede omitir. |
| `jornada` | Sí** | Número de jornada. Identificador estable del partido. |
| `fecha` | Sí | `dd/mm/yyyy` o `yyyy-mm-dd`. |
| `hora` | No | `hh:mm`. Si falta, hora por defecto del deporte. |
| `local` | Sí | Nombre del equipo local. |
| `visitante` | Sí | Nombre del equipo visitante. |
| `escenario` | No | Pista/campo. |
| `notas` | No | Texto libre. |

\* `equipo` se puede omitir si el CSV se sube desde la pantalla del equipo.  
\** `jornada` es muy recomendable. Sin ella, la idempotencia es frágil para partidos aplazados.

### 9.2 Reglas del importador

- **Factor campo**: el sistema busca si el nombre/alias del club aparece en `local` o `visitante`.
  - Si aparece en `local` → partido en casa.
  - Si aparece en `visitante` → partido fuera.
- **Venue en partidos locales**: si `escenario` coincide con un `Venue` del club, se vincula `venue_id`. Si no, se guarda `place_name`.
- **Venue en partidos visitantes**: se fuerza `venue_id = None` y `place_name = escenario`. Esto evita falsos solapamientos en campos ajenos.
- **Inyección de entrenador**: se añade automáticamente el `head_coach` del equipo.
- **Delegados vacíos**: se dejan para asignación manual posterior.
- **Duración**: se toma de `default_match_duration_min` a menos que exista la columna opcional `duracion_min`.
- **Idempotencia**:
  - Clave primaria: `jornada + local + visitante` (o `competition_id + jornada + local + visitante` para mayor seguridad).
  - La `fecha` es un dato mutable; **nunca forma parte de la clave**.
  - Si `jornada` falta, se usa `fecha + local + visitante` como fallback, pero con advertencia: partidos aplazados con fecha nueva generarán duplicados.
- **Resultado**: mismo `ImportReport` que hoy (`creados`, `actualizados`, `omitidos`, `errores`).

### 9.3 Ejemplo

```csv
equipo,jornada,fecha,hora,local,visitante,escenario,notas
Infantil A,1,15/09/2026,18:00,Club Piloto,FC Barcelona B,Campo Municipal,Jornada 1
Infantil A,2,22/09/2026,10:30,RCD Espanyol,Club Piloto,,Jornada 2
Infantil A,5,29/09/2026,18:00,Club Piloto,Real Madrid C,Campo Municipal,
```

Si la jornada 5 se aplaza al `06/10/2026`, se vuelve a subir:

```csv
equipo,jornada,fecha,hora,local,visitante,escenario,notas
Infantil A,5,06/10/2026,18:00,Club Piloto,Real Madrid C,Campo Municipal,Aplazado
```

El importador identifica la fila por `jornada=5` + `local=Club Piloto` + `visitante=Real Madrid C` y actualiza la `fecha`, sin crear duplicado.

---

## 10. Sincronización federativa (sync.py)

Una vez importado el calendario de una federación, el sistema guarda la versión oficial en `Match` (`official_date`, `official_start_time`, `official_end_time`, `official_venue_id`) — campos que ya existen en el modelo actual.

### 10.1 Flujo de sincronización

1. `sync.py` vuelve a consultar la federación para el `Competition` vinculado.
2. Compara los datos oficiales nuevos con los guardados en `Match.official_*`.
3. Si detecta un cambio:
   - Actualiza `Match.official_*` con los nuevos valores.
   - Si no hay decisión manual del club, marca el partido con `pending_federation_change = True`.
   - Crea un registro en `FedMatchChange` con el histórico.
4. El coordinador decide:
   - **Aceptar cambio**: `Match` se actualiza con los valores oficiales. `pending_federation_change = False`.
   - **Rechazar / solucionar manualmente**: el coordinador edita el partido a su gusto. El sistema guarda `Match.federation_override = True` y `pending_federation_change = False`.

### 10.2 Prevención del bucle infinito

- Si `Match.federation_override = True`, `sync.py` **sigue actualizando los campos `Match.official_*`** en segundo plano, pero **no genera avisos ni marcas `pending_federation_change`**.
- El club puede consultar en cualquier momento la discrepancia `actual vs oficial`, pero la interfaz no bombardea con alertas.
- Si el coordinador revierte el `federation_override`, el sistema vuelve a avisar de nuevos cambios oficiales.

### 10.3 Reglas de conflicto tras cambio

Si el nuevo horario oficial genera un **conflicto duro**, el sistema muestra el aviso en rojo si `federation_override = False` y no aplica el cambio automáticamente.

Si genera un **conflicto blando**, se muestra en amarillo y el coordinador decide.

Si el partido ya tiene `federation_override = True`, los conflictos derivados del cambio oficial no se alertan de nuevo, salvo que el coordinador decida reactivar la sincronización.

---

## 11. Estrategia "White Glove" para el piloto

- El MVP de fútbol se valida con el **CSV de rescate**.
- El equipo de Atempo se ofrece a **cargar el calendario histórico del club piloto** directamente (llave en mano), para generar el "efecto Wow" sin fricción.
- El **scraper federativo** se desarrolla en paralelo, sin bloquear la puesta en marcha del piloto.
- El CSV sigue disponible como plan de rescate a largo plazo para federaciones que no tengan scraper.

---

## 12. Fases de implementación

### Fase 0 — Preparación

1. Congelar este documento.
2. Crear entorno de test con copia de `atempo.db`.
3. Definir checklist de regresión de hockey.
4. Identificar club/federación piloto de fútbol.
5. Validar el formato CSV con el club piloto.

### Fase 1 — Núcleo genérico y desmontaje de `main.py`

1. Extraer `app/core/` con los módulos genéricos.
2. Crear `app/core/plugin_loader.py`.
3. Mover hockey a `app/sports/hockey/` como primer plugin.
4. Desmontar `main.py` en `app/core/routers/`.
5. Mantener `app/*.py` como wrappers de compatibilidad.

### Fase 2 — Migración de base de datos

1. Añadir `Sport`, `Country`, `Federation`, `Section`, `PlayerSection`, `Competition` y columnas asociadas.
2. Backfill: una `Section` hockey/ES por club; `Venue` pasa al club; `Person` pasa al club; `SectionMembership` por persona/temporada.
3. Migrar `CompetitionSource` a `federation_id` + `competition_id`.

### Fase 3a — MVP fútbol 11 con CSV

1. Crear `app/sports/football_11/`.
2. Implementar `plugin.py`, `rules.py`, `ui_config.py`, `i18n_pack.py`.
3. Implementar importador CSV con inyección de entrenador y gestión de escenarios local/visitante.
4. Cargar datos del club piloto (White Glove).
5. Validar flujo completo: calendario, entrenamientos, conflictos.

### Fase 3b — Scraper federativo

1. Implementar `football_11/federations.py` y `football_11/catalog.py` para la federación piloto.
2. Desarrollar scraper en paralelo.
3. Cuando esté listo, migrar el club piloto a importación automática.

### Fase 4 — Interfaz dinámica

1. Rutas por sección/deporte (`/hockey/*`, `/futbol/*`).
2. Selector de sección en login y admin.
3. Overrides de plantillas por deporte.
4. Integración de `ui_config` e `i18n_pack` en Jinja2.

### Fase 5 — Beta cerrada de fútbol

1. Backup y migración a producción.
2. Beta con 1-3 clubs de fútbol.
3. Recoger feedback y estabilizar.

### Fase 6 (opcional) — Subdominios y sincronización por email

1. Evaluar `futbol.atemposports.com` / `hockey.atemposports.com`.
2. Añadir notificaciones por email de cambios federativos.

---

## 13. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Pérdida de datos | Backups, migraciones en test, add-only schema, backfill controlado. |
| Beta de hockey rota | Fases con `go/no-go`, wrappers de compatibilidad, tests de regresión. |
| Sub-espacios complejos | Regla simple: padre u hijo como unidad indivisible; un hijo = un evento. |
| Conflictos mal clasificados | Definir roles y reglas claras; iterar con coordinadores reales. |
| Fuentes federativas fragmentadas | Comenzar con CSV; scraper por federación piloto en paralelo. |
| CSV con duplicados por aplazamientos | Idempotencia por `jornada + local + visitante`, no por fecha. |
| Bucle infinito de sincronización | `Match.federation_override` desactiva avisos mientras respeta la decisión del club. |
| i18n descontrolado | Packs por deporte; regenerar `i18n_missing.csv` por `sport`. |
| `main.py` ingobernable | Desmontar en la Fase 1. |
| Scrapers frágiles | No bloquean el MVP; se añaden después. |

---

## 14. Decisiones cerradas

1. **Club multi-sección**: sí, `Section` dentro de `Club`.
2. **Deporte en `Season` o `Section`**: en `Section`; `Season` hereda `sport_id` y `country_id` de `Section`.
3. **`Venue`**: pertenece al `Club`; secciones lo usan, no lo poseen.
4. **`Person`**: global del `Club`; datos deportivos en `SectionMembership`.
5. **Sub-espacios**: jerarquía `parent_id` + `capacity_percentage`; cada `Venue` (padre o hijo) es una unidad indivisible.
6. **Conflictos duros**: solapamiento de espacios y coach principal duplicado.
7. **Conflictos blandos**: técnicos secundarios duplicados y jugador convocado en dos equipos.
8. **`football_11` vs `futsal`**: deportes separados.
9. **Fútbol femenino**: rama de género dentro del deporte.
10. **Competiciones**: árbol `Competition` con `parent_id` y `node_type`.
11. **MVP piloto**: CSV, con carga White Glove por parte del equipo de Atempo.
12. **Scraper**: desarrollo en paralelo, no bloqueante.
13. **Sincronización**: `sync.py` detecta cambios, crea `FedMatchChange` y avisa al coordinador.
14. **Respeto a decisiones del club**: `Match.federation_override = True` evita bucles de alertas.
15. **Idempotencia CSV**: `jornada + local + visitante`; la `fecha` nunca es clave.
16. **Rutas**: `/hockey/*`, `/futbol/*` para el MVP; subdominios opcionales después.

---

## 15. Nota final

Este documento es la **referencia inmutable** para el desarrollo.  
La **Fase 0** no comienza hasta orden explícita.  
No se tocará código de producción antes de dicho momento.
