# CRUMBS — Launch Test Plan

Manual verification checklist before accepting production traffic. Run against the live domain over **HTTPS** after Phase 2 deploy, unless noted.

Record: tester name, date, git commit, `SITE_URL`, pass/fail per row.

---

## Public site

### Pages & navigation

| # | Test | Steps | Expected | Pass |
|---|------|-------|----------|------|
| P1 | Home loads | Open `/` | 200, hero and featured products visible | ☐ |
| P2 | Shop loads | Open `/shop/` | Product grid, categories | ☐ |
| P3 | Product detail | Click a product | Name, price, image, add-to-cart | ☐ |
| P4 | Desktop nav | Resize ≥1024px | Header links work | ☐ |
| P5 | Mobile drawer | Resize &lt;768px, open menu | Drawer opens; includes «سبد خرید»; links work; closes on navigate | ☐ |
| P5b | Drawer cart badge | Empty cart, then add ≥1 item and reopen drawer | Badge hidden when empty; count shown when cart has items | ☐ |
| P6 | Footer links | Click footer items | Contact, careers, legal pages load | ☐ |
| P7 | robots.txt | `curl -I /robots.txt` | HTTP 200 | ☐ |
| P8 | sitemap.xml | `curl -I /sitemap.xml` | HTTP 200 | ☐ |

### Cart & checkout

| # | Test | Steps | Expected | Pass |
|---|------|-------|----------|------|
| C1 | Add to cart | Add product from shop/detail | Cart count updates | ☐ |
| C2 | Update quantity | Change qty in cart | Line total recalculates | ☐ |
| C3 | Remove item | Remove line from cart | Item gone; empty state if last item | ☐ |
| C4 | Checkout COD / counter | Complete checkout (in-cafe pickup flow) | Order created, confirmation shown | ☐ |
| C5 | Zarinpal (if configured) | Online payment with sandbox or live merchant | Redirect to gateway; callback returns; order paid | ☐ |
| C6 | Order confirmation | After successful checkout | Confirmation page with order reference | ☐ |

### Account

| # | Test | Steps | Expected | Pass |
|---|------|-------|----------|------|
| A1 | Login / register | Sign in or create account | Session works over HTTPS | ☐ |
| A2 | Order history | `/accounts/orders/` | Recent test order listed | ☐ |
| A3 | Order detail | Open order from history | Items, status, totals correct | ☐ |

### Forms

| # | Test | Steps | Expected | Pass |
|---|------|-------|----------|------|
| F1 | Careers form — valid | Submit with PDF resume | Success message; application in admin | ☐ |
| F2 | Careers — PDF validation | Upload non-PDF or corrupt file | Validation error, no save | ☐ |
| F3 | Careers — size limit | Upload oversized PDF | Size error | ☐ |
| F4 | Contact form — valid | Submit required fields | Success / thank you | ☐ |
| F5 | Contact form — invalid | Submit empty required fields | Inline errors | ☐ |

---

## Django admin

Login at `/admin/` with superuser. Persian panel headers should show «مدیریت Crumbs».

| # | Test | Steps | Expected | Pass |
|---|------|-------|----------|------|
| D1 | Admin login | `/admin/` over HTTPS | Login works; CSRF OK | ☐ |
| D2 | Create / edit product | Products → add or edit | Saves; thumbnail preview | ☐ |
| D3 | Edit inventory | Inventory → adjust stock | `available_quantity` updates correctly | ☐ |
| D4 | View order | Orders → open test order | Customer, items, totals readonly | ☐ |
| D5 | Change order status | Action: در حال آماده‌سازی → آماده تحویل → تحویل‌شده | Status transitions via service | ☐ |
| D6 | Review career application | Careers → open submission | HR answers, resume link | ☐ |
| D7 | Career status action | Mark reviewing / rejected / hired | Status updates | ☐ |
| D8 | Check payments | Payments → filter by order | Provider, status, amount; no raw secrets | ☐ |

---

## Operations

| # | Test | Steps | Expected | Pass |
|---|------|-------|----------|------|
| O1 | Backup database | `./deploy/backup.sh db` | `backups/db/crumbs_db_*.sql.gz` created | ☐ |
| O2 | Backup media | `./deploy/backup.sh media` | `backups/media/crumbs_media_*.tar.gz` created | ☐ |
| O3 | Health (liveness) | `curl -I https://domain/health/` | HTTP 200, no DB dependency | ☐ |
| O4 | Ready (readiness) | `curl https://domain/ready/` | HTTP 200, `ready: true`, DB + Redis OK | ☐ |
| O5 | Web logs | `docker compose -f docker-compose.production.yml logs --tail=50 web` | No critical tracebacks | ☐ |
| O6 | Celery worker | `docker compose ... logs --tail=30 celery_worker` | Worker connected, no crash loop | ☐ |
| O7 | Celery beat | `docker compose ... logs --tail=30 celery_beat` | Beat schedule running | ☐ |
| O8 | Stale payment cleanup | Confirm beat task registered | `payments.tasks.cleanup_stale_online_payments_task` in logs or admin ops | ☐ |
| O9 | Sentry (if configured) | Trigger test error or check Sentry dashboard | Event received with `SENTRY_ENVIRONMENT` | ☐ |
| O10 | Smoke script | `./deploy/staging-smoke-test.sh "https://domain"` | Exits 0 | ☐ |

---

## Security spot-checks

| # | Test | Expected | Pass |
|---|------|----------|------|
| S1 | `DEBUG` off | No stack traces on 500 pages | ☐ |
| S2 | HTTP → HTTPS | `curl -I http://domain/` redirects to HTTPS (Phase 2) | ☐ |
| S3 | Admin over HTTPS | Cookies marked Secure | ☐ |
| S4 | Media PDF | Resume URL serves `Content-Type` safe (not executable) | ☐ |

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Deploy / ops | | | |
| Product / QA | | | |

**Go / no-go:** ☐ Go live &nbsp; ☐ Hold — issues: _______________
