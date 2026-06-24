# Database & Media Backups

Automated daily backups of the `crm_db` PostgreSQL database running in the
`crm-bluebee-db-1` Docker container, plus the uploaded media files
(attachments, org logos) on the host bind mount.

## What runs

- **Script:** [`ops/crm-bluebee-backup.sh`](./crm-bluebee-backup.sh)
- **Schedule:** root cron, `0 0 * * *` — every day at **00:00 UTC**
- **Log:** `/var/log/crm-bluebee-backup.log`
- **Output dir:** `/var/backups/crm-bluebee/`
- **Retention:** 14 days (older dumps are pruned automatically)

Each run produces three files, timestamped `YYYYmmdd_HHMMSS`:

| File | Contents | Restore tool |
|------|----------|--------------|
| `crm_db_<ts>.dump` | The application database, PostgreSQL **custom format** (compressed) | `pg_restore` |
| `globals_<ts>.sql.gz` | Global objects — roles incl. `crm_user`/RLS user (gzipped SQL) | `psql` |
| `media_<ts>.tar.gz` | Uploaded files from `backend/media/` (attachments, logos) — **not** in the DB dump | `tar` |

The script validates every dump (checks the `PGDMP` header, writes to a
`.partial` file and only promotes it on success) and exits non-zero on failure,
so a bad run is visible in the log and never leaves a corrupt file.

## Install on a fresh server

```bash
# 1. Copy the script into place and make it executable
install -m 755 ops/crm-bluebee-backup.sh /root/crm-bluebee-backup.sh

# 2. Add the cron entry (without clobbering existing jobs)
( crontab -l 2>/dev/null; \
  echo "0 0 * * * /root/crm-bluebee-backup.sh >> /var/log/crm-bluebee-backup.log 2>&1" ) \
  | crontab -

# 3. (Optional) run once to confirm it works
/root/crm-bluebee-backup.sh
```

Adjust `BACKUP_DIR`, `RETENTION_DAYS`, or `CONTAINER`/`DB` at the top of the
script if your deployment differs.

## Restore

> Restoring overwrites the current database. Make sure you intend to.

Pick a backup to restore from `/var/backups/crm-bluebee/` (newest last):

```bash
ls -1t /var/backups/crm-bluebee/crm_db_*.dump
```

### Restore into the existing database

```bash
DUMP=/var/backups/crm-bluebee/crm_db_YYYYmmdd_HHMMSS.dump

# Copy the dump into the db container
docker cp "$DUMP" crm-bluebee-db-1:/tmp/restore.dump

# Drop & recreate objects from the dump
docker exec crm-bluebee-db-1 \
  pg_restore -U postgres -d crm_db --clean --if-exists --no-owner /tmp/restore.dump

# Clean up
docker exec crm-bluebee-db-1 rm -f /tmp/restore.dump

# Restart the app so it picks up a clean connection state
docker compose -f /srv/crm-bluebee/docker-compose.yml restart backend celery-worker celery-beat
```

### Restore onto a brand-new server (empty cluster)

Restore the global roles first, then create and load the database:

```bash
GLOBALS=/var/backups/crm-bluebee/globals_YYYYmmdd_HHMMSS.sql.gz
DUMP=/var/backups/crm-bluebee/crm_db_YYYYmmdd_HHMMSS.dump

# 1. Roles (crm_user / RLS user, etc.)
gunzip -c "$GLOBALS" | docker exec -i crm-bluebee-db-1 psql -U postgres -f -

# 2. Create an empty database (skip if it already exists)
docker exec crm-bluebee-db-1 createdb -U postgres crm_db || true

# 3. Load the dump
docker cp "$DUMP" crm-bluebee-db-1:/tmp/restore.dump
docker exec crm-bluebee-db-1 \
  pg_restore -U postgres -d crm_db --no-owner /tmp/restore.dump
docker exec crm-bluebee-db-1 rm -f /tmp/restore.dump
```

### Restore uploaded media

Media lives at `MEDIA_ROOT=/media` **inside the backend container**. The tarball
expands to a `media/` directory; stream it back into the container:

```bash
MEDIA=/var/backups/crm-bluebee/media_YYYYmmdd_HHMMSS.tar.gz
gunzip -c "$MEDIA" | docker exec -i crm-bluebee-backend-1 tar -xzf - -C /
# files land at /media/ inside the container (served at /media/ by the app)
```

> Restore the database and media from the **same timestamp** so attachment rows
> and their files stay consistent.

> **Durability note:** unless a persistent volume is mounted at `/media` (see
> `docker-compose.yml`), the media directory is part of the container's
> ephemeral layer — it survives `docker compose restart` but is **lost on
> container recreation** (`down`/`up`, rebuild, `--force-recreate`). Mounting a
> named volume (e.g. `media_data:/media`) is strongly recommended.

### Inspect a backup without restoring

```bash
docker cp /var/backups/crm-bluebee/crm_db_YYYYmmdd_HHMMSS.dump crm-bluebee-db-1:/tmp/_v.dump
docker exec crm-bluebee-db-1 pg_restore -l /tmp/_v.dump | less   # lists the table of contents
docker exec crm-bluebee-db-1 rm -f /tmp/_v.dump
```

## Limitations / next steps

- **On-disk only.** Backups live on the same volume as the database, which
  protects against bad migrations or accidental deletes but **not** against
  disk or server loss. For off-site safety, add an upload step (S3, Hetzner
  Storage Box, or another host) after the dump in `crm-bluebee-backup.sh`.
- The cron runs in the server's timezone (**UTC**). Change the entry to
  `TZ=Europe/Warsaw 0 0 * * *` if you want local midnight.
