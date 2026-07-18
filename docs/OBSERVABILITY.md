# Observability — Monitoring, Logging & Sentry

Production observability for Crumbs: error monitoring, structured logs, health probes, and incident response.

---

## Sentry (optional)

Sentry is **disabled** when `SENTRY_DSN` is empty. No startup errors occur without a DSN.

| Variable | Purpose | Example |
|----------|---------|---------|
| `SENTRY_DSN` | Project DSN from Sentry | `https://…@o….ingest.sentry.io/…` |
| `SENTRY_ENVIRONMENT` | Environment tag | `production`, `staging` |
| `SENTRY_RELEASE` | Release/version tag | `crumbs@2026.06.01` or git SHA |
| `SENTRY_TRACES_SAMPLE_RATE` | Performance trace sampling | `0.1` (10%) |

`SENTRY_RELEASE` falls back to `APP_VERSION` when unset.

**What is captured**

- Django unhandled exceptions
- Celery task failures (via Celery integration)
- ERROR-level log events (via logging integration)

**What is NOT sent**

- Passwords, tokens, payment secrets
- Full request bodies or cookies
- Customer PII (emails, phones, addresses)
- Uploaded resume contents

Set in `.env` on the server before `docker compose up`.

---

## Structured logging

Production logs use **JSON** to stdout and rotating files under `logs/`:

| File | Contents |
|------|----------|
| `logs/django.log` | Application logs |
| `logs/celery.log` | Celery task logs |
| `logs/requests.log` | Django/gunicorn request warnings |

Each line includes: `level`, `time`, `logger`, `message`, and operational fields when present (`order_id`, `payment_id`, `provider`, `request_path`, task counts).

Log level: `LOG_LEVEL=INFO` (default in production).

---

## View Docker logs

```bash
docker compose -f docker-compose.production.yml logs -f web
docker compose -f docker-compose.production.yml logs -f celery_worker
docker compose -f docker-compose.production.yml logs -f celery_beat
```

Filter for payment issues:

```bash
docker compose -f docker-compose.production.yml logs -f web | grep crumbs.payments
docker compose -f docker-compose.production.yml logs -f celery_worker | grep "Stale payment cleanup"
```

---

## Health & readiness

| Endpoint | Purpose | DB required? |
|----------|---------|--------------|
| `GET /health/` | **Liveness** — process alive | No |
| `GET /ready/` | **Readiness** — DB, Redis, Celery broker, migrations | Yes |

### Verify locally (dry-run on port 8080)

```bash
curl -sS http://localhost:8080/health/ | jq .
curl -sS http://localhost:8080/ready/ | jq .
```

**Expected liveness (`/health/`):**

```json
{
  "status": "ok",
  "service": "crumbs",
  "type": "liveness"
}
```

**Expected readiness (`/ready/`) when healthy:**

```json
{
  "status": "ready",
  "type": "readiness",
  "service": "crumbs",
  "ready": true,
  "checks": {
    "database": "ok",
    "redis": "ok",
    "celery_broker": "ok",
    "migrations": "ok"
  }
}
```

Returns **HTTP 503** when any required check fails (`ready: false`).

Extended diagnostics: `GET /health/full/` (disabled in production unless `HEALTH_FULL_ENABLED=1`).

---

## Operational log events

Safe payment/order logs use **IDs only** (no customer PII):

| Event | Logger |
|-------|--------|
| `payment_callback_received` | `crumbs.payments` |
| `payment_callback_processed` | `crumbs.payments` |
| `payment_verified` | `crumbs.payments` |
| `payment_failed` | `crumbs.payments` |
| `Stale online payment cleanup finished` | `payments.stale_cleanup` |
| `stock_reservations_released` | `crumbs.orders` |
| `stock_reservations_confirmed` | `crumbs.orders` |
| `order_finalized` | `crumbs.orders` |

---

## Basic incident checklist

1. **Site down / 502**
   - `docker compose -f docker-compose.production.yml ps`
   - Compare gateway vs container: if `curl` through Nginx returns 502 but `web` `/health/` is 200, check Nginx logs for `connect() failed` to a stale upstream IP (after `web` recreate, Nginx must reload to re-resolve `web:8000`)
   - Quick recovery: `docker compose -f docker-compose.production.yml exec nginx nginx -s reload` (or re-run `./deploy/deploy.sh update`, which reloads Nginx automatically)
   - `curl /health/` via `SITE_URL` — if it still fails after reload, restart web: `./deploy/deploy.sh restart`
   - `curl /ready/` — identify failing check (`database`, `redis`, `celery_broker`, `migrations`)

2. **Payments stuck**
   - Check `crumbs.payments` logs for `payment_callback_*` events
   - Verify Zarinpal callback URL matches `SITE_URL`
   - Check stale cleanup: `celery_worker` logs for `Stale payment cleanup task finished`

3. **Background jobs not running**
   - Confirm `celery_worker` and `celery_beat` containers are up
   - Check `CELERY_BROKER_URL` / Redis connectivity via `/ready/`

4. **Errors in Sentry**
   - Filter by `SENTRY_ENVIRONMENT` and `SENTRY_RELEASE`
   - Cross-reference `order_id` / `payment_id` in JSON logs (never share customer data)

5. **After fix**
   - Re-run `./deploy/healthcheck.sh` and `./deploy/staging-smoke-test.sh "${SITE_URL}"`

---

See also: [DEPLOYMENT_ENV_CHECKLIST.md](../DEPLOYMENT_ENV_CHECKLIST.md), [LOCAL_PROD_DRY_RUN.md](../LOCAL_PROD_DRY_RUN.md).
