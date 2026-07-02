# CRUMBS — Final Launch Checklist

Master checklist for real VPS / domain / SSL go-live. No new features — audit, document, and verify readiness only.

**Related docs**

| Doc | Purpose |
|-----|---------|
| [DEPLOYMENT_ENV_CHECKLIST.md](../DEPLOYMENT_ENV_CHECKLIST.md) | Full `.env` variable reference |
| [VPS_LAUNCH_RUNBOOK.md](VPS_LAUNCH_RUNBOOK.md) | Step-by-step deploy + SSL |
| [LAUNCH_TEST_PLAN.md](LAUNCH_TEST_PLAN.md) | Manual functional tests |
| [BACKUP_RESTORE.md](BACKUP_RESTORE.md) | Backup schedule and restore |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Logs, Sentry, health endpoints |
| [LOCAL_PROD_DRY_RUN.md](../LOCAL_PROD_DRY_RUN.md) | Local Docker dry-run (differs from VPS) |

---

## 1. Production `.env` checklist

Copy `.env.example` → `.env` on the server (`chmod 600 .env`). Never commit `.env` or backup archives.

| Variable | VPS requirement | Phase 1 (HTTP) | Phase 2 (HTTPS) |
|----------|-----------------|----------------|-----------------|
| `SECRET_KEY` | **Required** — 50+ random chars | ✓ | ✓ |
| `DEBUG` | **Must be** `False` | ✓ | ✓ |
| `LOCAL_PROD_DRY_RUN` | **Must be** `False` on VPS | ✓ | ✓ |
| `DOMAIN` | Real domain (e.g. `crumbs.ir`) | ✓ | ✓ |
| `ALLOWED_HOSTS` | Real domain(s), not localhost-only | ✓ | ✓ |
| `CSRF_TRUSTED_ORIGINS` | `http://` origins | `https://` origins | switch at SSL |
| `SITE_URL` | `http://domain` | `https://domain` | switch at SSL |
| `ENABLE_HTTPS` | `False` | `True` | after SSL |
| `POSTGRES_PASSWORD` | **Required** — strong unique password | ✓ | ✓ |
| `ZARINPAL_MERCHANT_ID` | Production merchant UUID | ✓ | ✓ |
| `ZARINPAL_CALLBACK_URL` | `https://domain/payments/zarinpal/callback/` | HTTP OK for phase 1 test | HTTPS for live |
| `ZARINPAL_SANDBOX` | `False` for live payments | `True` only for sandbox test | `False` |
| `SMS_PROVIDER` | `kavenegar` (or `console` to disable real SMS) | ✓ | ✓ |
| `SMS_ENABLED` | `True` / `False` per ops choice | ✓ | ✓ |
| `KAVENEGAR_API_KEY` | Required if `SMS_PROVIDER=kavenegar` | ✓ | ✓ |
| `SENTRY_DSN` | Optional — empty disables Sentry | optional | optional |
| `CERTBOT_EMAIL` | Valid email for Let's Encrypt | ✓ (before SSL) | ✓ |

### Backup expectations

| Item | Expectation |
|------|-------------|
| **Before every deploy** | `./deploy/backup.sh all` |
| **Storage** | `backups/db/` and `backups/media/` on server (gitignored) |
| **Off-server copy** | Copy `.sql.gz` / `.tar.gz` to separate storage (rsync, S3, etc.) |
| **Never commit** | Backup archives must not enter git |
| **Restore** | Destructive — `CONFIRM_RESTORE=yes` only; see [BACKUP_RESTORE.md](BACKUP_RESTORE.md) |

---

## 2. Final VPS command flow

Run from repository root on the Ubuntu VPS after DNS `A` record points to the server.

```bash
# 0. Bootstrap (fresh server only)
bash deploy/server-bootstrap.sh

# 1. Clone and configure
git clone <your-repo-url> crumbs && cd crumbs
cp .env.example .env
chmod 600 .env
nano .env   # Phase 1 values: ENABLE_HTTPS=False, real DOMAIN, ALLOWED_HOSTS, secrets

# 2. Validate compose resolves env (no secrets printed)
docker compose --env-file .env -f docker-compose.production.yml config > /dev/null && echo "compose OK"

# 3. First deploy (HTTP)
chmod +x deploy/*.sh
./deploy/deploy.sh init

# 4. Create admin
docker compose --env-file .env -f docker-compose.production.yml exec web \
  python manage.py createsuperuser

# 5. Verify HTTP health
curl -sS "http://${DOMAIN}/health/"
curl -sS "http://${DOMAIN}/ready/"

# 6. SSL (ports 80 + 443 open; CERTBOT_EMAIL set)
./deploy/init-ssl.sh

# 7. Phase 2 — confirm .env (init-ssl.sh updates most values; review manually)
#    ENABLE_HTTPS=True, SITE_URL=https://..., CSRF_TRUSTED_ORIGINS=https://...
./deploy/deploy.sh update

# 8. Verify HTTPS
curl -I "https://${DOMAIN}/health/"
curl -sS "https://${DOMAIN}/ready/"

# 9. Pre-launch backup
./deploy/backup.sh all

# 10. Run manual tests — see LAUNCH_TEST_PLAN.md
./deploy/healthcheck.sh
./deploy/staging-smoke-test.sh "https://${DOMAIN}"
```

### Ongoing operations

```bash
./deploy/backup.sh all
git pull
./deploy/deploy.sh update
curl -I "https://yourdomain.com/health/"
curl -sS "https://yourdomain.com/ready/"
docker compose -f docker-compose.production.yml logs -f web
```

---

## 3. Domain + SSL

| Step | Action |
|------|--------|
| **DNS** | `A` record for apex (`crumbs.ir`) and `www` → VPS public IP |
| **Firewall** | Allow **80** (ACME + redirect) and **443** (HTTPS); restrict SSH |
| **Certbot email** | Set `CERTBOT_EMAIL` in `.env` before `./deploy/init-ssl.sh` |
| **Phase 1** | HTTP deploy with `ENABLE_HTTPS=False`; verify site loads on port 80 |
| **SSL issue** | `./deploy/init-ssl.sh` — Let's Encrypt webroot challenge via nginx |
| **Phase 2** | `ENABLE_HTTPS=True`, `SITE_URL=https://...`, secure cookies; `./deploy/deploy.sh update` |
| **HSTS** | `SECURE_HSTS_SECONDS=31536000` only **after** HTTPS works end-to-end |
| **HSTS preload** | Keep `SECURE_HSTS_PRELOAD=False` until deliberate review |

> `config.settings.prod` ignores insecure cookie env vars when `ENABLE_HTTPS=False` and enforces secure cookies when `ENABLE_HTTPS=True`.

---

## 4. Security checklist

- [ ] `DEBUG=False` (enforced — `True` raises at import)
- [ ] Strong `SECRET_KEY` (50+ chars, unique per environment)
- [ ] `LOCAL_PROD_DRY_RUN=False` on VPS
- [ ] `ALLOWED_HOSTS` lists real domain(s) only
- [ ] `ENABLE_HTTPS=True` after SSL certificate active
- [ ] `CSRF_TRUSTED_ORIGINS` matches `https://` site URL(s)
- [ ] Secure session/CSRF cookies (automatic when `ENABLE_HTTPS=True`)
- [ ] HSTS enabled only after HTTPS verified (`SECURE_HSTS_SECONDS=31536000`)
- [ ] `SECURE_HSTS_PRELOAD=False` unless preload deliberately approved
- [ ] Admin superuser uses strong password; limit SSH access to server
- [ ] No `.env`, API keys, or backup archives in git
- [ ] `.env` permissions `chmod 600`
- [ ] `/media/` served as static files only (nginx `application/octet-stream`, no script handlers)
- [ ] Career PDF uploads validated (extension + magic bytes) — no executable uploads
- [ ] `ZARINPAL_SANDBOX=False` for live payments
- [ ] Stripe disabled (`STRIPE_ENABLED=False`) for Iran production unless explicitly needed

---

## 5. Automated checks (run before go-live)

### On VPS (production-like `.env`)

Run from the server with Phase 2 values loaded (after SSL). `check --deploy` reads `.env` via `load_dotenv` — stale Phase 1 cookie vars will cause security warnings until updated.

```bash
python manage.py check
python manage.py check --deploy --settings=config.settings.prod
python manage.py check_migration_history
pytest -q   # CI / dev machine
```

Expected after Phase 2: only `security.W021` (HSTS preload) may remain — keep `SECURE_HSTS_PRELOAD=False` unless deliberately enabling preload.

### Local Docker dry-run (differs from VPS)

When testing locally with `.env.local-prod.example`:

| Check | Local dry-run | VPS |
|-------|---------------|-----|
| `LOCAL_PROD_DRY_RUN` | `True` | `False` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | real domain |
| `manage.py check --deploy` | May warn on `ALLOWED_HOSTS` / `SECRET_KEY` | Must pass clean |
| SSL | Skipped or port 8443 | Let's Encrypt on 443 |
| Payments | `ZARINPAL_SANDBOX=True` OK | `False` for live |

See [LOCAL_PROD_DRY_RUN.md](../LOCAL_PROD_DRY_RUN.md) for local validation steps.

---

## 6. Launch blockers (audit summary)

| Area | Status | Notes |
|------|--------|-------|
| Production settings | ✓ Ready | Two-phase HTTP→HTTPS; `DEBUG=False` enforced |
| Docker compose | ✓ Ready | Health/readiness endpoints configured |
| Deploy scripts | ✓ Ready | `init`, `update`, `init-ssl`, `backup.sh` |
| Backup/restore | ✓ Documented | [BACKUP_RESTORE.md](BACKUP_RESTORE.md) |
| Observability | ✓ Ready | Sentry optional; JSON logs; `/health/`, `/ready/` |
| Migrations | ✓ | Run `check_migration_history` before deploy |
| **Operator actions** | ⚠ Required | Set real secrets, DNS, SSL, Zarinpal merchant, SMS keys |
| **init-ssl.sh** | ✓ Fixed | Now updates cookies, HSTS, and `CSRF_TRUSTED_ORIGINS` in `.env` |
| **Manual QA** | ⚠ Required | Complete [LAUNCH_TEST_PLAN.md](LAUNCH_TEST_PLAN.md) |

No code launch blockers identified. Go-live depends on correct server configuration and manual verification.

---

## 7. Post-launch

- [ ] Complete [LAUNCH_TEST_PLAN.md](LAUNCH_TEST_PLAN.md)
- [ ] `./deploy/backup.sh all` + off-server copy
- [ ] Monitor logs and Sentry for 24–48 hours
- [ ] Schedule nightly backups (cron: `./deploy/backup.sh all`)
- [ ] Record launch date and git commit in your ops log
