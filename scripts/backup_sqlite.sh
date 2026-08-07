#!/usr/bin/env bash
# Còpia de seguretat del fitxer SQLite d’AtempoSports.
# Ús: ./scripts/backup_sqlite.sh
# Cron diari (exemple): 15 3 * * * /ruta/atempo/scripts/backup_sqlite.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="${ATEMPO_DB_PATH:-$ROOT/data/atempo.db}"
DEST_DIR="${ATEMPO_BACKUP_DIR:-$ROOT/data/backups}"
KEEP="${ATEMPO_BACKUP_KEEP:-14}"

if [[ ! -f "$DB" ]]; then
  echo "No trobo la base de dades: $DB" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="$DEST_DIR/atempo_${stamp}.db"

cp -p "$DB" "$dest"
echo "Backup: $dest"

# Esborra còpies antigues (en deixa KEEP)
mapfile -t old < <(ls -1t "$DEST_DIR"/atempo_*.db 2>/dev/null || true)
if ((${#old[@]} > KEEP)); then
  for f in "${old[@]:KEEP}"; do
    rm -f -- "$f"
  done
fi
