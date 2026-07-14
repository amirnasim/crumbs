# Crumbs

سامانه جامع سفارش‌گیری و مدیریت کافه و بیکری

نسخه فعلی: `v1.0.2`

---

## معرفی پروژه

Crumbs یک سامانه تحت وب برای سفارش‌گیری، پرداخت، مدیریت عملیات کافه و بیکری، کنترل موجودی، رهگیری سفارش و پشتیبانی از فرآیندهای مدیریتی است. این پروژه برای یک کسب‌وکار کافه/بیکری طراحی شده که نیاز دارد سفارش‌های حضوری و آنلاین، موجودی قابل فروش، پرداخت‌ها، وضعیت سفارش‌ها، پیامک‌ها، گزارش‌های عملیاتی و داده‌های رشد را در یک سیستم یکپارچه مدیریت کند.

هدف Crumbs کاهش پیچیدگی عملیاتی فروش روزانه و ایجاد یک جریان قابل اتکا از انتخاب محصول تا ثبت سفارش، پرداخت، رزرو موجودی، آماده‌سازی، تحویل از کانتر و گزارش‌دهی مدیریتی است.

این سامانه برای مشتریان کافه، کارکنان صندوق و عملیات، مدیران فروش، تیم بازاریابی و مدیران فنی قابل استفاده است. فلسفه طراحی پروژه بر پایه سادگی تجربه مشتری، شفافیت وضعیت سفارش، کنترل دقیق موجودی، آمادگی برای تولید و قابلیت نگهداری بلندمدت است.

---

## قابلیت‌های اصلی

### امکانات مشتری

- مشاهده صفحه اصلی، منو، دسته‌بندی‌ها و جزئیات محصولات
- مشاهده محصولات ویژه و محصولات مرتبط
- افزودن محصول به سبد خرید
- تغییر تعداد اقلام سبد خرید و حذف اقلام
- نمایش تعداد اقلام سبد خرید در هدر موبایل و دسکتاپ
- رزرو موجودی هنگام افزودن/به‌روزرسانی سبد خرید
- ثبت سفارش برای تحویل از کانتر
- انتخاب روش پرداخت:
  - پرداخت آنلاین
  - پرداخت حضوری
- اتصال به جریان پرداخت آنلاین
- ثبت سفارش حضوری با پرداخت هنگام تحویل سفارش
- مشاهده صفحه تأیید سفارش
- مشاهده رسید سفارش
- نمایش وضعیت سفارش با تایم‌لاین فارسی
- ورود، ثبت‌نام و مدیریت حساب کاربری
- مشاهده تاریخچه و جزئیات سفارش‌ها
- مدیریت اطلاعات پروفایل
- مدیریت علاقه‌مندی‌ها
- ثبت درخواست همکاری از طریق فرم استخدام
- دریافت پیام‌ها و خطاهای کاربرپسند فارسی در جریان سفارش
- پشتیبانی از شماره میز یا یادداشت سفارش
- پشتیبانی از صفحات SEO مانند `robots.txt` و `sitemap.xml`

### امکانات مدیریت

- پنل مدیریت Django با برچسب‌ها و نام‌گذاری فارسی
- مدیریت محصولات، دسته‌بندی‌ها و تصاویر
- مدیریت سفارش‌ها، اقلام سفارش و وضعیت پرداخت
- مشاهده شماره روزانه سفارش‌ها برای عملیات کافه
- مدیریت سفارش‌های در انتظار پرداخت حضوری
- داشبورد عملیات و صف آشپزخانه/کانتر
- صفحه جست‌وجوی سفارش
- صفحه خلاصه شیفت و گزارش فروش
- مدیریت موجودی محصول
- رزرو موجودی برای سبد خرید و سفارش
- کنترل ظرفیت تولید روزانه
- آزادسازی رزروهای منقضی‌شده
- مدیریت پرداخت‌ها و رویدادهای پرداخت
- پشتیبانی از پرداخت آنلاین و پرداخت حضوری
- ثبت و پیگیری وضعیت پیامک‌ها
- قالب‌های پیامک برای سفارش، پرداخت، بازاریابی و سبد رهاشده
- سیستم وفاداری، امتیاز و سطح مشتری
- کوپن، کد معرف، کمپین‌های رشد و قوانین پروموشن
- رهگیری رویدادهای رشد مانند مشاهده محصول، افزودن به سبد و تکمیل خرید
- رهگیری سبدهای رهاشده
- تحلیل ارزش مشتری و داده‌های درآمد
- لایه هوش تجاری برای آمار روزانه محصول، پیش‌بینی تقاضا، توصیه پخت، پیشنهاد فروش و پروفایل هوشمند مشتری
- لاگ وظایف پس‌زمینه و وضعیت اجرای کارهای غیرهمزمان
- Health check، readiness check و full health check برای استقرار
- لاگ‌گیری ساختاریافته و اتصال‌پذیری به Sentry در محیط تولید
- اسکریپت‌های پشتیبان‌گیری، بازیابی، استقرار و راه‌اندازی SSL

---

## فناوری‌های استفاده‌شده

| حوزه | فناوری‌ها |
| --- | --- |
| Backend | Python 3.12، Django 5.2 |
| Database | PostgreSQL |
| Cache / Queue | Redis، Celery |
| Web Server | Gunicorn، Nginx |
| Frontend | HTML، CSS، JavaScript |
| Payments | Zarinpal، Stripe |
| Messaging | Kavenegar، Console SMS Provider |
| Static / Media | Django staticfiles، WhiteNoise، Nginx static/media serving |
| Observability | Django logging، Sentry، health/readiness endpoints |
| Deployment | Docker، Docker Compose |
| Testing | pytest، Django test client |
| Environment | python-dotenv، `.env` based configuration |

---

## ساختار پروژه

کد اصلی پروژه در پوشه `apps` قرار دارد. هر اپلیکیشن مسئول یک بخش مشخص از دامنه کسب‌وکار یا زیرساخت سامانه است.

| اپلیکیشن | مسئولیت |
| --- | --- |
| `accounts` | پروفایل مشتری، آدرس‌ها، ورود/ثبت‌نام، حساب کاربری و سفارش‌های کاربر |
| `cart` | سبد خرید، اقلام سبد، محاسبه جمع، ادغام سبد و کنترل تغییرات سبد در جریان checkout |
| `careers` | فرم درخواست همکاری، موقعیت‌های شغلی، اعتبارسنجی رزومه و مدیریت درخواست‌های استخدام |
| `core` | صفحات عمومی، checkout، هدر/فوتر، SEO، health checks، داشبوردهای عملیاتی، context processors، برچسب‌های فارسی و ابزارهای مشترک |
| `delivery` | داده‌های legacy ارسال، وضعیت سفارش، لاگ تغییر وضعیت و سرویس‌های مربوط به checkout/fulfillment |
| `growth` | کوپن‌ها، معرف، پروموشن‌ها، رویدادهای رشد، سبد رهاشده، CLV و تحلیل درآمد |
| `intelligence` | متادیتای هوش محصول، خرید همزمان، آمار روزانه، پیش‌بینی تقاضا، توصیه پخت، پروفایل هوشمند مشتری و پیشنهاد فروش |
| `inventory` | موجودی محصول، ظرفیت تولید روزانه، رزرو موجودی، آزادسازی رزرو و کنترل موجودی قابل فروش |
| `loyalty` | حساب وفاداری، امتیاز مشتری، سطح‌بندی و تراکنش‌های امتیاز |
| `orders` | مدل سفارش، اقلام سفارش، وضعیت سفارش، شماره روزانه، ایجاد سفارش و checkout حضوری |
| `payments` | پرداخت‌ها، رویدادهای پرداخت، Providerها، callbackها و سرویس‌های دریافت/تأیید پرداخت |
| `products` | دسته‌بندی، محصول، قیمت، تصویر، وضعیت موجودی و مسیرهای فروشگاه |
| `wishlist` | علاقه‌مندی‌های کاربران و ارتباط کاربر با محصولات ذخیره‌شده |
| `notifications` | قالب‌های پیامک، لاگ پیامک، Providerها و ارسال/پیگیری پیام‌ها |

پوشه‌های مهم دیگر:

| مسیر | توضیح |
| --- | --- |
| `config` | تنظیمات Django، URLهای اصلی، ASGI/WSGI و Celery |
| `templates` | قالب‌های HTML عمومی، حساب کاربری، checkout، سفارش و ادمین سفارشی |
| `static` | CSS، JavaScript و دارایی‌های استاتیک |
| `docs` | مستندات راه‌اندازی، استقرار، observability، backup/restore و چک‌لیست‌ها |
| `deploy` | اسکریپت‌های deploy، backup، restore، healthcheck و SSL |
| `docker` | Dockerfile، تنظیمات Gunicorn، entrypoint و قالب‌های Nginx |
| `tests` | تست‌های واحد، integration، edge case، concurrency، load و مستندات تست |

---

## نصب و اجرا

### اجرای محلی با Virtualenv

پیش‌نیازها:

- Python 3.12
- PostgreSQL
- دسترسی به یک فایل `.env` معتبر

مراحل:

```bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements/dev.txt
```

یک فایل `.env` از روی نمونه بسازید و مقادیر لازم را تنظیم کنید:

```bash
cp .env.example .env
```

برای تولید مقدار محلی `SECRET_KEY`:

```bash
python - <<'PY'
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
PY
```

برای توسعه محلی، حداقل این موارد باید با محیط شما هماهنگ باشند:

```env
DJANGO_SETTINGS_MODULE=config.settings.dev
DEBUG=True
POSTGRES_DB=crumbs
POSTGRES_USER=crumbs
POSTGRES_PASSWORD=crumbs
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
SITE_URL=http://localhost:8000
SMS_PROVIDER=console
```

اجرای migrationها:

```bash
python manage.py migrate
```

در صورت نیاز، داده‌های پیش‌فرض فروشگاه و لایه هوشمندی را seed کنید:

```bash
python manage.py seed_iran_defaults
python manage.py seed_intelligence_defaults
```

اجرای سرور توسعه:

```bash
python manage.py runserver
```

آدرس‌های اصلی:

| بخش | مسیر |
| --- | --- |
| سایت | `http://localhost:8000/` |
| منو | `http://localhost:8000/shop/` |
| سبد خرید | `http://localhost:8000/cart/` |
| پنل مدیریت | `http://localhost:8000/admin/` |
| Health check | `http://localhost:8000/health/` |
| Readiness | `http://localhost:8000/ready/` |

### اجرای محلی با Docker Compose

فایل `docker-compose.yml` برای اجرای سرویس `web` و PostgreSQL در محیط محلی/آزمایشی وجود دارد.

```bash
cp .env.example .env
docker compose up --build
```

اجرای migration در کانتینر:

```bash
docker compose exec web python manage.py migrate
```

جمع‌آوری فایل‌های استاتیک در صورت نیاز:

```bash
docker compose exec web python manage.py collectstatic --noinput
```

### Docker Compose تولیدی

فایل `docker-compose.production.yml` برای استقرار VPS آماده شده و شامل سرویس‌های زیر است:

- `db` برای PostgreSQL
- `redis` برای cache/session و Celery broker
- `web` برای اجرای Django با Gunicorn
- `celery_worker`
- `celery_beat`
- `nginx`

فرمان‌های اصلی تولیدی از طریق اسکریپت‌های پوشه `deploy` اجرا می‌شوند.

---

## استقرار

مستندات استقرار در پوشه `docs` قرار دارد و باید قبل از اجرای تولیدی مطالعه شود.

| سند | مسیر |
| --- | --- |
| Launch Checklist | `docs/LAUNCH_CHECKLIST.md` |
| Launch Test Plan | `docs/LAUNCH_TEST_PLAN.md` |
| VPS Runbook | `docs/VPS_LAUNCH_RUNBOOK.md` |
| Backup / Restore | `docs/BACKUP_RESTORE.md` |
| Observability | `docs/OBSERVABILITY.md` |
| Migration Notes | `docs/MIGRATION_HISTORY_NOTES.md` |

اسکریپت‌های عملیاتی مهم:

| اسکریپت | کاربرد |
| --- | --- |
| `deploy/deploy.sh` | اجرای مراحل deploy، migration و collectstatic |
| `deploy/backup.sh` | پشتیبان‌گیری از دیتابیس و media |
| `deploy/restore.sh` | بازیابی دیتابیس و media |
| `deploy/healthcheck.sh` | بررسی سلامت سرویس |
| `deploy/init-ssl.sh` | راه‌اندازی SSL |
| `deploy/render-nginx.sh` | تولید تنظیمات Nginx |
| `deploy/server-bootstrap.sh` | آماده‌سازی اولیه سرور |

استقرار تولیدی باید با `.env` کامل، دامنه واقعی، تنظیمات HTTPS، تنظیمات پایگاه داده، Redis، SMS، پرداخت و مانیتورینگ انجام شود.

---

## تست

بررسی تنظیمات Django:

```bash
python manage.py check
```

اجرای کل تست‌ها:

```bash
pytest -q
```

وضعیت فعلی تست‌ها:

| وضعیت | تعداد |
| --- | ---: |
| Passed | 421 |
| Skipped | 4 |

---

## وضعیت پروژه

Production Ready

این وضعیت به این معناست که پروژه دارای تنظیمات تولیدی جداگانه، Dockerfile، Docker Compose تولیدی، Gunicorn، Nginx، health/readiness endpoints، لاگ‌گیری، پشتیبانی از Sentry، اسکریپت‌های backup/restore، چک‌لیست استقرار، تست‌های گسترده و مسیرهای عملیاتی برای سفارش، پرداخت، موجودی و مدیریت است.

Production Ready بودن به معنی حذف نیاز به تنظیمات محیطی نیست. پیش از اجرا روی سرور واقعی باید `.env`، دامنه، HTTPS، پرداخت، SMS، backup، مانیتورینگ و دسترسی‌های مدیریتی مطابق مستندات `docs` تکمیل و بررسی شوند.

---

## مستندات

مستندات فنی و عملیاتی پروژه در پوشه `docs` نگهداری می‌شود. برای راه‌اندازی، استقرار، بررسی سلامت، observability، backup/restore و برنامه تست انتشار، از این پوشه شروع کنید.

---

## نسخه

نسخه فعلی: `v1.0.2`

---

## توسعه‌دهنده

Amirhossein Nasimi
