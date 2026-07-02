# CRUMBS — Production Deployment Environment Checklist

Use this checklist when preparing a **server-side** `.env` file for VPS deployment with `docker-compose.production.yml`.

For a full **step-by-step staging dry-run**, see [STAGING_DEPLOY_RUNBOOK.md](STAGING_DEPLOY_RUNBOOK.md).

For **VPS go-live** (first deploy, SSL, backups, rollback), see [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md), [docs/VPS_LAUNCH_RUNBOOK.md](docs/VPS_LAUNCH_RUNBOOK.md), and [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md).

For **manual QA before traffic**, see [docs/LAUNCH_TEST_PLAN.md](docs/LAUNCH_TEST_PLAN.md).

**Never commit `.env` to git. Never bake `.env` into the Docker image.**

---

## Production `.env` at a glance (VPS)

| Variable | Required | VPS value |
|----------|----------|-----------|
| `SECRET_KEY` | Yes | 50+ char random string |
| `DEBUG` | Yes | `False` |
| `LOCAL_PROD_DRY_RUN` | Yes | `False` |
| `DOMAIN` | Yes | Your apex domain |
| `ALLOWED_HOSTS` | Yes | `domain,www.domain` |
| `CSRF_TRUSTED_ORIGINS` | Yes | `https://...` after SSL |
| `SITE_URL` | Yes | `https://...` after SSL |
| `ENABLE_HTTPS` | Yes | `False` → `True` after SSL |
| `POSTGRES_PASSWORD` | Yes | Strong unique password |
| `ZARINPAL_MERCHANT_ID` | Yes (online pay) | Production UUID |
| `ZARINPAL_CALLBACK_URL` | Yes | `https://domain/payments/zarinpal/callback/` |
| `SMS_PROVIDER` | Yes | `kavenegar` or `console` |
| `SMS_ENABLED` | Yes | `True` / `False` |
| `SENTRY_DSN` | No | Empty = disabled |
| **Backups** | Ops | `./deploy/backup.sh all` before each deploy |

Full phase-1 vs phase-2 TLS table below. Complete launch flow: [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md).

---

## Startup safety rules

1. **Never commit `.env`** — copy from `.env.example` on the server only.
2. **Never bake `.env` into the image** — `.dockerignore` excludes `.env` and `.env.*` from the Docker build context.
3. **Use `env_file` in Docker Compose only** — secrets are injected at container runtime, not at `docker build`.
4. **Use server-level secrets in production** — restrict `.env` permissions (`chmod 600 .env`), limit SSH access, rotate keys after incidents.
5. **Build images on CI or the server** — do not build on a laptop with a populated `.env` unless `.dockerignore` is present (now enforced in this repo).

---

## Required environment variables

### Django core

| Variable | Example / requirement |
|----------|----------------------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` (set in compose for web/celery) |
| `DEBUG` | `False` |
| `SECRET_KEY` | 50+ char random string (required; deploy script validates) |
| `ALLOWED_HOSTS` | `crumbs.ir,www.crumbs.ir` (required on VPS — localhost-only raises at startup) |
| `LOCAL_PROD_DRY_RUN` | `False` on VPS; set `True` only for local Docker dry-run (see `.env.local-prod.example`) |
| `CSRF_TRUSTED_ORIGINS` | `https://crumbs.ir,https://www.crumbs.ir` (required when `ENABLE_HTTPS=True`) |
| `SITE_URL` | `https://crumbs.ir` |

### Database (PostgreSQL)

| Variable | Example / requirement |
|----------|----------------------|
| `POSTGRES_DB` | `crumbs` |
| `POSTGRES_USER` | `crumbs` |
| `POSTGRES_PASSWORD` | Strong password (required; deploy script validates) |
| `POSTGRES_HOST` | `db` (compose service name) |
| `POSTGRES_PORT` | `5432` |
| `DB_CONN_MAX_AGE` | `600` (recommended in production) |

> `DATABASE_URL` is not used by this project; configure `POSTGRES_*` variables instead.

### Redis & Celery

| Variable | Example / requirement |
|----------|----------------------|
| `REDIS_URL` | `redis://redis:6379/1` (cache/sessions; set in compose) |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` |

### Payments (Iran-first)

| Variable | Example / requirement |
|----------|----------------------|
| `DEFAULT_PAYMENT_METHOD` | `cod` |
| `DEFAULT_PAYMENT_PROVIDER` | `zarinpal` |
| `ZARINPAL_MERCHANT_ID` | Your Zarinpal merchant UUID |
| `ZARINPAL_SANDBOX` | `False` in production |
| `ZARINPAL_CALLBACK_URL` | `https://crumbs.ir/payments/zarinpal/callback/` |
| `STRIPE_ENABLED` | `False` (keep disabled for Iran production) |

### SMS (Kavenegar)

| Variable | Example / requirement |
|----------|----------------------|
| `SMS_PROVIDER` | `kavenegar` |
| `KAVENEGAR_API_KEY` | Your API key |
| `KAVENEGAR_SENDER` | Approved sender line |

### TLS & cookies (two-phase deploy)

Deploy in **two phases**. Do not enable secure cookies or SSL redirect until HTTPS is active.

#### Phase 1 — First deploy over HTTP

Use these values so admin login, CSRF, sessions, and health checks work before SSL:

```env
ENABLE_HTTPS=False
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_HSTS_SECONDS=0
```

Recommended for phase 1:

```env
SITE_URL=http://crumbs.ir
CSRF_TRUSTED_ORIGINS=http://crumbs.ir,http://www.crumbs.ir
```

Validate before deploy:

```bash
SECRET_KEY=... DEBUG=False ENABLE_HTTPS=False python manage.py check --settings=config.settings.prod
```

#### Phase 2 — After SSL (`./deploy/init-ssl.sh`)

Update `.env` and restart services:

```env
ENABLE_HTTPS=True
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SITE_URL=https://crumbs.ir
CSRF_TRUSTED_ORIGINS=https://crumbs.ir,https://www.crumbs.ir
```

Validate after SSL:

```bash
SECRET_KEY=... DEBUG=False ENABLE_HTTPS=True \
  SITE_URL=https://crumbs.ir \
  CSRF_TRUSTED_ORIGINS=https://crumbs.ir,https://www.crumbs.ir \
  python manage.py check --settings=config.settings.prod
```

| Variable | Phase 1 (HTTP) | Phase 2 (HTTPS) |
|----------|----------------|-----------------|
| `ENABLE_HTTPS` | `False` | `True` |
| `SECURE_SSL_REDIRECT` | `False` | `True` |
| `SESSION_COOKIE_SECURE` | `False` | `True` |
| `CSRF_COOKIE_SECURE` | `False` | `True` |
| `SECURE_HSTS_SECONDS` | `0` | `31536000` |

> `config.settings.prod` enforces these rules at startup. Invalid combinations (e.g. `ENABLE_HTTPS=False` with `SECURE_SSL_REDIRECT=True`, or `ENABLE_HTTPS=True` without HTTPS `SITE_URL` / `CSRF_TRUSTED_ORIGINS`) raise a clear error.

### Production security headers & cookies

Always enabled in `config.settings.prod` (independent of HTTPS phase):

| Setting | Value |
|---------|-------|
| `SESSION_COOKIE_HTTPONLY` | `True` |
| `CSRF_COOKIE_HTTPONLY` | `True` (CSRF token also available via form hidden field) |
| `SESSION_COOKIE_SAMESITE` | `Lax` |
| `CSRF_COOKIE_SAMESITE` | `Lax` |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` |
| `X_FRAME_OPTIONS` | `DENY` |
| `SECURE_REFERRER_POLICY` | `strict-origin-when-cross-origin` |

When `ENABLE_HTTPS=True`:

| Variable | Default / notes |
|----------|-----------------|
| `SECURE_SSL_REDIRECT` | `True` (only when `ENABLE_HTTPS=True`) |
| `SESSION_COOKIE_SECURE` | `True` |
| `CSRF_COOKIE_SECURE` | `True` |
| `SECURE_HSTS_SECONDS` | `31536000` (override as needed) |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` (set `False` if subdomains are not HTTPS-ready) |
| `SECURE_HSTS_PRELOAD` | `False` — enable only after deliberate HSTS preload review |

### ALLOWED_HOSTS validation

| Scenario | Behavior |
|----------|----------|
| VPS / real production | `ALLOWED_HOSTS` must include your public domain(s). Localhost-only values **fail fast** at startup. |
| Local Docker dry-run | Set `LOCAL_PROD_DRY_RUN=True` with `ALLOWED_HOSTS=localhost,127.0.0.1` — emits a warning only. |

### Admin safety

- `DEBUG=False` is enforced in prod settings; `DEBUG=True` raises at import time.
- Never expose admin with `DEBUG=True` in production — stack traces and settings would leak.
- Default admin URL is `/admin/`. After launch, consider restricting admin by IP or a custom nginx path (optional hardening).

### Static & media files

| Path | Served by | Notes |
|------|-----------|-------|
| `/static/` | Nginx alias → `/var/www/static/` | Collected via `collectstatic`; immutable cache headers |
| `/media/` | Nginx alias → `/var/www/media/` | **Static files only** — never proxy through script handlers |

User uploads (e.g. career PDF resumes):

- Django validates PDF extension and `%PDF-` magic bytes on upload.
- Nginx serves `/media/` with `default_type application/octet-stream` and `X-Content-Type-Options: nosniff` so uploaded files cannot execute as code.
- Do not enable PHP/CGI handlers under the media path.

---

## Pre-deploy verification

```bash
# 1. Copy and edit env on server
cp .env.example .env
chmod 600 .env

# 2. Phase 1 — validate HTTP-first settings
SECRET_KEY=... DEBUG=False ENABLE_HTTPS=False python manage.py check --settings=config.settings.prod

# 3. Build image (secrets excluded via .dockerignore)
docker compose -f docker-compose.production.yml build web

# 4. First deploy
./deploy/deploy.sh init

# 5. Enable SSL, update .env to Phase 2 values, restart
./deploy/init-ssl.sh
./deploy/deploy.sh restart

# 6. Phase 2 — validate HTTPS settings
SECRET_KEY=... DEBUG=False ENABLE_HTTPS=True \
  SITE_URL=https://crumbs.ir \
  CSRF_TRUSTED_ORIGINS=https://crumbs.ir,https://www.crumbs.ir \
  python manage.py check --settings=config.settings.prod

# 7. Health checks
./deploy/healthcheck.sh

# Optional: readiness probe (DB, Redis, Celery broker, migrations)
curl -sS "${SITE_URL%/}/ready/" | jq .
```

Expected responses:

| Endpoint | Purpose | Expected |
|----------|---------|----------|
| `/health/` | Docker/web **liveness** — process alive, no DB | HTTP 200, `"type": "liveness"` |
| `/ready/` | Load balancer **readiness** — DB, Redis, Celery, migrations | HTTP 200 when all checks pass |
| `/health/full/` | Admin/debug diagnostics (disabled in prod unless `HEALTH_FULL_ENABLED=1`) | HTTP 404 in production by default |

Use `/health/` for `docker-compose.production.yml` web healthcheck (already configured).
Use `/ready/` for nginx/load balancer upstream health or post-deploy validation.

See [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) for Sentry setup, Docker log commands, and incident checklist.

---

## Docker build context — included vs excluded

**Included (required in image):**

- `manage.py`
- `apps/`
- `config/`
- `templates/`
- `static/`
- `requirements/` and `requirements.txt`
- `docker/` (entrypoint, gunicorn config)
- `deploy/` (scripts referenced at runtime on host; harmless in image)
- `.env.example` (template only, no secrets)

**Excluded (via `.dockerignore`):**

- `.env`, `.env.*` (except `.env.example` via negation)
- `venv/`, `.venv/`
- `*.sqlite3`, `db.sqlite3`
- `media/`, `staticfiles/`, `logs/`
- `.git/`, `__pycache__/`, `.pytest_cache/`, test coverage artifacts
- `node_modules/`, editor folders

Runtime data (`staticfiles/`, `media/`, `logs/`) is provided via Docker volumes in production compose.

---

## Optional but recommended

| Variable | Purpose |
|----------|---------|
| `SENTRY_DSN` | Error monitoring (optional — disabled when empty) |
| `SENTRY_ENVIRONMENT` | Sentry environment tag (`production`, `staging`) |
| `SENTRY_RELEASE` | Sentry release tag (git SHA or version; falls back to `APP_VERSION`) |
| `SENTRY_TRACES_SAMPLE_RATE` | Performance trace sampling (`0.1` default) |
| `DOMAIN` | Nginx template rendering (`./deploy/render-nginx.sh`) |
| `CERTBOT_EMAIL` | Let's Encrypt registration |
| `GUNICORN_WORKERS` | Tune worker count |
| `RUN_MIGRATIONS_ON_STARTUP` | Default `false` — run `./deploy/deploy.sh migrate` at deploy time |
| `RUN_COLLECTSTATIC_ON_STARTUP` | Default `false` — run `./deploy/deploy.sh collectstatic` at deploy time |
| `LOG_LEVEL` | `INFO` in production |

### Backups (operational requirement)

| Item | Requirement |
|------|-------------|
| Pre-deploy | Run `./deploy/backup.sh all` |
| Paths | `backups/db/`, `backups/media/` (gitignored) |
| Off-server | Copy archives after each backup |
| Restore | `CONFIRM_RESTORE=yes` only — see [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md) |

---

## Quick “go live” checklist

- [ ] `.env` created on server from `.env.example`
- [ ] `LOCAL_PROD_DRY_RUN=False` on VPS (default in `.env.example`)
- [ ] `SECRET_KEY` and `POSTGRES_PASSWORD` set
- [ ] `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` match real domain
- [ ] `DEFAULT_PAYMENT_PROVIDER=zarinpal` and merchant ID configured
- [ ] `KAVENEGAR_API_KEY` configured (if SMS enabled)
- [ ] DNS points to VPS
- [ ] Phase 1 `.env` uses `ENABLE_HTTPS=False` and insecure cookies
- [ ] `./deploy/deploy.sh init` succeeds
- [ ] `./deploy/backup.sh all` succeeds (see [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md))
- [ ] `./deploy/init-ssl.sh` run; `.env` updated to Phase 2 HTTPS values
- [ ] `./deploy/deploy.sh restart` after Phase 2 env update
- [ ] `./deploy/healthcheck.sh` passes
- [ ] `./deploy/staging-smoke-test.sh "${SITE_URL}"` passes (see [STAGING_DEPLOY_RUNBOOK.md](STAGING_DEPLOY_RUNBOOK.md))
- [ ] [docs/LAUNCH_TEST_PLAN.md](docs/LAUNCH_TEST_PLAN.md) completed and signed off
