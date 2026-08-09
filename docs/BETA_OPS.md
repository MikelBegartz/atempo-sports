# Beta tancada — què has de fer tu (en paraules senzilles)

Aquest document és per posar AtempoSports online per a **3 clubs** amics, gratis aquesta temporada. No cal pagament.

## 1) Domini (l’adreça web)

1. Tens un nom (ex. `atempo.el-teu-domini.cat`).
2. Al panell del domini (DNS), crea un registre **A** (o AAAA) que apunti a la IP del servidor.
3. Espera uns minuts fins que el nom obri el servidor.

## 2) Servidor

Necessites un ordinador a Internet (VPS barat va bé) amb Linux.

1. Puja el codi d’`atempo` al servidor.
2. Crea un entorn Python, instal·la `requirements.txt`.
3. Copia `.env.example` → `.env` i omple (veure secció 4).
4. Arrenca l’app amb uvicorn (o systemd), escoltant només a localhost, p. ex. port 8000.
5. Poses **Caddy** o **nginx** al davant perquè el món arribi amb **HTTPS** (candau al navegador). Amb Caddy, el certificat sol ser automàtic.

Exemple mínim d’arrencada (després de configurar `.env`):

```bash
cd /ruta/atempo
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 3) HTTPS (el candau)

- El navegador ha de mostrar `https://…`.
- Al `.env`: `ATEMPO_ENV=production` i `ATEMPO_HTTPS=1`.
- Això fa que la sessió (cookie) només vagi per connexió segura.

## 4) Variables importants (`.env`)

| Variable | Per a què |
|----------|-----------|
| `ATEMPO_ENV=production` | Mode beta/online: sense login buit, demo feble bloquejada |
| `ATEMPO_HTTPS=1` | Cookie segura |
| `ATEMPO_ADMIN_PASSWORD=…` | Clau per entrar a `/admin` (tu) |
| `ATEMPO_DEMO_PASSWORD=…` | Només si vols mantenir Mataró amb clau **forta**; si no, el demo queda sense accés online |
| `ATEMPO_PUBLIC_REGISTER=0` | Registre tancat (els clubs els crees tu) |
| `ATEMPO_SMTP_*` | Correu real per “he oblidat la contrasenya” |

### Correu (SMTP)

1. Crea un compte de correu (o “contrasenya d’aplicació” a Gmail/Outlook).
2. Omple host, port (`587` o `465`), usuari, contrasenya i remitent (`ATEMPO_SMTP_FROM`).
3. Prova “Has oblidat la contrasenya?” amb el teu club de prova: ha d’arribar un correu de veritat.
4. Sense SMTP, l’enllaç només queda al fitxer `data/mail_outbox.jsonl` del servidor (no serveix per als clubs).

## 5) Còpia de seguretat (SQLite)

Les dades són un fitxer: `data/atempo.db`. Si es perd, perds horaris.

- Linux: `scripts/backup_sqlite.sh` (cron diari recomanat).
- Windows: `scripts/backup_sqlite.ps1`.

Guarda les còpies també fora del servidor (núvol o disc).

## 6) Com dones accés als 3 clubs

1. Entra a `https://el-teu-domini/admin` amb la clau d’operador.
2. **Crear club**: nom, correu, contrasenya temporal.
3. Copia el **codi de club** que et mostra.
4. Els envies: URL + codi + contrasenya + enllaç a `/guia`.
5. Els acompanyes el primer setup si cal (federació → pistes → equips → entrenos).

## 7) Checklist abans d’invitar

- [ ] HTTPS funciona
- [ ] Login buit ja no entra a Mataró
- [ ] Registre públic tancat
- [ ] `/admin` crea clubs
- [ ] SMTP envia el reset de contrasenya
- [ ] Backup diari del `.db`
- [ ] Has llegit `/privacitat` i `/guia`

## Què no cal encara

Pagaments, plans Free/Pro, Docker perfecte, rols entrenador vs coordinador.

## Persistència: no perdis els clubs

**Això és el més important.** L'app guarda totes les dades (clubs, temporades, equips, partits...) en un únic fitxer: `atempo.db`.

El problema: al servei web normal de Render, el disc és temporal. Cada cop que es desplega una nova versió o el servei es reengega, el `atempo.db` es crea de nou i els clubs desapareixen. **L'app no esborra res; el servidor perd el fitxer.**

### Solució a Render

1. Crea un **Disk** persistent al panell de Render i munta'l a la carpeta `data` del projecte.
   - Ruta típica on muntar-ho: `/opt/render/project/src/atempo-sports/data`
   - Mida: 1 GB és més que suficient per començar.
2. A les variables d'entorn del servei, afegeix:
   - `ATEMPO_DATA_DIR=/opt/render/project/src/atempo-sports/data`
3. Amb aquesta configuració, `atempo.db` es guarda fora del contenidor i sobreviu als desplegaments.

### Còpia de seguretat diària

A més del Disc, fes còpies de `atempo.db` fora de Render (núvol o disc local), per si de cas. Això ja està a la checklist d'abaix.

## Actualització ràpida a Render (en paraules senzilles)

Ara que l'app està a Render, els canvis d'aquest ordinador arriben a Internet així:

1. Fas els canvis aquí.
2. `git add .`
3. `git commit -m "què canvies i per què"`
4. `git push origin main`
5. Render veu el nou `commit` de la branca `main`.

### Desplegament automàtic

Al panell de Render, dins del teu servei, hi ha un interruptor anomenat **Auto-Deploy**.
- Si està **ON**: cada `git push` a `main` s'actualitza sol en uns segons.
- Si està **OFF**: has d'entrar i prémer **Manual Deploy** → **Deploy latest commit**.

Per posar-lo automàtic: `dashboard.render.com` → el teu servei → pestanya `Settings`/`Deploy` → activa **Auto-Deploy** → guarda.

### Si vols fer-ho manual

Al mateix panell, botó **Manual Deploy** i tria l'últim `commit`. Això tira de GitHub i reengega l'app, però només quan tu ho premis.
