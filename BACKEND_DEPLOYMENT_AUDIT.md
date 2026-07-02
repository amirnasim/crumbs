# CRUMBS Backend + Deployment Audit

**Date:** 2026-06-02  
**Scope:** Backend stabilization, testing, production readiness, deployment  
**Method:** Read-only code review — no changes made  
**Auditor role:** Senior Django Backend & DevOps Engineer

---

## Executive Summary

CRUMBS is a well-structured Django 5.2 ecommerce backend with clear settings separation, a full Docker Compose production stack, Celery/Redis background jobs, and thoughtful inventory locking. The architecture layers checkout orchestration (`delivery`), domain services (`orders`, `payments`, `inventory`), and async side effects (`notifications`, `growth`, `loyalty`, `intelligence`) with idempotency patterns.

**Main launch risks** cluster around payment integrity (Stripe amount mismatch, duplicate sessions), cart-level concurrency (same-cart double checkout), and deployment hygiene (missing `.dockerignore`, secure cookies before SSL, PostgreSQL concurrency tests not run in default CI).

**Test suite:** 48 tests collected — **46 passed, 2 skipped** (concurrency tests require PostgreSQL).

---

## Production Readiness Scores

| Area | Score | Notes |
|------|-------|-------|
| **Backend** | **72 / 100** | Strong inventory/order locking; payment and cart gaps remain |
| **Deployment** | **68 / 100** | Full prod stack exists; secrets/build/SSL ordering gaps |
| **Testing** | **58 / 100** | Good unit/integration coverage for core flows; major gaps in cart, delivery, loyalty, concurrency CI |
| **Launch risk level** | **MEDIUM–HIGH** | Safe for controlled beta with COD; online payments + high traffic need fixes first |

---

## 1. Django Settings

**Location:** `config/settings/` (`base.py`, `dev.py`, `prod.py`, `test.py`)

### What works

| Concern | Status |
|---------|--------|
| Base/dev/prod/test split | ✅ Clear `from .base import *` overrides |
| Entry points | ✅ `manage.py` → dev; WSGI/Docker → prod; pytest → test |
| `SECRET_KEY` from env | ✅ Fail-fast in `base.py` if missing |
| `DEBUG` in prod | ✅ Hard `False`; raises if env `DEBUG=True` |
| PostgreSQL | ✅ Default engine in base; pooling in prod (`CONN_MAX_AGE=600`) |
| Secure cookies / HSTS | ✅ Configured in `prod.py` with env overrides |
| `SECURE_SSL_REDIRECT` | ✅ Tied to `ENABLE_HTTPS` / env |
| Proxy headers | ✅ `SECURE_PROXY_SSL_HEADER`, `USE_X_FORWARDED_*` |
| Logging | ✅ JSON rotating files in prod; Sentry optional |
| Celery/Redis | ✅ Queues, beat schedule, late ack, prefetch 1 |
| Rate limiting | ✅ Checkout/login paths in `RATE_LIMIT_PATHS` |

### Gaps & risks

| Issue | Severity | Detail |
|-------|----------|--------|
| `CSRF_TRUSTED_ORIGINS` empty by default | **High** | No prod startup validation; HTTPS POSTs fail CSRF if unset |
| `ALLOWED_HOSTS` soft validation | **Medium** | Prod only warns on localhost defaults |
| Secure cookies vs SSL redirect mismatch | **High** | `.env.example`: `SESSION_COOKIE_SECURE=True` but `ENABLE_HTTPS=False` — login/CSRF broken on HTTP-first deploy |
| `POSTGRES_PASSWORD` can be empty | **Medium** | No startup validation in base |
| Test settings + `SECRET_KEY` | **Medium** | Base import requires `SECRET_KEY` before test override; CI must set env |
| Prod without Redis | **High** | Falls back to LocMem cache with warning — broken for multi-worker |
| Dev always `DEBUG=True` | **Low** | Cannot mirror prod debug behavior locally without switching settings module |

---

## 2. Database

### PostgreSQL readiness

- **Engine:** `django.db.backends.postgresql` in base/prod/dev
- **Env vars:** `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- **Connection:** `CONN_MAX_AGE`, `connect_timeout` configurable
- **Tests:** SQLite in-memory by default; PostgreSQL optional via `CRUMBS_TEST_POSTGRES=1`

### Migrations health

- **29 migration files** across apps — linear chains, no broken dependencies observed
- Recent additive migrations: growth revenue engine, inventory cart FK on reservations
- **Delivery app label:** `fulfillment` (referenced correctly from `Order.delivery_zone`)

### Indexes (good coverage)

- Orders: `(status, created_at)`, `(payment_status, created_at)`, `(fulfillment_date, status)`
- Payments: `(order, status)`, `(provider, status, created_at)`; unique Stripe event IDs
- Inventory: unique `(product, production_date)`; reservation status indexes

### Recommended indexes

| Index | Reason |
|-------|--------|
| `StockReservation (status, expires_at)` | Hot path for `expire_stale_reservations` |
| Unique `BackgroundTaskLog.idempotency_key` | Harden Celery dedupe |

### Transaction safety & concurrency

| Pattern | Location | Assessment |
|---------|----------|------------|
| `select_for_update()` on orders | `orders/services/order_service.py` | ✅ Strong |
| `select_for_update()` on inventory | `inventory/services.py` | ✅ Strong |
| Payment row locks + idempotent `mark_paid` | `payments/services.py` | ✅ Good per-payment |
| Checkout `@transaction.atomic` | `delivery/services.py` | ✅ Good |
| Webhook dedupe | `PaymentEvent.event_id` unique | ✅ Good |
| Celery idempotency | `core/tasks/dispatch.py` | ✅ Good (soft — no DB unique on key) |
| **Cart checkout lock** | — | ❌ **Missing** — same cart can double-checkout |
| **Coupon global limit redeem** | `growth/coupon_service.py` | ⚠️ TOCTOU without row lock |

---

## 3. Core Ecommerce Flow

```
Product → Cart → Checkout → Order → Payment (COD/Stripe) → Inventory → Notifications
                              ↓
                         Growth (coupon/referral) → Loyalty (on paid)
```

**Orchestration entry:** `apps/delivery/services.py` — `DeliveryServiceCheckout.process_checkout()`

### Flow assessment

| Stage | Status | Notes |
|-------|--------|-------|
| Add to cart | ⚠️ | Reservations created on `add_item()` only |
| Stock check | ✅ | `StockService.check_availability` before checkout |
| Growth discounts | ✅ | `GrowthCheckoutFacade.prepare` applies coupon/promo/referral |
| Order creation | ✅ | Atomic with stock reserve + cart clear |
| COD | ✅ | Phone required; stock confirmed on placement |
| Online (Stripe) | ⚠️ | Session created; webhook finalizes |
| Inventory fulfill | ✅ | `fulfill_reservations` on COD cash / delivery complete |
| Notifications | ✅ | Celery SMS via order signals + idempotency |
| Loyalty | ⚠️ | Award on paid; limited test coverage |

### Critical weak points

| # | Issue | Risk | Location |
|---|-------|------|----------|
| 1 | **Stripe charge ≠ order total** (no delivery fee / coupon in line items) | Customer pays wrong amount | `payments/providers/stripe.py` |
| 2 | **Multiple Stripe sessions per order** | Double charge possible | `payments/services.py`, `payments/views.py` |
| 3 | **Same-cart parallel checkout** | Duplicate orders | `delivery/services.py` (no cart lock) |
| 4 | **Cart reservation leaks** on remove/qty change | Inflated reserved stock | `cart/services.py` |
| 5 | **Stripe session expired** leaves orphan order + reserved stock | DB clutter until 120min expiry job | `payments/providers/stripe.py` |
| 6 | **`mark_paid` idempotent per Payment, not per Order** | Second payment webhook edge case | `payments/services.py` |

### Failure states covered by tests

- Empty cart, out of stock, payment failed webhook, webhook dedupe, coupon/referral abuse, SMS dedupe, stale stock expiry

### Failure states NOT covered by tests

- Undeliverable address, Stripe session expired cleanup, loyalty double-award, same-cart concurrent checkout, cart reservation sync

---

## 4. Apps Review

| App | Purpose | Risk | Production concerns | Tests |
|-----|---------|------|---------------------|-------|
| **products** | Catalog, pricing, availability flag | Medium | Price snapshot at order time; availability not always synced with inventory | Indirect only |
| **cart** | Session/user cart, coupon codes | **High** | Reservation leaks; no checkout lock; merge cart edge cases | **None dedicated** |
| **orders** | Order models, lifecycle, events | **High** | Order number generation (5-attempt loop, no DB constraint) | ✅ Unit + integration |
| **payments** | Stripe + COD, webhooks | **Critical** | Amount mismatch, duplicate sessions, expired session orphans | ✅ Unit + integration |
| **delivery** (`fulfillment`) | Zones, fees, checkout orchestration, state machine | **High** | Payment method from settings only; zone scan O(n) | **None for DeliveryService** |
| **inventory** | Stock, capacity, reservations | **Critical** | Strongest part of stack; Celery expiry dependency | ✅ Unit + concurrency (PG only) |
| **notifications** | Kavenegar SMS, templates, retry | Medium | Quiet hours, dedupe via SMSLog queries | ✅ Integration + edge cases |
| **accounts** | CustomerProfile, saved addresses | Low–Medium | No phone format validation | **None** |
| **loyalty** | Points tiers, earn on paid | Medium | Idempotent via transaction filter | **None dedicated** |
| **growth** | Coupons, referrals, CLV, abandoned cart, analytics | **High** | Coupon redeem TOCTOU; deferred until payment (correct) | ✅ Coupon/referral unit + integration |
| **intelligence** | Recommendations, forecasting, upsells | Low | Read/analytics; not order-critical | **None** |

**Note:** `wishlist` app exists but was out of audit scope. Server logs show `VariableDoesNotExist: Failed lookup for key [name] in URLResolver (wishlist)` — likely a template URL reference bug affecting runtime pages.

---

## 5. Celery / Redis

### Configuration (`config/settings/base.py`)

| Setting | Value |
|---------|-------|
| Broker | `CELERY_BROKER_URL` (default `redis://localhost:6379/0`) |
| Result backend | Same as broker |
| Reliability | `ACKS_LATE`, `REJECT_ON_WORKER_LOST`, prefetch 1 |
| Queues | `default`, `sms`, `orders`, `analytics` |
| SMS rate limit | 30/min on `send_sms_event_task` |

### Beat schedule (13 jobs)

| Job | Schedule |
|-----|----------|
| Expire stale reservations | Every 15 min |
| Retry failed SMS | Every 30 min |
| Abandoned cart SMS | Hourly |
| Daily analytics / revenue / CLV / intelligence | 02:00–06:00 UTC window |
| Personalized SMS offers | Tue/Fri 11:00 |

### Production stack (`docker-compose.production.yml`)

- `redis:7-alpine` with 512MB LRU
- `celery_worker` — queues `default,sms,orders,analytics`, concurrency 4
- `celery_beat` — depends on worker
- Redis DB split: cache DB 1, broker DB 0

### Gaps

| Issue | Severity |
|-------|----------|
| No Flower / Celery monitoring | Medium |
| Health endpoint doesn't check Redis/Celery | Medium |
| `claim_idempotency_key` check-then-create race | Low |
| Dev compose has no Redis/Celery | Medium (dev/prod parity) |
| Failed task dead-letter logging exists but no alert integration | Medium |

---

## 6. Docker / Deployment

### File inventory

| File | Status |
|------|--------|
| `docker/Dockerfile` | ✅ Python 3.12-slim, prod settings, Gunicorn CMD |
| `docker-compose.yml` | ⚠️ Dev: db + web only, uses prod settings |
| `docker-compose.production.yml` | ✅ Full stack (7 services) |
| `docker/nginx/` | ✅ Main + site + SSL templates |
| `docker/gunicorn.conf.py` | ✅ Preload, max requests, env-configurable |
| `docker/entrypoint.sh` | ✅ Wait DB; optional migrate/collectstatic via env flags |
| `deploy/deploy.sh` | ✅ init/update/migrate/restart/logs |
| `deploy/init-ssl.sh`, `render-nginx.sh`, `healthcheck.sh`, `server-bootstrap.sh` | ✅ |
| `.env.example` | ✅ Comprehensive |
| `.dockerignore` | ❌ **Missing** |
| Deployment README / runbook | ❌ **Missing** |
| CI/CD pipeline | ❌ **Missing** |
| DB backup scripts | ❌ **Missing** |

### Architecture (production)

```
Client → Nginx (80/443) → Gunicorn (web:8000) → Django → PostgreSQL
                              ↓                      ↓
                         static/media volumes      Redis ← Celery worker + beat
                              ↓
                         Certbot (Let's Encrypt)
```

### Deployment blockers

| Blocker | Detail |
|---------|--------|
| `.env` not configured | `deploy.sh` requires `SECRET_KEY`, `POSTGRES_PASSWORD` |
| **No `.dockerignore`** | `COPY . .` can bake local `.env`/secrets into image |
| **Secure cookies before SSL** | Session/CSRF cookies won't work on HTTP-first deploy |
| **`CSRF_TRUSTED_ORIGINS` / `ALLOWED_HOSTS`** | Must match production domain |
| **`DOMAIN` + DNS** | Required for nginx templating and SSL |
| **`gettext-base`** | Required on host for `envsubst` (bootstrap script installs it) |
| **Cert renewal** | `certbot-renew.cron` is comment-only — must add to host crontab |
| **Empty Stripe/Kavenegar keys** | Payments/SMS non-functional until configured |

### What works well

- Full production service definition with healthchecks
- Nginx static/media offloading via shared volumes
- Entrypoint handles migrations + collectstatic for web
- Server bootstrap covers Docker, UFW, fail2ban
- Structured JSON logging + optional Sentry in prod

---

## 7. Tests

### Inventory

| Category | Files | Test functions |
|----------|-------|----------------|
| Unit | 5 files | ~30 |
| Integration | 5 files | ~5 |
| Concurrency | 1 file | 2 (PostgreSQL only) |
| Celery | 1 file | ~4 |
| Edge cases | 1 file | ~7 |
| **Total** | **13 test modules** | **48 collected** |

### Current run result

```
46 passed, 2 skipped in ~1.2s (SQLite, config.settings.test)
2 skipped: concurrency tests require CRUMBS_TEST_POSTGRES=1
```

### Coverage by critical flow

| Flow | Covered? |
|------|----------|
| COD full lifecycle | ✅ `test_flow_cod.py` |
| Online payment fail → retry | ✅ `test_flow_online_payment.py` |
| Coupon at checkout | ✅ `test_flow_coupon.py` |
| Referral + attribution | ✅ `test_flow_referral.py` |
| Order SMS + dedupe | ✅ `test_flow_sms.py` |
| Stock reserve/oversell/expire | ✅ `test_stock_service.py` |
| Parallel checkout (different carts) | ✅ `test_stock_race.py` (PG only) |
| Payment webhook dedupe | ✅ |
| Order state machine | ✅ `test_order_service.py` |
| Same-cart double checkout | ❌ |
| Stripe amount with discounts | ❌ |
| Cart reservation sync | ❌ |
| DeliveryService zones/fees | ❌ |
| Loyalty award idempotency | ❌ |
| Accounts / intelligence | ❌ |

---

## 8. Findings by Priority

### Critical blockers (must fix before production launch with online payments)

1. **Stripe checkout amount mismatch** — line items exclude delivery fee and growth discounts; customer may be charged wrong amount (`payments/providers/stripe.py`)
2. **Duplicate Stripe payment sessions** — multiple `initiate_online()` calls can create multiple chargeable sessions per order (`payments/services.py`)
3. **Missing `.dockerignore`** — risk of baking secrets into Docker image during build
4. **Secure cookies enabled before SSL** — breaks auth/CSRF on HTTP-first deploy (`.env.example` + `prod.py` defaults)
5. **`CSRF_TRUSTED_ORIGINS` not validated at startup** — silent CSRF failures in production

### High priority fixes

6. **Cart row lock at checkout** — prevent same-cart parallel double orders (`delivery/services.py`)
7. **Cart reservation lifecycle** — sync release/reserve on `remove_item()` and `set_item_quantity()` (`cart/services.py`)
8. **Stripe session expired handler** — cancel order + release stock, not just payment row (`payments/providers/stripe.py`)
9. **Run concurrency tests on PostgreSQL in CI** — set `CRUMBS_TEST_POSTGRES=1`
10. **Prod startup validation** — fail fast on empty `POSTGRES_PASSWORD`, localhost-only `ALLOWED_HOSTS`, missing `CSRF_TRUSTED_ORIGINS`
11. **Health check expansion** — include Redis ping (and optionally Celery broker connectivity)

### Medium priority fixes

12. **Coupon global usage limit race** — lock coupon row at redeem time (`growth/coupon_service.py`)
13. **`mark_paid` order-level guard** — reject if order already in paid terminal state
14. **DeliveryService unit tests** — zone resolution, minimum order, fee calculation
15. **Loyalty idempotency tests** — verify no double point awards
16. **Accounts validation** — phone format, address defaults
17. **Certbot renewal automation** — install cron from `deploy/certbot-renew.cron`
18. **DB backup/restore scripts** — pg_dump scheduled job
19. **Deployment runbook** — document init → SSL → verify sequence
20. **Dev compose parity** — add Redis/Celery or document that background jobs don't run locally via compose

### Nice-to-have

21. Celery Flower or equivalent monitoring
22. Unique DB constraint on `BackgroundTaskLog.idempotency_key`
23. Index on `StockReservation (status, expires_at)`
24. Intelligence/upsell test coverage
25. CI/CD pipeline (GitHub Actions: lint, test, build, deploy)
26. Fix wishlist template `URLResolver.name` runtime error in logs
27. Gunicorn async/gevent worker evaluation for I/O-bound views
28. Stripe refund API integration (webhook currently updates order state only)

---

## Recommended Next 5 Tasks

1. **Fix Stripe payment integrity** — align Stripe session total with `order.total` (delivery + discounts); block duplicate session creation per order
2. **Add `.dockerignore` + document `.env` deploy checklist** — prevent secret leakage; fix secure-cookie/SSL ordering for first deploy
3. **Lock cart at checkout** — `select_for_update()` on cart row inside `process_checkout()` + test for concurrent duplicate orders
4. **Enable PostgreSQL concurrency tests in CI** — add `CRUMBS_TEST_POSTGRES=1` job; fix cart reservation sync with tests
5. **Harden prod startup** — validate `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS`, `POSTGRES_PASSWORD`; extend `/health/` to check Redis

---

## Appendix: Key File References

| Area | Path |
|------|------|
| Settings base | `config/settings/base.py` |
| Settings prod | `config/settings/prod.py` |
| Checkout orchestration | `apps/delivery/services.py` |
| Order lifecycle | `apps/orders/services/order_service.py` |
| Payments | `apps/payments/services.py`, `apps/payments/providers/stripe.py` |
| Inventory | `apps/inventory/services.py` |
| Celery app | `config/celery.py` |
| Health check | `apps/core/health_views.py` |
| Docker prod | `docker-compose.production.yml` |
| Deploy scripts | `deploy/deploy.sh` |
| Test suite | `tests/` (48 tests) |
| Env template | `.env.example` |

---

*Report generated from read-only audit. No code was modified.*
