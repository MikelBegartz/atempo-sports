# Disseny — Pantalla de benvinguda i importació flexible

## 1. Pantalla de benvinguda

### URL proposat
`/welcome` o reutilitzar `/app` quan el club no té setup complet.

### Títol
"Benvingut a AtempoSports, [nom del club]"

### Subtítol
"Abans de començar, tria com vols configurar el club."

### Contingut principal: dues cards

#### Card A — Importar de la federació
- **Icona:** descàrrega / fletxa avall
- **Text:** "Si els equips ja estan inscrits a RFEP o FECAPA i els partits oficials estan publicats, podem importar-los."
- **Botó:** "Importar de federació"
- **Nota 1:** "Aquest pas només importa equips i partits. Persones, pistes i entrenaments les configuraràs després."
- **Nota 2 (fallback):** "Si encara no estan publicats, crea'ls manualment i vincula'ls més tard."

#### Card B — Començar manualment
- **Icona:** llapis / editar
- **Text:** "Crea els equips, entrenaments i partits manualment."
- **Botó:** "Crear manualment"
- **Nota:** "Podràs vincular els equips a RFEP/FECAPA més endavant des de l'apartat Equips."

### Barra de progrés secundària
Sota les cards, mostrar els passos comuns independentment de la tria:

1. Pistes (necessari per a tots dos)
2. Equips i partits (importació o manual)
3. Persones (entrenadors/jugadors)
4. Entrenaments

### Footer
"Si tens dubtes, consulta la /guia o contacta amb l'operador."

### Fluxos de redirecció
- Card A → `/season/{id}/fed` (elecció RFEP/FECAPA)
- Card B → `/season/{id}/venues` (començar per pistes)
- Després: pista → equips → persones → entrenaments

---

## 2. Importació flexible

### On apareix
Botó "Importar" a `/season/{id}/people` i `/season/{id}/teams`.

### Modal/pantalla amb pestanyes

#### Pestanya 1 — Enganxar noms
- Textarea amb placeholder: "Un nom per línia" o "Nom, Rol, Equip"
- Botó "Previsualitzar" mostra taula
- Filas amb error marcades en vermell

#### Pestanya 2 — Pujar CSV/Excel
- Input file o drag & drop
- Enllaç a plantilla descarregable
- Vista prèvia abans de confirmar

#### Pestanya 3 — Afegir un a un
- Formulari normal existent

#### Pestanya 4 — Importar federació (si aplica)
- Buscador de club/equip
- Selector d'equips a importar

### Persones
- Camp de text lliure
- Selector de rol: Jugador / Entrenador / Ambdós
- Previsualització de noms parsejats
- Botó "Crear X persones"

### Equips
- Camp de text lliure
- Selector de categoria/branch
- Previsualització
- Botó "Crear X equips"

---

## 3. Criteris de disseny

- No bloquejar l'usuari si la federació no té dades públiques.
- Ofereix sempre un camí manual com a fallback.
- Explicar el què i el què no es importa.
- Previsualitzar abans de crear per evitar duplicats i errors.
- Mantenir la coherència visual amb la resta de l'app (cards, botons, colors).
