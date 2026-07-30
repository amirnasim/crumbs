# Installation

نقطه ورود سریع برای نصب و اجرای محلی Crumbs.

نسخه مستند: `v2.0.1`

## پیش‌نیازها

- Python 3.12
- PostgreSQL (برای توسعه محلی کامل)
- Docker و Docker Compose (اختیاری؛ برای stack کانتینری)
- فایل `.env` بر اساس `.env.example`

جزئیات بیشتر در [`README.md`](README.md) و [`docs/07-راهنمای-توسعه.md`](docs/07-راهنمای-توسعه.md).

## نصب با Virtualenv

```bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements/dev.txt

cp .env.example .env
# مقادیر محلی را تنظیم کنید؛ حداقل:
# DJANGO_SETTINGS_MODULE=config.settings.dev
# DEBUG=True
# POSTGRES_* و SITE_URL=http://localhost:8000
# SMS_PROVIDER=console

python manage.py migrate
python manage.py runserver
```

Seed اختیاری:

```bash
python manage.py seed_iran_defaults
python manage.py seed_intelligence_defaults
```

## نصب با Docker Compose (محلی)

```bash
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py migrate
```

فایل Compose محلی: `docker-compose.yml`.

## تست

```bash
python manage.py check
pytest -q
```

وضعیت شناخته‌شده در `v2.0.1`: `422 passed, 4 skipped`.

## استقرار تولید

برای VPS و Docker Compose تولیدی به [`DEPLOYMENT.md`](DEPLOYMENT.md) مراجعه کنید.
