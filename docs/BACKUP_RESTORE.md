# CRUMBS — Backup & Restore

Operational guide for PostgreSQL and media backups on the production Docker stack.

**Never commit backup archives to git.** Local copies live under `backups/` (gitignored).

---

## Backup commands

From the repository root on the VPS (with `.env` configured and stack running):

```bash
./deploy/backup.sh db      # PostgreSQL → backups/db/crumbs_db_YYYYMMDD_HHMMSS.sql.gz
./deploy/backup.sh media   # /app/media volume → backups/media/crumbs_media_YYYYMMDD_HHMMSS.tar.gz
./deploy/backup.sh all     # both
```

### What each backup contains

| Type | Source | Format |
|------|--------|--------|
| Database | `db` container via `pg_dump` | gzip-compressed SQL |
| Media | `web` container `/app/media` | gzip-compressed tar |

Scripts fail fast if the required container (`db` or `web`) is not running.

### Manual equivalents

```bash
docker compose --env-file .env -f docker-compose.production.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backups/db/crumbs_db_$(date +%Y%m%d_%H%M%S).sql.gz

docker compose --env-file .env -f docker-compose.production.yml exec -T web \
  tar -czf - -C /app/media . > backups/media/crumbs_media_$(date +%Y%m%d_%H%M%S).tar.gz
```

### Schedule (recommended)

Run `./deploy/backup.sh all` before every deploy and on a cron schedule (e.g. nightly). Copy archives off-server (S3, another VPS, rsync) — Docker volumes alone are not disaster recovery.

---

## Restore commands (destructive)

Restores **overwrite live data**. They require an explicit confirmation:

```bash
CONFIRM_RESTORE=yes ./deploy/restore.sh db backups/db/crumbs_db_YYYYMMDD_HHMMSS.sql.gz
CONFIRM_RESTORE=yes ./deploy/restore.sh media backups/media/crumbs_media_YYYYMMDD_HHMMSS.tar.gz
```

Without `CONFIRM_RESTORE=yes`, the script refuses to run.

---

## A) Database restore procedure

Use only when you must recover from corruption, a bad migration, or a confirmed bad deploy — **not** for routine rollbacks after live orders/payments.

### Steps (automated script)

The restore script performs:

1. Refuses to run unless `CONFIRM_RESTORE=yes`
2. Takes a **safety backup** of the current database (`./deploy/backup.sh db`)
3. Stops `web`, `celery_worker`, `celery_beat`, and `nginx`
4. Terminates DB connections, drops and recreates the database
5. Restores from the `.sql.gz` archive via `psql`
6. Runs `python manage.py migrate --noinput`
7. Starts services and checks `GET /ready/`

### Manual procedure (if script unavailable)

```bash
# 1. Safety backup
./deploy/backup.sh db

# 2. Stop app tier
docker compose --env-file .env -f docker-compose.production.yml stop web celery_worker celery_beat nginx

# 3. Recreate database (DESTRUCTIVE)
docker compose --env-file .env -f docker-compose.production.yml exec -T db \
  psql -U "$POSTGRES_USER" -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid();"
docker compose --env-file .env -f docker-compose.production.yml exec -T db dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB"
docker compose --env-file .env -f docker-compose.production.yml exec -T db createdb -U "$POSTGRES_USER" "$POSTGRES_DB"

# 4. Restore
gunzip -c backups/db/crumbs_db_YYYYMMDD_HHMMSS.sql.gz | \
  docker compose --env-file .env -f docker-compose.production.yml exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1

# 5. Migrate and start
./deploy/deploy.sh migrate
docker compose --env-file .env -f docker-compose.production.yml up -d
curl -s "${SITE_URL}/ready/" | jq .
```

### After database restore

- Verify admin login and recent orders in Django admin
- Reconcile payment provider dashboards if restore point predates callbacks
- Check Sentry for new errors
- **Do not** restore an old DB over a live shop with new orders unless you accept data loss

---

## B) Media restore procedure

Use when product images, uploads, or career resumes were lost or corrupted.

### Steps (automated script)

1. `CONFIRM_RESTORE=yes` required
2. Safety backup via `./deploy/backup.sh media`
3. Stops app services
4. Clears `/app/media` and extracts the tarball
5. Restarts services

### Manual verification

```bash
docker compose --env-file .env -f docker-compose.production.yml exec web ls -la /app/media
curl -I "${SITE_URL}/media/"   # sample public file if applicable
```

Check product detail pages and any uploaded career files in admin.

---

## When to restore vs. roll forward

| Situation | Action |
|-----------|--------|
| Bad code deploy, DB intact | `./deploy/deploy.sh update` with previous git tag; **do not** restore DB |
| Failed migration / DB corruption | DB restore from pre-deploy backup + investigate |
| Lost uploads only | Media restore only |
| Live orders since backup | **Avoid** DB restore — roll forward with fixes |

---

## Related docs

- [VPS_LAUNCH_RUNBOOK.md](VPS_LAUNCH_RUNBOOK.md) — first deploy and go-live
- [OBSERVABILITY.md](OBSERVABILITY.md) — logs and Sentry after incidents
- [DEPLOYMENT_ENV_CHECKLIST.md](../DEPLOYMENT_ENV_CHECKLIST.md) — environment variables
