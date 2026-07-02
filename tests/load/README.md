# Lightweight Load Simulation

This document describes how to stress-test CRUMBS without adding load-test code to the application.

## Goals

- 100 concurrent checkouts
- Celery worker queue depth under burst order events
- Database row-lock contention on `ProductInventory` / `StockReservation`

## Prerequisites

- Production-like stack: PostgreSQL, Redis, Celery worker + beat
- Staging environment with test payment/SMS providers disabled or mocked
- Seed catalog with at least one high-demand SKU (e.g. 50 units)

## 1. Concurrent checkout (Locust)

```bash
pip install locust
```

Create `locustfile.py` at repo root (local only, not committed unless approved):

```python
from locust import HttpUser, task, between

class CheckoutUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        self.client.post("/accounts/login/", {"username": "loaduser", "password": "pass"})

    @task
    def checkout_cod(self):
        self.client.post("/cart/add/", {"product_id": 1, "quantity": 1})
        self.client.post("/checkout/", {
            "email": "load@test.com",
            "phone": "09120000000",
            "city": "Tehran",
            # ... remaining checkout fields
        })
```

Run:

```bash
locust -f locustfile.py --host=https://staging.crumbs.example --users 100 --spawn-rate 10
```

**Pass criteria:**

- No negative `available_quantity` in `inventory_productinventory`
- HTTP 4xx for oversell attempts, not 500s
- Order count ≤ starting stock for the SKU

## 2. Celery worker load

During Locust run, monitor:

```bash
celery -A config inspect active_queues
redis-cli -n 0 llen celery
```

Watch `BackgroundTaskLog` for duplicate skips (`Skipping duplicate task` in logs).

**Pass criteria:**

- SMS queue drains within SLA (e.g. 5 min for 100 orders)
- No duplicate `SMSLog` rows with same `dedupe_key`
- Idempotency keys prevent double lifecycle processing

## 3. Database locking

On PostgreSQL during peak:

```sql
SELECT pid, wait_event_type, wait_event, query
FROM pg_stat_activity
WHERE datname = 'crumbs' AND wait_event_type IS NOT NULL;
```

```sql
SELECT relname, mode, granted
FROM pg_locks
JOIN pg_class ON pg_locks.relation = pg_class.oid
WHERE relname LIKE '%inventory%' OR relname LIKE '%stock%';
```

**Pass criteria:**

- Lock waits resolve within seconds, not minutes
- No deadlocks in application logs

## 4. Automated concurrency subset

For CI/staging smoke, run the pytest concurrency suite against PostgreSQL:

```bash
CRUMBS_TEST_POSTGRES=1 pytest tests/concurrency/ -v
```

This validates 10–50 parallel COD checkouts without external load tools.

## 5. Recommended staging checklist

1. Seed 100 test users + shared delivery zone (Tehran)
2. Set product stock to known quantity (e.g. 25)
3. Run Locust 100 users for 5 minutes
4. Assert: `reserved_quantity + available_quantity == stock_quantity` per product
5. Drain Celery queues; verify SMS count ≤ orders × expected templates
6. Review `PaymentEvent` for duplicate `event_id` handling
