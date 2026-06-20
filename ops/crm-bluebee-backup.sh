#!/usr/bin/env bash
#
# Daily backup of the crm-bluebee PostgreSQL database.
# Invoked from root's crontab at 00:00 UTC. Writes a compressed custom-format
# dump (restore with pg_restore) plus a globals dump (roles incl. crm_user),
# validates the dump, and prunes backups older than RETENTION_DAYS.
#
set -euo pipefail

CONTAINER="crm-bluebee-db-1"
DB="crm_db"
DB_USER="postgres"
BACKUP_DIR="/var/backups/crm-bluebee"
RETENTION_DAYS=14

ts="$(date -u +%Y%m%d_%H%M%S)"
now() { date -u '+%F %T UTC'; }
dump_file="$BACKUP_DIR/crm_db_${ts}.dump"
globals_file="$BACKUP_DIR/globals_${ts}.sql.gz"

mkdir -p "$BACKUP_DIR"
echo "[$(now)] Starting backup of '$DB' -> $dump_file"

# The database must be up.
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "[$(now)] ERROR: container $CONTAINER is not running" >&2
  exit 1
fi

# Application database (custom format = compressed + selective restore).
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB" > "${dump_file}.partial"

# Validate: custom-format dumps start with the magic bytes "PGDMP".
if [ "$(head -c5 "${dump_file}.partial")" != "PGDMP" ]; then
  echo "[$(now)] ERROR: dump failed validation (bad header), discarding" >&2
  rm -f "${dump_file}.partial"
  exit 1
fi
mv "${dump_file}.partial" "$dump_file"

# Global objects (roles/RLS user) needed for a from-scratch restore.
docker exec "$CONTAINER" pg_dumpall -U "$DB_USER" --globals-only | gzip > "$globals_file"

size="$(du -h "$dump_file" | cut -f1)"
echo "[$(now)] OK: $dump_file ($size) + $(basename "$globals_file")"

# Rotation: keep the last RETENTION_DAYS days.
find "$BACKUP_DIR" -maxdepth 1 -name 'crm_db_*.dump'     -mtime "+${RETENTION_DAYS}" -delete
find "$BACKUP_DIR" -maxdepth 1 -name 'globals_*.sql.gz'  -mtime "+${RETENTION_DAYS}" -delete

count="$(find "$BACKUP_DIR" -maxdepth 1 -name 'crm_db_*.dump' | wc -l | tr -d ' ')"
echo "[$(now)] Done. ${count} dump(s) retained (max ${RETENTION_DAYS}d) in $BACKUP_DIR"
