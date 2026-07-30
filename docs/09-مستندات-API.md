# مستندات API

| مورد | مقدار |
| --- | --- |
| Project | Crumbs |
| Version | `v2.0.1` |
| Author | Amirhossein Nasimi |
| Last Update | ۱۵ ژوئیه ۲۰۲۶ |
| Audience | توسعه‌دهنده Backend، مدیر فنی، تیم نگهداری و شرکت تحویل‌گیرنده |
| Status | مستند رسمی مسیرهای HTTP، Viewها و Endpointهای سیستمی |

## فهرست مطالب

- [1- مقدمه](#1--مقدمه)
- [2- معماری ارتباط HTTP](#2--معماری-ارتباط-http)
- [3- ساختار URLها](#3--ساختار-urlها)
- [4- صفحات عمومی](#4--صفحات-عمومی)
- [5- Endpointهای Checkout](#5--endpointهای-checkout)
- [6- Endpointهای پرداخت](#6--endpointهای-پرداخت)
- [7- Endpointهای مدیریتی](#7--endpointهای-مدیریتی)
- [8- Health Endpoints](#8--health-endpoints)
- [9- Authentication](#9--authentication)
- [10- فرم‌های اصلی](#10--فرمهای-اصلی)
- [11- Services used by Views](#11--services-used-by-views)
- [12- Request lifecycle](#12--request-lifecycle)
- [13- Error handling](#13--error-handling)
- [14- Security](#14--security)
- [15- Best Practices](#15--best-practices)
- [16- Common mistakes](#16--common-mistakes)
- [17- FAQ](#17--faq)
- [18- جمع‌بندی](#18--جمعبندی)
- [19- اطلاعات پایانی سند](#19--اطلاعات-پایانی-سند)

# 1- مقدمه

این سند مسیرهای HTTP، viewهای Django، فرم‌ها، endpointهای سیستمی و جریان‌های اصلی request در پروژه Crumbs را توضیح می‌دهد. هدف سند، ایجاد تصویر دقیق از API واقعی پروژه است؛ نه طراحی API جدید و نه معرفی REST endpointهایی که در repository وجود ندارند.

Crumbs در وضعیت فعلی یک برنامه عمدتاً server-rendered است. مرورگر بیشتر درخواست‌ها را به viewهای Django ارسال می‌کند، viewها داده را از فرم‌ها و serviceها دریافت می‌کنند و پاسخ معمولاً صفحه HTML، redirect یا در چند مورد مشخص JSON است.

## 1-1- تعریف API در پروژه Crumbs

در این سند، API به معنی سطح ارتباط HTTP پروژه است:

| نوع API | توضیح |
| --- | --- |
| صفحات server-rendered | مسیرهایی که HTML render می‌کنند؛ مانند صفحه فروشگاه، سبد خرید، checkout و حساب کاربری |
| Form endpoints | مسیرهایی که با `POST` فرم دریافت می‌کنند و معمولاً redirect یا پیام validation برمی‌گردانند |
| System endpoints | مسیرهای health، readiness و payment callback |
| Admin endpoints | مسیرهای Django Admin و صفحه‌های عملیاتی staff |
| Provider callbacks | مسیرهایی که provider پرداخت به آن‌ها callback یا webhook ارسال می‌کند |

## 1-2- تفاوت صفحات و Endpointهای سیستمی

| گروه | خروجی معمول | نمونه |
| --- | --- | --- |
| صفحه عمومی | HTML | `/shop/`، `/cart/` |
| فرم عمومی | redirect همراه message | `/checkout/`، `/contact/` |
| پرداخت | JSON یا redirect داخلی provider flow | `/payments/zarinpal/callback/` |
| Health | JSON | `/health/`، `/ready/` |
| Admin | HTML داخل پنل مدیریت | `/admin/kitchen/` |

# 2- معماری ارتباط HTTP

معماری ارتباط HTTP در Crumbs بر اساس requestهای کلاسیک وب طراحی شده است. مرورگر صفحه HTML دریافت می‌کند، فرم ارسال می‌کند و Django با view، form، service و database پاسخ مناسب تولید می‌کند.

```text
Browser
  |
  v
Nginx
  |
  v
Gunicorn
  |
  v
Django URL Resolver
  |
  v
View
  |
  +--> Form Validation
  |
  +--> Service Layer
  |       |
  |       v
  |     Database
  |
  v
Template / Redirect / JSON
  |
  v
Browser
```

## 2-1- مسئولیت هر لایه

| لایه | مسئولیت |
| --- | --- |
| Browser | ارسال request، دریافت HTML، ارسال فرم و نگهداری session cookie |
| Nginx | reverse proxy، TLS، static و media در محیط تولید |
| Gunicorn | اجرای processهای Django در تولید |
| Django URL Resolver | نگاشت route به view |
| Views | دریافت request، اجرای form، فراخوانی service و تعیین response |
| Templates | تولید HTML برای صفحات server-rendered |
| Forms | validation ورودی کاربر و تبدیل داده فرم |
| Services | اجرای منطق دامنه، transaction، پرداخت، سفارش و موجودی |

# 3- ساختار URLها

فایل اصلی URL پروژه `config/urls.py` است. این فایل health endpoints، Django Admin، SEO endpoints و namespaceهای appها را ثبت می‌کند.

## 3-1- فایل‌های URL اصلی

| فایل | مسئولیت |
| --- | --- |
| `config/urls.py` | مسیرهای root، health، admin، sitemap و include کردن appها |
| `apps/core/urls.py` | صفحات عمومی، cart، checkout و رسید سفارش |
| `apps/products/urls.py` | فروشگاه، دسته‌بندی و جزئیات محصول |
| `apps/accounts/urls.py` | ثبت‌نام، ورود، پروفایل، سفارش‌ها و آدرس‌ها |
| `apps/payments/urls.py` | webhook و callback پرداخت |
| `apps/careers/urls.py` | فرم همکاری |
| `apps/wishlist/urls.py` | لیست و عملیات علاقه‌مندی |
| `apps/core/admin_urls.py` | مسیرهای عملیاتی داخل admin |
| `apps/growth/admin_urls.py` | داشبورد analytics و growth داخل admin |
| `apps/intelligence/admin_urls.py` | داشبورد intelligence داخل admin |

## 3-2- ساختار Routing

| Prefix | Namespace | توضیح |
| --- | --- | --- |
| `/` | `core` | خانه، درباره، تماس، cart، checkout و رسید |
| `/shop/` | `products` | کاتالوگ و جزئیات محصول |
| `/payments/` | `payments` | callback و webhook پرداخت |
| `/accounts/` | `accounts` | حساب کاربری و آدرس‌ها |
| `/careers/` | `careers` | درخواست همکاری |
| `/wishlist/` | `wishlist` | علاقه‌مندی‌های کاربر |
| `/admin/` | Django Admin | پنل مدیریت و مسیرهای staff |

## 3-3- نکته مهم درباره REST API

در repository فعلی، REST API عمومی مبتنی بر Django REST Framework یا endpointهای JSON عمومی برای محصولات، سفارش‌ها یا کاربران وجود ندارد. مسیرهای عمومی اصلی server-rendered هستند و نباید به عنوان APIهای JSON مستند شوند.

# 4- صفحات عمومی

این بخش مسیرهای عمومی و account-facing موجود را مستند می‌کند. بسیاری از این مسیرها هم `GET` و هم `POST` را در یک view مدیریت می‌کنند.

## 4-1- صفحات Core

| Route | Method | View | نیاز به ورود | نتیجه |
| --- | --- | --- | --- | --- |
| `/` | `GET`، `POST` | `home` | خیر | نمایش خانه؛ `POST` فقط برای فرم newsletter |
| `/about/` | `GET` | `about` | خیر | نمایش صفحه درباره ما |
| `/contact/` | `GET`، `POST` | `contact` | خیر | نمایش فرم تماس یا ثبت پیام و redirect |
| `/cart/` | `GET`، `POST` | `cart_view` | خیر | نمایش سبد؛ `POST` برای update یا remove |
| `/cart/add/` | `POST` | `add_to_cart` | خیر | افزودن محصول به سبد و redirect به مقصد بعدی |
| `/checkout/` | `GET`، `POST` | `checkout` | خیر | نمایش یا پردازش checkout |
| `/checkout/confirmation/ORDER_NUMBER/` | `GET` | `order_confirmation` | مشروط | نمایش تأیید سفارش برای مالک، staff یا session مجاز |
| `/orders/ORDER_NUMBER/receipt/` | `GET` | `order_receipt` | مشروط | نمایش رسید برای مالک، staff یا session مجاز |
| `/checkout/redirect/` | `GET` | `checkout_redirect_info` | خیر | نمایش صفحه redirect پرداخت بدون URL فعال |

## 4-2- صفحات فروشگاه

| Route | Method | View | نیاز به ورود | نتیجه |
| --- | --- | --- | --- | --- |
| `/shop/` | `GET` | `product_list` | خیر | نمایش محصولات فعال |
| `/shop/CATEGORY_SLUG/` | `GET` | `product_list` | خیر | نمایش محصولات یک دسته |
| `/shop/CATEGORY_SLUG/PRODUCT_SLUG/` | `GET` | `product_detail` | خیر | نمایش جزئیات محصول و پیشنهادهای مرتبط |

## 4-3- حساب کاربری

| Route | Method | View | نیاز به ورود | نتیجه |
| --- | --- | --- | --- | --- |
| `/accounts/register/` | `GET`، `POST` | `register` | خیر | ثبت‌نام و login خودکار پس از موفقیت |
| `/accounts/login/` | `GET`، `POST` | `login_view` | خیر | ورود session-based و merge شدن cart مهمان |
| `/accounts/logout/` | `POST` | `logout_view` | بله | خروج از حساب و redirect به خانه |
| `/accounts/profile/` | `GET`، `POST` | `profile` | بله | نمایش و ویرایش پروفایل |
| `/accounts/orders/` | `GET` | `order_list` | بله | فهرست سفارش‌های کاربر |
| `/accounts/orders/ORDER_NUMBER/` | `GET` | `order_detail` | مشروط | نمایش جزئیات سفارش برای مالک، staff یا session مجاز |
| `/accounts/addresses/` | `GET` | `address_list` | بله | نمایش آدرس‌های کاربر |
| `/accounts/addresses/add/` | `GET`، `POST` | `address_create` | بله | افزودن آدرس |
| `/accounts/addresses/ADDRESS_ID/edit/` | `GET`، `POST` | `address_edit` | بله | ویرایش آدرس متعلق به کاربر |
| `/accounts/addresses/ADDRESS_ID/delete/` | `POST` | `address_delete` | بله | حذف آدرس متعلق به کاربر |
| `/accounts/addresses/ADDRESS_ID/default/` | `POST` | `address_set_default` | بله | تنظیم آدرس پیش‌فرض |

## 4-4- علاقه‌مندی و همکاری

| Route | Method | View | نیاز به ورود | نتیجه |
| --- | --- | --- | --- | --- |
| `/wishlist/` | `GET` | `wishlist_view` | بله | نمایش محصولات علاقه‌مندی |
| `/wishlist/add/` | `POST` | `wishlist_add` | بله | افزودن product به wishlist و redirect |
| `/wishlist/remove/` | `POST` | `wishlist_remove` | بله | حذف product از wishlist و redirect |
| `/careers/` | `GET`، `POST` | `careers` | خیر | نمایش یا ثبت فرم همکاری |

## 4-5- SEO و فایل‌های عمومی سیستمی

| Route | Method | View | نتیجه |
| --- | --- | --- | --- |
| `/robots.txt` | `GET` | `robots_txt` | پاسخ متنی robots |
| `/sitemap.xml` | `GET` | Django sitemap view | sitemap محصولات، دسته‌ها و صفحات ثابت |

# 5- Endpointهای Checkout

Checkout در Crumbs یک جریان server-rendered است. مسیر اصلی آن `/checkout/` است و payload JSON عمومی ندارد. داده‌ها از `CheckoutForm` خوانده می‌شوند، سپس view بر اساس روش پرداخت، service مناسب را اجرا می‌کند.

## 5-1- مسیر اصلی Checkout

| Route | Method | View | فرم | خروجی |
| --- | --- | --- | --- | --- |
| `/checkout/` | `GET` | `checkout` | `CheckoutForm` با initial data | نمایش صفحه checkout |
| `/checkout/` | `POST` | `checkout` | `CheckoutForm` | ایجاد سفارش، شروع پرداخت یا redirect به تأیید سفارش |

## 5-2- اعتبارسنجی Checkout

| مورد | رفتار واقعی |
| --- | --- |
| سبد خالی | پیام warning و redirect به `/cart/` |
| نام | در `CheckoutForm` الزامی است. |
| تلفن | در `CheckoutForm` الزامی است. |
| ایمیل | اختیاری است؛ در نبود آن مقدار guest محلی ساخته می‌شود. |
| یادداشت pickup | در `pickup_note` خوانده و در notes سفارش ذخیره می‌شود. |
| روش پرداخت | گزینه‌های فرم فعلی `online` و `cash` هستند. |

## 5-3- جریان پرداخت آنلاین

```text
POST /checkout/
  |
  v
CheckoutForm.is_valid
  |
  v
process_checkout
  |
  v
create_order_from_cart
  |
  v
finalize_checkout_stock
  |
  v
PaymentService.initiate_online
  |
  v
checkout_redirect.html
```

| مرحله | توضیح |
| --- | --- |
| service اصلی | `DeliveryServiceCheckout.process_checkout` |
| payment service | `PaymentService.initiate_online` |
| provider | بر اساس `DEFAULT_PAYMENT_PROVIDER` انتخاب می‌شود. |
| نتیجه موفق | نمایش صفحه redirect پرداخت با `checkout_url` |
| خطای پرداخت | پاک‌سازی checkout شکست‌خورده، آزادسازی stock و نمایش پیام خطا |

## 5-4- جریان پرداخت حضوری

```text
POST /checkout/
  |
  v
CheckoutForm.is_valid
  |
  v
process_counter_checkout
  |
  v
Order status: awaiting_payment
  |
  v
Payment provider: cash
  |
  v
Order detail or confirmation page
```

| مرحله | توضیح |
| --- | --- |
| service اصلی | `CounterCheckoutService.process_checkout` |
| وضعیت اولیه سفارش | `awaiting_payment` |
| وضعیت پرداخت اولیه | `pending_payment` |
| provider پرداخت | `cash` برای پرداخت حضوری عمومی فعلی |
| نتیجه کاربر واردشده | redirect به `/accounts/orders/ORDER_NUMBER/` |
| نتیجه کاربر مهمان | redirect به `/checkout/confirmation/ORDER_NUMBER/` |

## 5-5- مسیرهای مرتبط با تأیید و رسید

| Route | Method | دسترسی |
| --- | --- | --- |
| `/checkout/confirmation/ORDER_NUMBER/` | `GET` | staff، مالک سفارش یا session دارای access |
| `/orders/ORDER_NUMBER/receipt/` | `GET` | staff، مالک سفارش یا session دارای access |
| `/accounts/orders/ORDER_NUMBER/` | `GET` | staff، مالک سفارش یا session دارای access |

# 6- Endpointهای پرداخت

پرداخت‌ها در app `payments` قرار دارند. این بخش فقط مسیرهای واقعی موجود را توضیح می‌دهد.

## 6-1- مسیرهای پرداخت

| Route | Method | View | دسترسی | خروجی |
| --- | --- | --- | --- | --- |
| `/payments/zarinpal/callback/` | `GET` | `zarinpal_callback` | callback provider | JSON |
| `/payments/webhooks/stripe/` | `POST` | `stripe_webhook` | webhook provider | HTTP status |
| `/payments/orders/ORDER_NUMBER/checkout/` | `POST` | `create_checkout_session` | staff | JSON |

## 6-2- Zarinpal callback

| مورد | رفتار واقعی |
| --- | --- |
| Method | `GET` |
| queryهای خوانده‌شده | `Authority` یا `authority`، `Status` یا `status` |
| payment lookup | بر اساس `provider_checkout_session_id` |
| handler | `handle_zarinpal_callback` |
| موفقیت | JSON شامل `status`، `processed` و `event_id` |
| خطای authority | JSON با status `400` |
| خطای configuration | JSON با status `503` |
| خطای processing | JSON با status `500` |

## 6-3- Stripe webhook

| مورد | رفتار واقعی |
| --- | --- |
| Method | `POST` |
| CSRF | با `csrf_exempt` مستثنی شده است. |
| signature | از header `HTTP_STRIPE_SIGNATURE` خوانده می‌شود. |
| handler | `handle_stripe_webhook` |
| موفقیت | status `200` بدون body مهم |
| signature نامعتبر | status `400` |
| configuration ناقص | status `503` |
| خطای processing | status `500` |

## 6-4- Create checkout session برای staff

مسیر `/payments/orders/ORDER_NUMBER/checkout/` با `POST` و `staff_member_required` محافظت شده است. این endpoint برای جریان admin یا testing طراحی شده و سفارش را با `initiate_payment` وارد جریان checkout provider می‌کند.

| حالت | خروجی |
| --- | --- |
| سفارش پیدا نشود | JSON با status `404` |
| خطای پرداخت | JSON با status `400` |
| configuration ناقص | JSON با status `503` |
| موفقیت | JSON شامل `order_number`، `payment_id`، `checkout_url` و `status` |

## 6-5- پرداخت حضوری در پنل

پرداخت حضوری از checkout عمومی با method داخلی `cash` ساخته می‌شود. دریافت وجه و نهایی‌سازی آن از طریق actionهای admin و serviceهای `PaymentService.mark_counter_cash_received` یا مسیرهای عملیاتی انجام می‌شود، نه از طریق یک endpoint عمومی مستقل.

# 7- Endpointهای مدیریتی

مسیرهای مدیریتی زیر روی `/admin/` ثبت شده‌اند و با Django Admin session و staff permission محافظت می‌شوند. این مسیرها API عمومی نیستند.

## 7-1- مسیرهای عملیات

| Route | Method | View | هدف |
| --- | --- | --- | --- |
| `/admin/operations/` | `GET` | `operations_dashboard` | داشبورد وضعیت عملیاتی، سفارش‌های جدید، payment issue، low stock و taskهای ناموفق |
| `/admin/ops/` | `GET` | `ops_dashboard` | داشبورد عملیاتی گسترده‌تر برای موجودی، سفارش‌ها و تنظیمات پرداخت |
| `/admin/kitchen/` | `GET` | `kitchen_queue` | صف آشپزخانه و وضعیت آماده‌سازی |
| `/admin/kitchen/action/` | `POST` | `kitchen_action` | تغییر وضعیت سفارش در آشپزخانه |
| `/admin/pickup-screen/` | `GET` | `pickup_screen` | سفارش‌های آماده تحویل |
| `/admin/pickup-screen/action/` | `POST` | `pickup_action` | ثبت تحویل سفارش |
| `/admin/order-lookup/` | `GET` | `order_lookup` | جست‌وجوی سریع سفارش |
| `/admin/shift-summary/` | `GET` | `shift_summary` | خلاصه شیفت روزانه |

## 7-2- مسیرهای Analytics و Intelligence

| Route | Method | View | هدف |
| --- | --- | --- | --- |
| `/admin/analytics/` | `GET` | `analytics_dashboard` | snapshot تحلیلی رشد با پارامتر `days` |
| `/admin/growth/` | `GET` | `growth_control_panel` | نمای رشد و attribution با پارامتر `days` |
| `/admin/intelligence/` | `GET` | `intelligence_dashboard` | forecast، توصیه پخت، low stock و insightهای intelligence |

## 7-3- Actionهای Kitchen

| action | رفتار |
| --- | --- |
| `start_preparing` | سفارش را از `paid` یا `confirmed_by_shop` به آماده‌سازی هدایت می‌کند. |
| `mark_ready` | سفارش را به `packaged` منتقل می‌کند. |
| `mark_completed` | سفارش pickup را کامل می‌کند. |

## 7-4- Actionهای Pickup

| action | رفتار |
| --- | --- |
| `mark_picked_up` | سفارش `packaged` را با service تکمیل pickup به وضعیت تحویل‌شده منتقل می‌کند. |

## 7-5- Order lookup

`/admin/order-lookup/` پارامتر query به نام `q` را می‌خواند. جست‌وجو روی `order_number`، `phone`، `first_name`، `last_name`، `notes` و در صورت عددی بودن عبارت روی `daily_sequence` انجام می‌شود.

# 8- Health Endpoints

Health endpoints در `config/urls.py` ثبت شده‌اند و خروجی JSON دارند.

## 8-1- فهرست Health endpoints

| Route | Method | View | هدف |
| --- | --- | --- | --- |
| `/health/` | `GET` | `health_check` | liveness probe |
| `/ready/` | `GET` | `readiness_check` | readiness probe برای وابستگی‌ها |
| `/health/full/` | `GET` | `health_full` | diagnostic گسترده، محدود به تنظیمات |

## 8-2- `/health/`

این endpoint فقط زنده بودن process Django را بررسی می‌کند.

```json
{
  "status": "ok",
  "service": "crumbs",
  "type": "liveness"
}
```

## 8-3- `/ready/`

این endpoint database، Redis، Celery broker و migrationها را بررسی می‌کند. اگر آماده باشد status HTTP برابر `200` است و در غیر این صورت `503` برمی‌گرداند.

| فیلد | معنی |
| --- | --- |
| `status` | `ready` یا `not_ready` |
| `ready` | مقدار boolean |
| `checks.database` | وضعیت اتصال database |
| `checks.redis` | وضعیت Redis یا `skipped` |
| `checks.celery_broker` | وضعیت broker یا `skipped` |
| `checks.migrations` | `ok`، `pending` یا `error` |

## 8-4- `/health/full/`

در حالت DEBUG فعال است. در production فقط وقتی فعال می‌شود که `HEALTH_FULL_ENABLED` مقدار فعال داشته باشد. در غیر این صورت JSON با status `404` برمی‌گرداند.

# 9- Authentication

احراز هویت پروژه بر اساس sessionهای Django انجام می‌شود. مسیرهای عمومی بدون login قابل مشاهده‌اند، اما صفحات account، wishlist و admin به authentication وابسته‌اند.

## 9-1- مسیرهای ورود و خروج

| Route | Method | رفتار |
| --- | --- | --- |
| `/accounts/login/` | `GET`، `POST` | نمایش و پردازش `LoginForm` |
| `/accounts/logout/` | `POST` | خروج از session |
| `/accounts/register/` | `GET`، `POST` | ایجاد user و login خودکار |

## 9-2- سطح دسترسی‌ها

| نوع مسیر | محافظت |
| --- | --- |
| public pages | بدون login |
| profile و addresses | `login_required` |
| wishlist | `login_required` |
| account orders | مالک سفارش، staff یا session مجاز checkout |
| custom admin pages | `staff_member_required` و `admin.site.admin_view` |
| Django Admin | authentication و permission داخلی Django Admin |

## 9-3- Session access برای سفارش مهمان

برای سفارش مهمان، `grant_checkout_order_access` شماره سفارش را در session نگهداری می‌کند. سپس `can_view_checkout_order` اجازه نمایش confirmation یا receipt را فقط برای همان session، مالک سفارش یا staff می‌دهد.

# 10- فرم‌های اصلی

فرم‌ها نقطه اصلی validation ورودی کاربر هستند. repository فعلی فرم‌های زیر را دارد.

## 10-1- فرم‌های عمومی

| Form | محل | کاربرد |
| --- | --- | --- |
| `CheckoutForm` | `apps/core/forms.py` | دریافت نام، تلفن، ایمیل اختیاری، یادداشت pickup و روش پرداخت |
| `ContactForm` | `apps/core/forms.py` | فرم تماس |
| `NewsletterForm` | `apps/core/forms.py` | ثبت ایمیل newsletter در صفحه خانه |
| `CareerApplicationForm` | `apps/careers/forms.py` | ثبت درخواست همکاری و رزومه PDF |

## 10-2- فرم‌های حساب کاربری

| Form | کاربرد |
| --- | --- |
| `RegisterForm` | ثبت user با username، email، نام، نام خانوادگی و رمز |
| `LoginForm` | ورود با identifier که توسط `resolve_login_identifier` پردازش می‌شود |
| `ProfileForm` | ویرایش اطلاعات user و `CustomerProfile` |
| `AddressForm` | ایجاد و ویرایش `Address` |

## 10-3- Validationهای شاخص

| Form | Validation |
| --- | --- |
| `CheckoutForm` | الزام تلفن و نام، trim کردن داده‌ها، ساخت email مهمان در صورت نبود ایمیل |
| `CareerApplicationForm` | الزام فیلدهای اصلی، محدودیت سن، پاسخ‌های HR، فایل PDF و magic header PDF |
| `LoginForm` | تبدیل identifier ورود با `resolve_login_identifier` |
| `AddressForm` | محدود شدن عملیات view به آدرس متعلق به user |

# 11- Services used by Views

Viewها در مسیرهای حساس نباید مستقیم چند model را تغییر دهند. منطق مهم در serviceها قرار دارد.

## 11-1- سرویس‌های checkout و سفارش

| Service | استفاده در view | نقش |
| --- | --- | --- |
| `DeliveryServiceCheckout.process_checkout` | `/checkout/` آنلاین | ساخت سفارش، stock finalization و شروع پرداخت آنلاین |
| `CounterCheckoutService.process_checkout` | `/checkout/` پرداخت حضوری | ساخت سفارش حضوری با وضعیت `awaiting_payment` |
| `OrderService` | kitchen، pickup، payment | transition وضعیت، confirm stock، finalize payment و cancellation |
| `create_order_from_cart` | checkout service | ساخت `Order` و `OrderItem` از cart |

## 11-2- سرویس‌های پرداخت

| Service | نقش |
| --- | --- |
| `PaymentService.initiate_online` | ایجاد payment آنلاین و دریافت checkout URL |
| `PaymentService.initiate_counter_payment` | ایجاد payment حضوری |
| `PaymentService.mark_counter_cash_received` | نهایی کردن دریافت وجه نقد |
| `PaymentService.mark_counter_card_received` | نهایی کردن دریافت کارت در کانتر |
| `handle_zarinpal_callback` | پردازش callback Zarinpal |
| `handle_stripe_webhook` | پردازش webhook Stripe |

## 11-3- سرویس‌های cart، inventory و پیشنهادها

| Service | نقش |
| --- | --- |
| `get_or_create_cart` | ساخت یا دریافت cart کاربر یا session |
| `add_item` | افزودن محصول و رزرو موجودی cart |
| `set_item_quantity` | تغییر تعداد و به‌روزرسانی reservation |
| `remove_item` | حذف product و آزادسازی reservation |
| `StockService` | facade موجودی برای cart و order |
| `RecommendationService` | پیشنهاد در خانه و جزئیات محصول |
| `UpsellService` | پیشنهادهای cart، checkout و ثبت impression |
| `ConversionService` | ثبت eventهای growth |

## 11-4- سرویس‌های admin و تحلیل

| Service | نقش |
| --- | --- |
| `build_shift_summary` | ساخت خلاصه شیفت |
| `get_analytics_snapshot` | داده dashboard analytics |
| `get_growth_dashboard_snapshot` | داده growth control panel |
| `InsightsService` | payload داشبورد intelligence |
| `InventoryOptimizationService` | هشدار low stock و overstock |
| `DemandForecastService` | الگوهای forecast |

# 12- Request lifecycle

## 12-1- جریان عمومی صفحه

```text
Browser
  |
  | GET /shop/
  v
Django URL Resolver
  |
  v
product_list
  |
  v
Product query + cache
  |
  v
Template render
  |
  v
HTML response
```

## 12-2- جریان فرم

```text
Browser
  |
  | POST /checkout/
  v
View
  |
  v
Form validation
  |
  +--> invalid: render page with errors
  |
  v
Service Layer
  |
  v
Database transaction
  |
  v
Redirect / HTML / JSON
```

## 12-3- جریان callback پرداخت

```text
Provider
  |
  | GET /payments/zarinpal/callback/
  v
zarinpal_callback
  |
  v
handle_zarinpal_callback
  |
  v
PaymentEvent idempotency
  |
  v
PaymentService
  |
  v
OrderService
  |
  v
JSON response
```

# 13- Error handling

خطاها در Crumbs بسته به نوع endpoint به سه شکل اصلی مدیریت می‌شوند: message و redirect، render فرم با error، یا JSON/status code برای endpointهای سیستمی.

## 13-1- خطاهای فرم

| موقعیت | رفتار |
| --- | --- |
| checkout نامعتبر | فرم با errorها دوباره نمایش داده می‌شود. |
| contact نامعتبر | صفحه تماس با form error render می‌شود. |
| career نامعتبر | فرم همکاری با errorهای فیلدها نمایش داده می‌شود. |
| register/login نامعتبر | template account با errorهای فرم نمایش داده می‌شود. |

## 13-2- خطاهای checkout

| خطا | رفتار |
| --- | --- |
| cart خالی | warning و redirect به `/cart/` |
| خطای موجودی یا capacity | message خطا و redirect به cart یا باقی ماندن در flow |
| پرداخت آنلاین در دسترس نیست | message خطا و redirect به `/cart/` |
| checkout در حال انجام | استفاده از سفارش و payment فعال در صورت امکان |

## 13-3- خطاهای پرداخت

| Endpoint | خطا | status |
| --- | --- | --- |
| `/payments/zarinpal/callback/` | authority missing | `400` |
| `/payments/zarinpal/callback/` | verification error | `400` |
| `/payments/zarinpal/callback/` | configuration error | `503` |
| `/payments/zarinpal/callback/` | processing error | `500` |
| `/payments/webhooks/stripe/` | signature invalid | `400` |
| `/payments/webhooks/stripe/` | configuration error | `503` |
| `/payments/webhooks/stripe/` | processing error | `500` |

## 13-4- خطاهای permission و not found

| موقعیت | رفتار |
| --- | --- |
| مسیر login required | redirect به login توسط Django |
| مسیر staff | redirect به admin login یا deny بر اساس Django Admin |
| سفارش غیرمجاز | پیام warning و redirect به login با `next` |
| object پیدا نشود | `404` از `get_object_or_404` |
| rate limit | `403` با پیام فارسی |

# 14- Security

امنیت endpointها ترکیبی از middlewareهای Django، تنظیمات production، CSRF، session authentication، permission decorators و rate limiting است.

## 14-1- کنترل‌های پیاده‌سازی‌شده

| کنترل | وضعیت در repository |
| --- | --- |
| CSRF | `CsrfViewMiddleware` فعال است؛ webhookهای provider به‌صورت هدفمند exempt شده‌اند. |
| Session | `SessionMiddleware` و login/logout Django استفاده می‌شود. |
| Authentication | `AuthenticationMiddleware` و decorators مثل `login_required` فعال هستند. |
| Authorization | staff pages با `staff_member_required` و `admin.site.admin_view` محافظت می‌شوند. |
| HTTPS | در production با `ENABLE_HTTPS` و تنظیمات secure cookie و HSTS کنترل می‌شود. |
| Security headers | `X_FRAME_OPTIONS`، nosniff و referrer policy در production تنظیم شده‌اند. |
| Rate limiting | در production برای `POST` روی `/accounts/login/` و `/checkout/` فعال است. |
| Order access | سفارش مهمان فقط با session مجاز checkout قابل مشاهده است. |

## 14-2- مسیرهای CSRF exempt

| Route | دلیل |
| --- | --- |
| `/payments/webhooks/stripe/` | webhook خارجی Stripe با signature validation |
| `/payments/zarinpal/callback/` | callback خارجی Zarinpal |

## 14-3- Rate limiting

`RateLimitMiddleware` فقط در حالت غیر DEBUG و برای `POST` فعال می‌شود.

| Prefix | Limit پیش‌فرض |
| --- | --- |
| `/accounts/login/` | ۱۰ درخواست در ۶۰ ثانیه |
| `/checkout/` | ۵ درخواست در ۶۰ ثانیه |

# 15- Best Practices

| شماره | توصیه |
| --- | --- |
| 1 | endpoint جدید را فقط در app مالک دامنه تعریف کنید. |
| 2 | برای صفحات عمومی server-rendered از view ساده و service مشخص استفاده کنید. |
| 3 | validation ورودی را در form انجام دهید، نه در template. |
| 4 | mutationهای سفارش، پرداخت و موجودی را مستقیم در view ننویسید. |
| 5 | برای مسیرهای `POST` از CSRF محافظت کنید مگر webhook خارجی باشد. |
| 6 | webhook خارجی باید signature یا verification provider داشته باشد. |
| 7 | endpointهای پرداخت باید idempotent باشند. |
| 8 | برای callback پرداخت، status code دقیق برگردانید. |
| 9 | routeهای staff را با `staff_member_required` محافظت کنید. |
| 10 | routeهای user-specific را با ownership check محدود کنید. |
| 11 | برای checkout از transaction و service layer استفاده کنید. |
| 12 | responseهای فرم را با message و redirect قابل فهم نگه دارید. |
| 13 | route names را ثابت و معنادار انتخاب کنید. |
| 14 | routeهای جدید را در سند مربوط به همان قابلیت ثبت کنید. |
| 15 | payload JSON عمومی نسازید مگر نیاز محصولی و تست وجود داشته باشد. |
| 16 | در admin actionها از serviceهای دامنه استفاده کنید. |
| 17 | در viewهای list از `select_related` و `prefetch_related` استفاده کنید. |
| 18 | برای endpointهای health داده حساس برنگردانید. |
| 19 | health full را در production فقط با تنظیم روشن کنید. |
| 20 | برای login و checkout rate limit را حفظ کنید. |
| 21 | routeهای SEO مثل `/robots.txt` و `/sitemap.xml` را سبک نگه دارید. |
| 22 | query parameterهای admin مثل `q` و `days` را ساده و قابل کنترل نگه دارید. |
| 23 | redirectهای پس از `POST` را رعایت کنید تا refresh باعث تکرار mutation نشود. |
| 24 | از افشای raw provider metadata در response عمومی خودداری کنید. |
| 25 | پیش از معرفی endpoint، تست method، permission و error path بنویسید. |

# 16- Common mistakes

| شماره | ضدالگو | پیامد |
| --- | --- | --- |
| 1 | مستند کردن REST API که وجود ندارد | گمراهی تیم تحویل‌گیرنده |
| 2 | ساخت JSON payload فرضی برای checkout | ناسازگاری با server-rendered flow |
| 3 | دور زدن `CheckoutForm` | ورود داده نامعتبر به سفارش |
| 4 | تغییر مستقیم `Order.status` در view | شکستن state machine |
| 5 | تغییر پرداخت بدون `PaymentService` | ناسازگاری payment و order |
| 6 | حذف CSRF از فرم‌های داخلی | افزایش ریسک امنیتی |
| 7 | CSRF exempt کردن routeهای غیر webhook | سطح حمله غیرضروری |
| 8 | قرار دادن route مدیریتی خارج از admin protection | دسترسی ناخواسته |
| 9 | اعتماد به `order_number` بدون ownership check | افشای سفارش |
| 10 | نادیده گرفتن session access سفارش مهمان | شکستن تجربه checkout مهمان |
| 11 | استفاده از `GET` برای mutation جدید | تکرار ناخواسته و مشکل cache |
| 12 | برگشت JSON از فرم‌های HTML بدون نیاز | پیچیده شدن frontend |
| 13 | نداشتن redirect بعد از `POST` | تکرار عملیات با refresh |
| 14 | log کردن داده حساس provider | ریسک امنیتی |
| 15 | نبود status code درست در webhook | retry یا خطای provider |
| 16 | ایجاد endpoint پرداخت بدون idempotency | پردازش تکراری callback |
| 17 | اضافه کردن route بدون namespace | تداخل نام route |
| 18 | query سنگین در view عمومی | کندی صفحه |
| 19 | query در template | N+1 و سختی تست |
| 20 | وابستگی مستقیم template به منطق domain | نگهداری دشوار |
| 21 | مستند نکردن permission endpoint جدید | ابهام امنیتی |
| 22 | پذیرش file upload بدون validation | ریسک امنیتی و عملیاتی |
| 23 | نمایش health full در production بدون کنترل | افشای وضعیت داخلی |
| 24 | نداشتن rate limit برای مسیرهای حساس | امکان سوءاستفاده |
| 25 | مخلوط کردن admin endpoint و public endpoint | ابهام مسئولیت و امنیت |

# 17- FAQ

## 17-1- آیا Crumbs REST API عمومی دارد؟

خیر. repository فعلی عمدتاً server-rendered است و REST API عمومی برای محصولات، سفارش‌ها یا کاربران ندارد.

## 17-2- آیا checkout JSON payload می‌گیرد؟

خیر. checkout از `CheckoutForm` و فرم HTML روی `/checkout/` استفاده می‌کند.

## 17-3- پرداخت آنلاین از کدام route برمی‌گردد؟

callback پرداخت Zarinpal روی `/payments/zarinpal/callback/` ثبت شده است.

## 17-4- webhook Stripe فعال است؟

مسیر `/payments/webhooks/stripe/` وجود دارد، اما پردازش آن به تنظیمات Stripe و `STRIPE_ENABLED` وابسته است.

## 17-5- Health endpoint اصلی کدام است؟

`/health/` برای liveness و `/ready/` برای readiness استفاده می‌شود.

## 17-6- مسیرهای admin API عمومی هستند؟

خیر. مسیرهای `/admin/operations/`، `/admin/kitchen/` و مشابه آن‌ها داخل Django Admin و مخصوص staff هستند.

## 17-7- سفارش مهمان چگونه بعد از checkout دیده می‌شود؟

شماره سفارش در session مجاز checkout ذخیره می‌شود و فقط همان session، staff یا مالک سفارش می‌تواند آن را ببیند.

## 17-8- جست‌وجوی سفارش در admin با چه فیلدی انجام می‌شود؟

مسیر `/admin/order-lookup/` از query `q` استفاده می‌کند و روی شماره سفارش، تلفن، نام، نام خانوادگی، notes و در صورت عددی بودن روی شماره روزانه جست‌وجو می‌کند.

## 17-9- آیا payment callback صفحه HTML برمی‌گرداند؟

خیر. callbackهای پرداخت خروجی JSON یا status code دارند.

## 17-10- چرا routeهای عمومی با HTML مستند شده‌اند؟

چون معماری فعلی پروژه server-rendered است و browser به جای مصرف REST API، HTML و redirect دریافت می‌کند.

# 18- جمع‌بندی

API واقعی Crumbs مجموعه‌ای از مسیرهای HTTP server-rendered، فرم‌های Django، endpointهای پرداخت، health endpoints و مسیرهای عملیاتی admin است. این پروژه در وضعیت فعلی REST API عمومی برای منابعی مثل product، order یا user ندارد و نباید چنین APIهایی در مستندات فرض شوند.

مسیرهای حساس مثل checkout، payment callback، kitchen action و pickup action به serviceهای دامنه متکی هستند تا وضعیت سفارش، پرداخت و موجودی هماهنگ باقی بماند. توسعه endpoint جدید باید با حفظ همین الگو، کنترل permission، CSRF، transaction و تست انجام شود.

# 19- اطلاعات پایانی سند

| مورد | مقدار |
| --- | --- |
| Document Version | 1.0 |
| Document Owner | Amirhossein Nasimi |
| Related Documents | `README.md`، `docs/01-معرفی-پروژه.md`، `docs/02-امکانات-پروژه.md`، `docs/03-معماری-سیستم.md`، `docs/06-راهنمای-استقرار.md`، `docs/07-راهنمای-توسعه.md`، `docs/08-مستندات-Database.md` |

| سند مرتبط | کاربرد |
| --- | --- |
| `README.md` | معرفی پروژه و مسیرهای شروع |
| `docs/01-معرفی-پروژه.md` | دامنه کلی پروژه و وضعیت فعلی |
| `docs/02-امکانات-پروژه.md` | کاتالوگ قابلیت‌ها و وضعیت آن‌ها |
| `docs/03-معماری-سیستم.md` | معماری سیستم، appها و sequenceها |
| `docs/06-راهنمای-استقرار.md` | استقرار، Nginx، Gunicorn و health checks |
| `docs/07-راهنمای-توسعه.md` | استاندارد توسعه endpoint، service، form و test |
| `docs/08-مستندات-Database.md` | معماری داده، relationshipها و transaction strategy |
