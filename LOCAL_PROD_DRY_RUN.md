# CRUMBS — Local Production Docker Dry-Run

Validate the **full production Docker stack** on your machine before VPS deploy.

Related: [STAGING_DEPLOY_RUNBOOK.md](STAGING_DEPLOY_RUNBOOK.md) · [DEPLOYMENT_ENV_CHECKLIST.md](DEPLOYMENT_ENV_CHECKLIST.md)

---

## Prerequisites

- Docker 24+ and Docker Compose v2
- Ports **8080** (HTTP) and **8443** (HTTPS placeholder) available locally  
  (avoids macOS/Linux conflicts with system services on 80/443)
- ~4 GB free disk for images + volumes

---

## Step 1 — Prepare environment file

Copy the local production template:

```bash
cd /path/to/crumbs
cp .env.local-prod.example .env
chmod 600 .env
```

Or copy from `.env.example` and set these values manually:

| Variable | Local dry-run value |
|----------|---------------------|
| `DEBUG` | `False` |
| `LOCAL_PROD_DRY_RUN` | `True` |
| `ENABLE_HTTPS` | `False` |
| `SECURE_SSL_REDIRECT` | `False` |
| `SESSION_COOKIE_SECURE` | `False` |
| `CSRF_COOKIE_SECURE` | `False` |
| `SECURE_HSTS_SECONDS` | `0` |
| `DOMAIN` | `localhost` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost,http://127.0.0.1` |
| `SITE_URL` | `http://localhost:8080` |
| `POSTGRES_PASSWORD` | any strong local password |
| `SECRET_KEY` | 50+ char random string |
| `REDIS_URL` | `redis://redis:6379/1` |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` |
| `NGINX_HTTP_PORT` | `8080` |
| `NGINX_HTTPS_PORT` | `8443` |
| `DEFAULT_PAYMENT_METHOD` | `cod` |
| `DEFAULT_PAYMENT_PROVIDER` | `zarinpal` |
| `ZARINPAL_SANDBOX` | `True` |
| `SMS_PROVIDER` | `console` |
| `USE_WHITENOISE` | `False` |

Validate prod settings load:

```bash
set -a && source .env && set +a
python manage.py check --deploy --settings=config.settings.prod
```

> `.env.local-prod.example` sets `LOCAL_PROD_DRY_RUN=True` so localhost `ALLOWED_HOSTS` is allowed with a warning only.

---

## Step 2 — Nginx config (optional for localhost)

The repo ships `docker/nginx/conf.d/crumbs.conf` with `server_name _` (catch-all) for local testing.

On VPS, run `./deploy/render-nginx.sh` after setting `DOMAIN`. For localhost dry-run, **skip** render unless you need domain-specific config.

---

## Step 3 — Build and start stack

Recommended (runs migrate + collectstatic before app start):

```bash
./deploy/deploy.sh init
```

Or manually:

```bash
docker compose -f docker-compose.production.yml up -d --build db redis
docker compose -f docker-compose.production.yml run --rm --no-deps --entrypoint "" web python manage.py migrate --noinput
docker compose -f docker-compose.production.yml run --rm --no-deps --entrypoint "" web python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml up -d
```

Wait ~30–60s for web healthcheck. The entrypoint skips migrate/collectstatic by default (`RUN_MIGRATIONS_ON_STARTUP=false`, `RUN_COLLECTSTATIC_ON_STARTUP=false`).

Verify containers:

```bash
docker compose -f docker-compose.production.yml ps
```

Expected: `db`, `redis`, `web`, `celery_worker`, `celery_beat`, `nginx` — running/healthy.

---

## Step 4 — Logs (troubleshooting)

```bash
docker compose -f docker-compose.production.yml logs web --tail=100
docker compose -f docker-compose.production.yml logs celery_worker --tail=100
docker compose -f docker-compose.production.yml logs nginx --tail=100
```

---

## Step 5 — Migrations and seeds

Run migrations and collectstatic explicitly during deploy (not on every web container boot):

```bash
COMPOSE="docker compose -f docker-compose.production.yml"

$COMPOSE run --rm --no-deps --entrypoint "" web python manage.py migrate --noinput
$COMPOSE run --rm --no-deps --entrypoint "" web python manage.py collectstatic --noinput
$COMPOSE exec web python manage.py seed_iran_defaults
$COMPOSE exec web python manage.py seed_growth_defaults
$COMPOSE exec web python manage.py seed_intelligence_defaults
$COMPOSE exec web python manage.py createsuperuser
```

---

## Step 6 — Endpoint validation

Use port **8080** (from `NGINX_HTTP_PORT`):

```bash
./deploy/staging-smoke-test.sh http://localhost:8080
```

Manual checks:

```bash
curl -sS http://localhost:8080/health/ | jq .
curl -sS http://localhost:8080/ready/ | jq .
curl -sI http://localhost:8080/static/css/crumbs.css
```

| Endpoint | Expected |
|----------|----------|
| `/health/` | HTTP 200, `"type": "liveness"` |
| `/ready/` | HTTP 200, `"status": "ready"`, redis + celery_broker `"ok"` |
| `/admin/` | HTTP 302 → login |
| `/shop/` | HTTP 200 |
| `/cart/` | HTTP 200 |
| `/checkout/` | HTTP 200 or 302 (empty cart) |
| `/static/css/crumbs.css` | HTTP 200 (served by nginx) |

---

## Step 7 — Worker validation

```bash
COMPOSE="docker compose -f docker-compose.production.yml"

# Redis
$COMPOSE exec redis redis-cli ping
# Expected: PONG

# Celery worker
$COMPOSE exec celery_worker celery -A config inspect ping
# Expected: pong from worker

# Readiness JSON
curl -sS http://localhost:8080/ready/ | jq '.checks'
```

---

## Step 8 — Manual functional checks (not automated)

- [ ] Admin login at `http://localhost:8080/admin/`
- [ ] Add product to cart → COD checkout completes
- [ ] (Optional) Online Zarinpal sandbox order with test merchant ID

---

## Teardown

```bash
docker compose -f docker-compose.production.yml down
# Remove volumes for clean re-run:
docker compose -f docker-compose.production.yml down -v
```

---

## Common blockers

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `POSTGRES_PASSWORD is required` | Missing in `.env` | Set in `.env.local-prod.example` copy |
| Port 80 in use | Local service on port 80 | Set `NGINX_HTTP_PORT=8080` |
| `/ready/` 503 migrations pending | First boot slow | Wait or run `migrate` manually |
| Static 404 | collectstatic not run | Check web logs; re-run collectstatic in container |
| Admin CSRF error | `CSRF_TRUSTED_ORIGINS` mismatch | Match `SITE_URL` host/port exactly |
| `ENABLE_HTTPS` startup error | HTTPS vars without SSL | Phase 1: `ENABLE_HTTPS=False`, insecure cookies |
| Smoke test fails on `127.0.0.1` | nginx `server_name` after render | Use `http://localhost:8080` or keep catch-all `crumbs.conf` |

---

## Result log

After running, record outcomes in [LOCAL_PROD_DRY_RUN_RESULT.md](LOCAL_PROD_DRY_RUN_RESULT.md).
