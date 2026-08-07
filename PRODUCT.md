# AtempoSports — producto (referencia)

Documento vivo para chats nuevos. Forma parte de las **Instrucciones** del proyecto junto con `.cursor/rules/*.mdc`.

- **Rules** = normas cortas que el agente debe seguir
- **Este PRODUCT.md** = mapa de producto / roadmap / “por qué”

Cuando digas “actualiza las instrucciones”, el agente elige rule y/o este fichero según el contenido.

## Qué es
Gestión de horarios para clubs (hockey/patín): calendario, partidos federativos, conflictos, entrenamientos, setup RFEP/FECAPA.

## Estado actual (alto nivel)
- Calendario 4 semanas, conflictos hard/soft, Partits (modificar), Conflictes (auto + manual).
- Acceso multi-club: login, recuperación, admin operador; **registre públic tancat** (beta).
- Entrenamientos: **puzle setmanal** (3×1,5 h/equip). Prioritat: maximitzar sols → mínim de sessions compartides (el companys poden canviar cada dia; el patró es repeteix cada setmana) → aprofitar la disponibilitat de pistes. Proposta → borrador; calendari oficial només amb **Aplicar**.
- Auditoría V1 (juliol 2026): canvas `atempo-v1-audit` en el projecte Cursor.
- **Beta tancada (codi):** checklist tècnic fet a l’app; falta el teu desplegament real (domini, SMTP, servidor). Veure `docs/BETA_OPS.md`.

## Beta tancada (decisió actual — juliol 2026)

**Objectiu:** donar l’app a **3 clubs coneguts** perquè la provin aquesta temporada / aquest any **gratis**. Encara no és “oberta a tothom” ni de pagament.

En paraules senzilles:
1. Posem l’app a un **servidor amb adreça web** (HTTPS), no només al teu PC.
2. **Tu crees** el compte de cada club des de `/admin`. Ells no s’han de registrar sols des de la web pública.
3. Els dones **usuari (codi del club) + contrasenya** i un email on rebre enllaços si obliden la clau.
4. Aquest any: **sense cobrar**. Més endavant, quan hagin validat el producte, es parla de preu.
5. Reculls feedback (setup, entrenos, aplicar al calendari).

### Checklist tècnic
| # | Què | Estat |
|---|-----|--------|
| 1 | Treure “entrar buit → Mataró” | Fet (cal codi + contrasenya) |
| 2 | Demo Mataró assegurat | Fet: local `mataro`/`mataro`; producció bloqueja clau feble / `ATEMPO_DEMO_PASSWORD` |
| 3 | Registre públic tancat | Fet (`ATEMPO_PUBLIC_REGISTER=0`); crear clubs a `/admin` |
| 4 | SMTP per reset | Codi llest (465/587); **tu** configures `ATEMPO_SMTP_*` |
| 5 | HTTPS + backup SQLite | Cookie HTTPS + scripts + guia `docs/BETA_OPS.md`; **tu** desplegues |
| 6 | Text prova/privacitat | Fet: `/privacitat` |
| 7 | Guia 1 pàgina coordinador | Fet: `/guia` |

**No cal encara:** passarel·la de pagament, plans Free/Pro, Docker perfecte, rols entrenador vs coordinador.

### Com els hi donem accés (operativa)
1. Operador (tu) crea club a `/admin`: nom, email, contrasenya temporal → copia el **codi**.
2. Els envies URL + codi club + contrasenya + enllaç `/guia`.
3. Els acompanyes el primer setup (RFEP/FECAPA → pistes → equips) en una trucada curta si cal.
4. Gratis fins a **final de temporada 2025–26 / calendari 2026** (ajustar data concreta amb cada club).

## Decisiones cerradas
| Tema | Decisión |
|------|----------|
| UI idioma | Catalán por defecto (plantillas vía i18n, no hardcode ES) |
| Contraseñas | Hash; reset/admin set; no plaintext |
| Calendario | Solo realidad aplicada |
| Alternativas | Conflictes / fitxa, no calendario |
| Nombres | Federativos completos; Local/Visitant |
| Setup ready | RFEP + pistas + equipos |
| Entrenos hores | Primer: defecte per a tots; link per ajustar fins a nivell d’equip |
| Entrenos aplicar | Avisa que modifica el calendari; **Desfer aplicació** torna el darrer lot a borrador |
| Entrenos flux | Hores/grups/solapes/manual regeneren o afegeixen **borrador**; **Modificar** = palanques; **Aplicar** = calendari; **Descartar** = wipe de la prova |
| Entrenos sessió solta / excepció | 1 equip; va al borrador (`is_manual`); es veu a la gràfica abans d’aplicar; sobreviu al regen automàtic. Grups es modifiquen a Grups |
| Entrenos vs partits | Partits canvien; entrenos estables de temporada |
| Grups | Unitat / superequip (mateixa franja sencera). Plantilla temporada |
| Solapes | Parella ordenada A→B (equip o grup), mateixa pista; `overlap_minutes` ∈ {0,15,30,45,60}; cascada A→B→C si hi ha plantilles encadenades. No barrejar amb grups |
| Beta | Tancada, 3 clubs, gratis aquest any; sense pagament encara |
| Registre | Tancat al públic; alta només des d’admin fins que diguis el contrari |

## Entrenamientos — visión
1. Por equipo: horas/semana + pista(s) permitidas. **(hores: hecho defecto+override)**
2. Reparto preferente en **3 sesiones**. *(generador borrador: hecho)*
3. Categorías / refuerzos / inferiores cuando aplique.
4. Jugadores **y** entrenadores como recursos.
5. Franja horaria por equipo/categoría (defaults + override).
6. Defaults antes; preguntar solo en conflicto/excepción; **borrador** para el coordinador *(gràfica + modificar/aplicar/descartar: hecho)*.
7. Feedback del coordinador vía preferencias/acciones en producto.
8. Opcional: 30 min actividad física **sin** ocupar pista.
9. Tiempo de pista sin desperdiciar (solapes / relevos como herramienta de diseño, no solo de escasez). **(solapes v1: hecho)**
10. Partido oficial tiene prioridad sobre entreno.
11. **Grupos** = unidades (v1). **Solapes** = relevos (v1).

## Próximos épicos sugeridos (chats separados)
1. ~~Config horas/semana~~ (fase A hecha)
2. ~~Generador de borrador + gráfica~~ (fase B hecha)
3. ~~Grupos (unidades)~~ (v1)
4. ~~Solapes / relevos entre unidades~~ (v1)
5. ~~Beta tancada: preparar accés per a 3 clubs~~ (codi fet; ops teves a `docs/BETA_OPS.md`)
6. Preferencias / reacciones del coordinador
7. App Excel → web (otro proyecto; otro chat)
8. Planes de pago / monetización (después de la beta)
9. ~~Cerca global multi-federació per equip~~ — buscador global sense triar federació, agrupat per nom d’equip, pick_value amb font; inclou afegir font valenciana (URL/sigla pendent)
10. **Guia ràpida / ajuda dins l’app** (`/guia`) — manual d’ús per a coordinadors
11. **Revisió d’idiomes** — afegir euskara i galego i completar/auditar totes les traduccions

## Demo / ops
- Local: demo `mataro` / `mataro` (desenvolupament). Producció: `ATEMPO_ENV=production` + `ATEMPO_DEMO_PASSWORD` o demo sense accés.
- Admin: `ATEMPO_ADMIN_PASSWORD` o `data/.admin_password`
- SMTP: `ATEMPO_SMTP_HOST/PORT/USER/PASSWORD/FROM` — sense això → `data/mail_outbox.jsonl`
- Variables: veure `.env.example`
- Desplegament: `docs/BETA_OPS.md`
- App local: `uvicorn app.main:app --reload` → `127.0.0.1:8000`
- Auditoria: canvas Cursor `atempo-v1-audit`
