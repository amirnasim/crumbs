# CRUMBS — Local Production Docker Dry-Run Results

**Date:** 2026-06-04  
**Environment:** macOS agent (Docker Desktop)  
**Reference:** [LOCAL_PROD_DRY_RUN.md](LOCAL_PROD_DRY_RUN.md)

---

## Summary

| Area | Result |
|------|--------|
| Prod settings validation (`manage.py check`) | **PASS** |
| Docker image pull / stack start | **BLOCKED** (Docker Hub 403 in this environment) |
| Container health / smoke test | **NOT RUN** (stack did not start) |
| Deployment doc + env template | **PASS** (added) |

The production compose file and local env template are ready. Full stack validation must be completed on a machine with working Docker Hub access.

---

## Commands run

```bash
# 1. Prepare local prod env
cp .env.local-prod.example .env
chmod 600 .env

# 2. Validate Django prod settings (no containers)
set -a && source .env.local-prod.example && set +a
python manage.py check --settings=config.settings.prod
# → System check identified no issues (0 silenced)

# 3. Attempt full stack (blocked)
docker compose -f docker-compose.production.yml down -v
docker compose -f docker-compose.production.yml up -d --build
# → Error: Docker Hub 403 Forbidden pulling postgres:16-alpine, redis:7-alpine, nginx:1.27-alpine

# 4. Not reached (stack unavailable)
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs web --tail=100
docker compose -f docker-compose.production.yml exec web python manage.py migrate
docker compose -f docker-compose.production.yml exec web python manage.py seed_iran_defaults
./deploy/staging-smoke-test.sh http://localhost:8080
```

---

## Pass / fail detail

| Check | Status | Notes |
|-------|--------|-------|
| `.env.local-prod.example` created | PASS | Phase 1 HTTP, port 8080, console SMS |
| `manage.py check --settings=config.settings.prod` | PASS | With local prod env sourced |
| `docker compose up -d --build` | FAIL | Registry 403 — environment/network, not app config |
| `docker compose ps` (all healthy) | SKIP | — |
| `/health/` liveness | SKIP | — |
| `/ready/` readiness (redis, celery, migrations) | SKIP | — |
| `./deploy/staging-smoke-test.sh` | SKIP | — |
| Static via nginx | SKIP | — |
| Celery worker / beat | SKIP | — |

---

## Blockers found

### 1. Docker Hub pull 403 (environment)

```
failed to resolve reference "docker.io/library/postgres:16-alpine": 403 Forbidden
```

**Impact:** Cannot build/start stack in this agent session.  
**Repo fix needed:** None — retry on developer machine or VPS with registry access.  
**Workaround:** Log in to Docker Hub (`docker login`) or use a mirror; ensure network allows `registry-1.docker.io`.

### 2. Port 80/443 conflict on local machines (documented)

**Impact:** `docker compose up` may fail if ports 80/443 are in use.  
**Fix applied:** `.env.local-prod.example` sets `NGINX_HTTP_PORT=8080` and `NGINX_HTTPS_PORT=8443`; `SITE_URL=http://localhost:8080`.

### 3. CSRF / callback URL must include nginx port (documented)

**Impact:** Admin login and Zarinpal callback fail if `CSRF_TRUSTED_ORIGINS` / `ZARINPAL_CALLBACK_URL` omit `:8080`.  
**Fix applied:** Updated `.env.local-prod.example` with port-aware URLs.

---

## Fixes made (deployment-only)

| File | Change |
|------|--------|
| `.env.local-prod.example` | New local prod env template (port 8080, Phase 1 HTTP, console SMS) |
| `LOCAL_PROD_DRY_RUN.md` | Step-by-step local dry-run guide |
| `.env.example` | Pointer to local dry-run docs |
| `LOCAL_PROD_DRY_RUN_RESULT.md` | This results log |

**No changes** to business logic, frontend, payments, orders, cart, or inventory.

**No compose/nginx code changes required** — existing `crumbs.conf` uses `server_name _` (catch-all), suitable for localhost dry-run without running `render-nginx.sh`.

---

## Remaining manual checks (on your machine)

After successful `docker compose up`:

```bash
cp .env.local-prod.example .env
docker compose -f docker-compose.production.yml up -d --build
sleep 90
docker compose -f docker-compose.production.yml ps

docker compose -f docker-compose.production.yml exec web python manage.py seed_iran_defaults
docker compose -f docker-compose.production.yml exec web python manage.py seed_growth_defaults
docker compose -f docker-compose.production.yml exec web python manage.py seed_intelligence_defaults
docker compose -f docker-compose.production.yml exec web python manage.py createsuperuser

./deploy/staging-smoke-test.sh http://localhost:8080

docker compose -f docker-compose.production.yml exec redis redis-cli ping
docker compose -f docker-compose.production.yml exec celery_worker celery -A config inspect ping
curl -sS http://localhost:8080/ready/ | jq '.checks'
```

Manual functional tests:

- [ ] Admin login at `http://localhost:8080/admin/`
- [ ] COD checkout end-to-end
- [ ] Zarinpal sandbox (set `ZARINPAL_MERCHANT_ID`, `DEFAULT_PAYMENT_METHOD=online`)
- [ ] Confirm no ERROR lines in `logs web` / `logs celery_worker`

Teardown:

```bash
docker compose -f docker-compose.production.yml down -v
```

---

## Go / no-go for VPS deploy

**Proceed to staging VPS deploy** after local dry-run passes on a machine where:

1. `docker compose -f docker-compose.production.yml up -d --build` succeeds  
2. `./deploy/staging-smoke-test.sh http://localhost:8080` passes  
3. `/ready/` shows `database`, `redis`, `celery_broker`, `migrations` all `ok`  
4. Celery `inspect ping` returns worker response  

Then follow [STAGING_DEPLOY_RUNBOOK.md](STAGING_DEPLOY_RUNBOOK.md).
