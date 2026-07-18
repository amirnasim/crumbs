# CRUMBS — VPS Launch Runbook

Step-by-step guide to deploy Crumbs on a production Ubuntu VPS with Docker Compose.

**Master checklist:** [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md)  
**Manual QA:** [LAUNCH_TEST_PLAN.md](LAUNCH_TEST_PLAN.md)  
**Environment variables:** [DEPLOYMENT_ENV_CHECKLIST.md](../DEPLOYMENT_ENV_CHECKLIST.md)  
**Backups:** [BACKUP_RESTORE.md](BACKUP_RESTORE.md)

---

## 1. Server requirements

| Requirement | Notes |
|-------------|-------|
| **OS** | Ubuntu 22.04 LTS or newer |
| **Docker** | 24+ with Compose v2 plugin |
| **Resources** | 2+ vCPU, 4+ GB RAM recommended for web + Celery + Postgres + Redis |
| **DNS** | `A` record for apex and `www` pointing to the VPS public IP |
| **Firewall** | Allow **80** and **443** (HTTP/HTTPS); restrict SSH (22) to your IP |
| **Domain** | Real domain required for TLS (`DOMAIN`, `ALLOWED_HOSTS`, `SITE_URL`) |

Optional bootstrap on a fresh server:

```bash
bash deploy/server-bootstrap.sh
```

---

## 2. Initial setup

```bash
git clone <your-repo-url> crumbs
cd crumbs
cp .env.example .env
chmod 600 .env
nano .env
```

### Required `.env` values (VPS)

| Variable | Example |
|----------|---------|
| `SECRET_KEY` | 50+ character random string |
| `DEBUG` | `False` |
| `LOCAL_PROD_DRY_RUN` | `False` |
| `DOMAIN` | `crumbs.ir` |
| `ALLOWED_HOSTS` | `crumbs.ir,www.crumbs.ir` |
| `CSRF_TRUSTED_ORIGINS` | `https://crumbs.ir,https://www.crumbs.ir` (after HTTPS) |
| `SITE_URL` | `https://crumbs.ir` |
| `POSTGRES_PASSWORD` | Strong unique password |
| `ZARINPAL_MERCHANT_ID` | Production merchant UUID |
| `ZARINPAL_SANDBOX` | `False` |
| `KAVENEGAR_API_KEY` | If SMS enabled |

Optional monitoring:

```bash
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=crumbs@1.0.0   # or git SHA
```

**Phase 1 (HTTP first deploy):** set `ENABLE_HTTPS=False` and use insecure cookie flags per [DEPLOYMENT_ENV_CHECKLIST.md](../DEPLOYMENT_ENV_CHECKLIST.md).

---

## 3. First deploy

```bash
chmod +x deploy/*.sh

# Validate compose file and env interpolation (does not start containers)
docker compose --env-file .env -f docker-compose.production.yml config > /dev/null && echo "compose OK"

./deploy/deploy.sh init
```

This builds images, starts Postgres/Redis, runs migrations and collectstatic, brings up the full stack, and runs `./deploy/healthcheck.sh`.

Create admin user:

```bash
docker compose --env-file .env -f docker-compose.production.yml exec web python manage.py createsuperuser
```

Optional seed data:

```bash
docker compose --env-file .env -f docker-compose.production.yml exec web python manage.py seed_iran_defaults
```

---

## 4. SSL setup

After HTTP works and DNS resolves:

```bash
./deploy/init-ssl.sh
```

Update `.env` to **Phase 2** HTTPS values (`ENABLE_HTTPS=True`, `CSRF_TRUSTED_ORIGINS` with `https://`).  
`init-ssl.sh` updates most values automatically — review `.env` before restart.

```bash
./deploy/deploy.sh update
```

Verify:

```bash
curl -I "https://${DOMAIN}/health/"
curl -sS "https://${DOMAIN}/ready/"
```

---

## 5. Health checks

```bash
curl -s "${SITE_URL}/health/" | jq .
curl -s "${SITE_URL}/ready/" | jq .
./deploy/healthcheck.sh
```

| Endpoint | Purpose |
|----------|---------|
| `/health/` | Liveness — process up, no DB |
| `/ready/` | Readiness — DB + Redis |

---

## 6. Backup before every deploy

```bash
./deploy/backup.sh all
```

Store copies off-server. See [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

---

## 7. Update deploy

```bash
./deploy/backup.sh all
git pull
./deploy/deploy.sh update
./deploy/healthcheck.sh
```

`deploy.sh update` force-recreates `web` (new internal IP), then reloads Nginx so upstream `web:8000` is re-resolved, and runs health checks. Skipping the Nginx reload can leave a stale upstream IP and produce temporary `502 Bad Gateway` responses.

Tail logs if needed:

```bash
docker compose -f docker-compose.production.yml logs -f web
docker compose -f docker-compose.production.yml logs -f celery_worker
docker compose -f docker-compose.production.yml logs -f celery_beat
```

---

## 8. Rollback basics

| Scenario | Action |
|----------|--------|
| Bad application code | `git checkout <previous-tag>` then `./deploy/deploy.sh update` |
| Bad Docker image | Rebuild from known-good git ref; keep previous image tag if you tag releases |
| DB migration failure / corruption | Restore DB from pre-deploy backup only — see [BACKUP_RESTORE.md](BACKUP_RESTORE.md) |
| Live shop with new orders | **Never** casually restore an old database |

Database restore is destructive and can lose orders/payments created after the backup timestamp.

---

## 9. Post-launch checklist

See [LAUNCH_TEST_PLAN.md](LAUNCH_TEST_PLAN.md) for the full manual test matrix.

- [ ] Superuser created
- [ ] `./deploy/backup.sh all` succeeds and archive copied off-server
- [ ] `curl -I ${SITE_URL}/health/` → 200
- [ ] `curl ${SITE_URL}/ready/` → 200, `ready: true`
- [ ] Homepage loads over HTTPS
- [ ] Add-to-cart works
- [ ] Checkout flow (test order or sandbox payment if available)
- [ ] Careers form submission (if enabled)
- [ ] `docker compose -f docker-compose.production.yml logs --tail=50 web` — no critical errors
- [ ] Sentry receiving events (if `SENTRY_DSN` set)
- [ ] `curl -I ${SITE_URL}/robots.txt` → 200
- [ ] `curl -I ${SITE_URL}/sitemap.xml` → 200
- [ ] `./deploy/staging-smoke-test.sh "${SITE_URL}"` passes

---

## Quick command reference

```bash
docker compose --env-file .env -f docker-compose.production.yml config   # validate compose
./deploy/deploy.sh init              # first deploy
./deploy/init-ssl.sh                 # Let's Encrypt
./deploy/deploy.sh update            # rebuild + migrate + restart (after SSL)
./deploy/backup.sh all               # DB + media backup
./deploy/healthcheck.sh              # smoke checks
curl -I "https://yourdomain.com/health/"
curl -sS "https://yourdomain.com/ready/"
docker compose -f docker-compose.production.yml logs -f web
CONFIRM_RESTORE=yes ./deploy/restore.sh db backups/db/<file>.sql.gz    # emergency only
```
