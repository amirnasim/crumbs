# CRUMBS Production Test Suite

Production-grade pytest suite for CRUMBS Django ecommerce. Tests cover unit services, integration flows, concurrency, Celery reliability, and edge cases — without calling real SMS or payment APIs.

## Architecture

```
tests/
├── conftest.py              # Shared fixtures (users, products, mocks)
├── factories.py             # Lightweight test data builders
├── mocks/
│   ├── payments.py          # MockPaymentProvider (Stripe/Zarinpal stand-in)
│   └── sms.py               # RecordingSMSProvider (Kavenegar stand-in)
├── unit/                    # Isolated service tests
├── integration/             # End-to-end business flows (A–E)
├── concurrency/             # Parallel checkout / stock races (PostgreSQL)
├── celery/                  # Idempotency, task fan-out, Beat schedule
├── edge_cases/              # Webhook dupes, abuse, expired carts
└── load/
    └── README.md            # Lightweight load simulation guide
```

### Layers

| Layer | Purpose | Marker |
|-------|---------|--------|
| Unit | OrderService, PaymentService, StockService, CouponService, ReferralService | — |
| Integration | COD, online payment, coupon, referral, SMS flows | `@pytest.mark.integration` |
| Concurrency | Parallel checkouts, cart locking, no oversell | `@pytest.mark.concurrency` |
| Celery | `claim_idempotency_key`, lifecycle fan-out, Beat | `@pytest.mark.celery` |
| Edge cases | Duplicate webhooks, SMS dedupe, referral abuse | `@pytest.mark.edge_case` |

### External service mocking

- **SMS**: `mock_sms_provider` fixture patches `notifications.services.get_sms_provider`. Integration SMS flow uses `RecordingSMSProvider`.
- **Payments (default)**: Online checkout integration tests use **mocked Stripe** via `STRIPE_ONLINE_SETTINGS` + `mock_stripe_checkout`. Default `pytest -q` never calls real payment APIs.
- **Zarinpal (unit)**: `tests/unit/test_payment_service.py` mocks `requests.post` and uses `@override_settings` with a test merchant ID. These run in the default suite.
- **Zarinpal (integration, opt-in)**: Tests marked `@pytest.mark.zarinpal_integration` are **skipped** unless `ZARINPAL_MERCHANT_ID` is set in the environment. They still mock HTTP — the env gate prevents accidental reliance on local `.env` provider overrides.
- **Webhooks**: Stripe/Zarinpal webhook tests use `MockPaymentProvider` or mocked HTTP — no external calls in default CI.

### Zarinpal integration mode (optional)

```bash
export ZARINPAL_MERCHANT_ID=your-sandbox-merchant-id
export CRUMBS_TEST_ZARINPAL=1   # optional explicit flag

pytest -m zarinpal_integration -v
pytest tests/integration/test_flow_online_payment.py -v
```

Production still requires a real `ZARINPAL_MERCHANT_ID` in `.env` — test settings do not weaken prod validation.

## Install

```bash
pip install -r requirements/test.txt
```

## Run tests

### Fast tests (SQLite, default)

Uses in-memory SQLite — fast, no Docker required. Concurrency tests are **skipped** because SQLite does not enforce real `select_for_update` row locking.

```bash
pytest -q
```

### PostgreSQL concurrency tests

Concurrency tests validate stock reservation and checkout locking under real row-level locks. They only run when:

1. `CRUMBS_TEST_POSTGRES=1` is set, and
2. PostgreSQL is reachable with the credentials below.

```bash
export CRUMBS_TEST_POSTGRES=1
export TEST_POSTGRES_DB=crumbs_test
export TEST_POSTGRES_USER=crumbs
export TEST_POSTGRES_PASSWORD=crumbs
export TEST_POSTGRES_HOST=localhost
export TEST_POSTGRES_PORT=5432

pytest -m concurrency -v
```

Or use the helper script (sets env vars and runs concurrency tests):

```bash
chmod +x scripts/run_postgres_tests.sh
./scripts/run_postgres_tests.sh
```

### Full suite on PostgreSQL

```bash
CRUMBS_TEST_POSTGRES=1 pytest -q
```

### Other useful commands

```bash
# Unit only
pytest tests/unit/

# Integration flows
pytest -m integration

# With coverage
pytest --cov=apps --cov-report=term-missing
```

## PostgreSQL test database setup

### Option A — Docker Compose (recommended locally)

The repo includes a `db` service (`postgres:16-alpine`) in `docker-compose.yml`:

```bash
# Start PostgreSQL
docker compose up -d db

# Create dedicated test database (once)
docker compose exec db psql -U "${POSTGRES_USER:-crumbs}" -d postgres \
  -c "CREATE DATABASE crumbs_test;" 2>/dev/null || true

# Run concurrency tests
CRUMBS_TEST_POSTGRES=1 pytest -m concurrency -v
```

Default credentials match `docker-compose.yml` / `.env.example`:

| Variable | Default |
|----------|---------|
| `TEST_POSTGRES_DB` | `crumbs_test` |
| `TEST_POSTGRES_USER` | `crumbs` |
| `TEST_POSTGRES_PASSWORD` | `crumbs` |
| `TEST_POSTGRES_HOST` | `localhost` |
| `TEST_POSTGRES_PORT` | `5432` |

Use a **separate** test database (`crumbs_test`), not the app database (`crumbs`).

### Option B — Local PostgreSQL

```bash
createdb -U crumbs crumbs_test
CRUMBS_TEST_POSTGRES=1 pytest -m concurrency -v
```

pytest-django creates/applies migrations on the test database automatically.

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Tests skipped with “require PostgreSQL” | `CRUMBS_TEST_POSTGRES` not set | Export `CRUMBS_TEST_POSTGRES=1` |
| `connection refused` | DB not running | `docker compose up -d db` |
| `database "crumbs_test" does not exist` | Test DB not created | Run the `CREATE DATABASE` command above |
| Deadlock under extreme parallelism | Postgres row-lock contention in stress tests | Expected; tests treat deadlocks as failed checkout attempts |
| Teardown warning about open sessions | Thread pool left DB connections open | Use `--reuse-db`; concurrency tests close connections per thread |

## Settings reference

`config/settings/test.py`:

| Mode | Trigger | Database |
|------|---------|----------|
| Fast (default) | *(unset)* | SQLite `:memory:` |
| PostgreSQL | `CRUMBS_TEST_POSTGRES=1` | PostgreSQL via `TEST_POSTGRES_*` env vars |

Other test defaults:

- `CELERY_TASK_ALWAYS_EAGER=True` — tasks run synchronously
- `SMS_PROVIDER=console`, mock Stripe keys
- MD5 password hasher for speed

## CI / staging readiness

No GitHub Actions workflow is checked in yet. When adding CI, use **PostgreSQL 16** as a service:

```yaml
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_USER: crumbs
      POSTGRES_PASSWORD: crumbs
      POSTGRES_DB: crumbs_test
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U crumbs -d crumbs_test"
      --health-interval 5s
      --health-timeout 5s
      --health-retries 5

env:
  CRUMBS_TEST_POSTGRES: "1"
  TEST_POSTGRES_DB: crumbs_test
  TEST_POSTGRES_USER: crumbs
  TEST_POSTGRES_PASSWORD: crumbs
  TEST_POSTGRES_HOST: localhost
  TEST_POSTGRES_PORT: 5432

steps:
  - run: pytest -m concurrency -v
  - run: CRUMBS_TEST_POSTGRES=1 pytest -q
```

Suggested CI jobs:

1. **Fast gate** — `pytest -q` (SQLite, ~1 min)
2. **Concurrency gate** — `CRUMBS_TEST_POSTGRES=1 pytest -m concurrency -v` (PostgreSQL)

## Critical flows covered

| Flow | File |
|------|------|
| A — COD order lifecycle | `integration/test_flow_cod.py` |
| B — Online payment fail → retry | `integration/test_flow_online_payment.py` |
| C — Coupon discount correctness | `integration/test_flow_coupon.py` |
| D — Referral reward + attribution | `integration/test_flow_referral.py` |
| E — SMS + deduplication | `integration/test_flow_sms.py` |

## Success criteria

- All critical business flows have integration coverage
- Duplicate payment webhooks processed once (`PaymentEvent.processed`)
- SMS dedupe via `SMS_DEDUPE_WINDOW_SECONDS` + explicit `dedupe_key`
- Stock reservations use `select_for_update`; concurrency tests validate no oversell on PostgreSQL
- Celery tasks testable via eager mode + `BackgroundTaskLog` idempotency

## Load simulation

See [load/README.md](load/README.md) for 100 concurrent checkout guidance.
