# CHANGELOG

این سند تاریخچه تغییرات رسمی پروژه Crumbs را نگهداری می‌کند.

فرمت این فایل بر اساس Keep a Changelog است.

شماره نسخه‌ها از Semantic Versioning پیروی می‌کنند.

---

## [Unreleased]

### Notes

- تغییرات پس از `v2.0.1` در این بخش ثبت می‌شوند.

---

## [v2.0.1]

| مورد | مقدار |
| --- | --- |
| Status | Patch release |
| Release Type | UI / content / documentation |
| Git Tag | `v2.0.1` |
| Tag Date | ۱۸ ژوئیه ۲۰۲۶ |

### Summary

هم‌تراز کردن اطلاعات تماس و شبکه‌های اجتماعی در فوتر، صفحه تماس و منوی موبایل؛ به‌روزرسانی حساب اینستاگرام و ساعات کاری؛ بهبود واژه‌گزینی فارسی؛ همگام‌سازی مستندات با وضعیت واقعی repository و استقرار تولید.

### Changed

- حساب اینستاگرام به `@crumbs.tehran` (`https://instagram.com/crumbs.tehran`) به‌روزرسانی شد.
- فوتر: یک لینک اجتماعی با آیکن اینستاگرام و نام کاربری (بدون برچسب متنی تکراری).
- صفحه تماس: نمایش متنی `@crumbs.tehran` و ساعات کاری هم‌تراز با فوتر/drawer.
- ساعات کاری در UI فارسی: «هر روز» و «۸:۰۰ صبح تا ۱۰:۳۰ شب»؛ structured data با `opens: 08:00` و `closes: 22:30`.
- واژه‌گزینی فارسی: «بیکری» به‌جای «نانوایی» در صفحات مرتبط.
- README، CHANGELOG و اسناد استقرار با نسخه `v2.0.1` و مسیر تولید `/opt/crumbs` همگام شدند.

### Documentation

- `README.md` برای `v2.0.1`، بخش Latest Release، ساختار پروژه، استقرار و تعداد تست‌ها به‌روز شد.
- `DEPLOYMENT.md` و `INSTALL.md` به‌عنوان نقاط ورود سریع اضافه شدند.
- نسخه‌های اسناد در `docs/` به `v2.0.1` به‌روز شدند.

### Testing

| مورد | وضعیت |
| --- | --- |
| `python manage.py check` | بدون خطا |
| `pytest -q` | `422 passed, 4 skipped` |

---

## [v2.0.0]

| مورد | مقدار |
| --- | --- |
| Status | Minor / production hardening |
| Release Type | UI + infrastructure |
| Reference Commit | `ae11f1f` (Release v2.0.0 - Production deployment) |

### Summary

آماده‌سازی استقرار تولید با بهبود سرو static در Nginx، ساده‌سازی hero صفحه اصلی، اصلاح نمایش لوگو، و بهبود UX سبد در موبایل همراه با reload مطمئن Nginx پس از recreate سرویس `web`.

### Added

- لینک «سبد خرید» در منوی کشویی (drawer) موبایل، با مسیر موجود `core:cart`.
- نمایش badge تعداد اقلام سبد در drawer موبایل فقط زمانی که سبد حداقل یک قلم دارد.

### Changed

- بخش hero صفحه اصلی به پس‌زمینه برند بدون رسانهٔ جاسازی‌شده ساده‌سازی شد.
- لوگو هدر برای نمایش پایدارتر (از جمله Safari) تنظیم شد.
- `./deploy/deploy.sh update` پس از force-recreate سرویس `web`، Nginx را reload می‌کند تا آدرس upstream تازه‌سازی شود؛ سپس health check اجرا می‌شود.
- کش/سرو فایل‌های static در Nginx برای فایل‌های بدون hash تنظیم شد تا به‌روزرسانی دارایی‌ها قابل اتکاتر باشد.

### Fixed

- پس از `deploy.sh update`، احتمال `502 Bad Gateway` ناشی از کش شدن IP قدیمی `web` در Nginx برطرف شد (بدون تغییر منطق اپلیکیشن).

### Notes

- این نسخه در تاریخچه Git با commit `ae11f1f` ثبت شده است؛ tag رسمی بعدی `v2.0.1` است.

---

## [v1.0.2]

| مورد | مقدار |
| --- | --- |
| Status | Initial documented release |
| Release Type | Patch / Documentation Baseline |
| Git Tag | `v1.0.2` |
| Tag Date | ۱۴ ژوئیه ۲۰۲۶ |
| Reference Commit | `1be87208513dfadbc961ad68c349ca6d4a5c480a` |

### Summary

`v1.0.2` نسخه مستندشده فعلی پروژه Crumbs است. این نسخه به عنوان نخستین release رسمی با مستندات کامل ثبت می‌شود و وضعیت فعلی سامانه، زیرساخت، تست‌ها و اسناد تحویل را یکپارچه می‌کند.

### Added

- لینک سبد خرید در header دسکتاپ، مطابق commit ثبت‌شده برای tag `v1.0.2`.
- جریان سفارش‌گیری برای تحویل از کانتر با پشتیبانی از پرداخت آنلاین و پرداخت حضوری.
- سبد خرید با افزودن، حذف، تغییر تعداد و نمایش تعداد اقلام در header.
- رزرو موجودی برای سبد خرید و سفارش.
- شماره روزانه سفارش برای عملیات کافه.
- پنل مدیریت Django با برچسب‌ها، فیلترها و actionهای فارسی.
- داشبوردهای عملیاتی برای kitchen، pickup، order lookup و shift summary.
- سیستم پرداخت با providerهای Zarinpal، Stripe، cash و counter card در لایه backend.
- قالب‌ها و لاگ‌های SMS با providerهای console و Kavenegar.
- قابلیت‌های رشد شامل coupon، referral، promotion، abandoned cart و revenue analytics.
- سیستم وفاداری شامل حساب امتیاز، tier و تراکنش امتیاز.
- لایه intelligence شامل آمار روزانه محصول، forecast، توصیه پخت، upsell و profile تحلیلی مشتری.
- health، readiness و full health endpointها برای عملیات و استقرار.

### Changed

- معماری checkout فعلی حول پرداخت آنلاین و پرداخت حضوری برای تحویل از کانتر مستند و تثبیت شده است.
- terminology عمومی پروژه روی «پرداخت حضوری»، «تحویل از کانتر»، «سبد خرید»، «پنل مدیریت» و «آمادگی تولید» یکدست شده است.
- مستندات رسمی پروژه برای خوانایی بهتر فارسی و ترکیب Persian/English بازبینی شده‌اند.
- ساختار مستندات پروژه به مجموعه‌ای قابل تحویل برای تیم فنی، مدیر سایت، توسعه‌دهنده و QA تبدیل شده است.

### Fixed

- مورد مستقل قابل انتساب به `v1.0.2` برای این بخش در changelog اولیه ثبت نشده است.

### Documentation

- README اصلی پروژه تکمیل شده است: `README.md`.
- معرفی پروژه تکمیل شده است: `docs/01-معرفی-پروژه.md`.
- کاتالوگ امکانات تکمیل شده است: `docs/02-امکانات-پروژه.md`.
- معماری سیستم تکمیل شده است: `docs/03-معماری-سیستم.md`.
- راهنمای مدیر سایت تکمیل شده است: `docs/04-راهنمای-مدیر-سایت.md`.
- راهنمای استقرار تکمیل شده است: `docs/06-راهنمای-استقرار.md`.
- راهنمای توسعه تکمیل شده است: `docs/07-راهنمای-توسعه.md`.
- مستندات Database تکمیل شده است: `docs/08-مستندات-Database.md`.
- مستندات API تکمیل شده است: `docs/09-مستندات-API.md`.
- راهنمای تست تکمیل شده است: `docs/10-راهنمای-تست.md`.
- اسناد عملیاتی موجود مانند backup، observability، launch checklist و runbookها به عنوان منابع تکمیلی حفظ شده‌اند.

### Infrastructure

- Dockerfile پروژه در `docker/Dockerfile` وجود دارد.
- Docker Compose توسعه در `docker-compose.yml` وجود دارد.
- Docker Compose تولید در `docker-compose.production.yml` وجود دارد.
- Gunicorn configuration در `docker/gunicorn.conf.py` وجود دارد.
- Nginx configuration و templateها در `docker/nginx` وجود دارند.
- PostgreSQL به عنوان database اصلی در stack تولید تعریف شده است.
- Redis برای cache و Celery broker/backend در stack تولید تعریف شده است.
- Celery worker و Celery beat در `docker-compose.production.yml` تعریف شده‌اند.
- health checkهای `/health/`، `/ready/` و `/health/full/` پیاده‌سازی شده‌اند.
- اسکریپت‌های deployment، backup، restore، healthcheck، SSL و bootstrap در `deploy` وجود دارند.

### Testing

| مورد | وضعیت |
| --- | --- |
| دستور سلامت Django | `python manage.py check` |
| دستور اصلی تست | `pytest -q` |
| وضعیت شناخته‌شده مستندشده | `421 passed, 4 skipped` |
| تنظیمات pytest | `pytest.ini` با `config.settings.test` |
| تست‌های سریع | SQLite in-memory در حالت پیش‌فرض |
| تست‌های همزمانی | وابسته به PostgreSQL و `CRUMBS_TEST_POSTGRES=1` |
| ابزار coverage | pytest-cov در `requirements/test.txt` |

### Notes

- این نسخه نخستین release با changelog رسمی و مستندات کامل پروژه است.
- جزئیات نسخه‌های قبلی در این فایل بازسازی نشده‌اند تا release یا تغییر ساختگی ثبت نشود.
- `v1.0.2` یک Git tag تأییدشده در repository است.

---

## سیاست شماره‌گذاری نسخه‌های آینده

| نوع نسخه | کاربرد |
| --- | --- |
| Major | تغییر ناسازگار در رفتار عمومی، schema، API، deployment contract یا flowهای اصلی کسب‌وکار |
| Minor | افزودن قابلیت جدید سازگار با نسخه فعلی |
| Patch | رفع باگ، بهبود مستندات، اصلاح UI کوچک، بهبود تست یا تغییر سازگار بدون شکستن contract |

نسخه‌های آینده باید فقط زمانی در این فایل ثبت شوند که تغییرات آن‌ها در repository قابل تأیید باشد.
