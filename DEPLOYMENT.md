# Deployment

نقطه ورود سریع برای استقرار تولید Crumbs.

نسخه مستند: `v2.0.1`

## مسیر و فایل‌های کلیدی

| مورد | مقدار |
| --- | --- |
| مسیر استاندارد روی سرور | `/opt/crumbs` |
| Compose تولید | `docker-compose.production.yml` |
| Env | `.env` (از روی `.env.example`) |
| اسکریپت اصلی | `./deploy/deploy.sh` |

## فرمان Compose

همه فرمان‌های تولید باید از ریشه پروژه و با `--env-file` اجرا شوند:

```bash
cd /opt/crumbs
docker compose --env-file .env -f docker-compose.production.yml <command>
```

اسکریپت `deploy/deploy.sh` همین الگوی Compose را استفاده می‌کند.

## به‌روزرسانی معمول

```bash
cd /opt/crumbs
# توصیه: قبل از deploy پشتیبان بگیرید
./deploy/backup.sh all

git pull
./deploy/deploy.sh update
```

`deploy.sh update` سرویس `web` را rebuild/recreate می‌کند، Nginx را reload می‌کند، سپس health check را اجرا می‌کند.

## استقرار اولیه

راهنمای مرحله‌به‌مرحله:

1. [`docs/VPS_LAUNCH_RUNBOOK.md`](docs/VPS_LAUNCH_RUNBOOK.md)
2. [`docs/LAUNCH_CHECKLIST.md`](docs/LAUNCH_CHECKLIST.md)
3. [`docs/06-راهنمای-استقرار.md`](docs/06-راهنمای-استقرار.md)

متغیرهای محیطی:

- [`.env.example`](.env.example)
- [`DEPLOYMENT_ENV_CHECKLIST.md`](DEPLOYMENT_ENV_CHECKLIST.md)

## بررسی سلامت

```bash
cd /opt/crumbs
./deploy/healthcheck.sh
```

Endpointهای داخلی اپلیکیشن: `/health/`، `/ready/`، `/health/full/`.

## Backup / Restore

- [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md)
- `./deploy/backup.sh`
- `./deploy/restore.sh`
