# مستندات Database

| مورد | مقدار |
| --- | --- |
| Project | Crumbs |
| Version | `v2.0.1` |
| Author | Amirhossein Nasimi |
| Last Update | ۱۵ ژوئیه ۲۰۲۶ |
| Audience | توسعه‌دهنده Backend، مدیر فنی، تیم نگهداری و شرکت تحویل‌گیرنده |
| Status | مستند رسمی معماری داده و پایگاه‌داده |

## فهرست مطالب

- [1- مقدمه](#1--مقدمه)
- [2- نمای کلی دیتابیس](#2--نمای-کلی-دیتابیس)
- [3- دامنه‌های اصلی داده](#3--دامنههای-اصلی-داده)
- [4- مدل‌های هر دامنه](#4--مدلهای-هر-دامنه)
- [5- ارتباط بین مدل‌ها](#5--ارتباط-بین-مدلها)
- [6- کلیدها و شناسه‌ها](#6--کلیدها-و-شناسهها)
- [7- وضعیت‌ها و Enumها](#7--وضعیتها-و-enumها)
- [8- Constraintها](#8--constraintها)
- [9- Indexها](#9--indexها)
- [10- Transaction strategy](#10--transaction-strategy)
- [11- Migration strategy](#11--migration-strategy)
- [12- Data lifecycle](#12--data-lifecycle)
- [13- Performance considerations](#13--performance-considerations)
- [14- توسعه Database](#14--توسعه-database)
- [15- Backup considerations](#15--backup-considerations)
- [16- Best Practices](#16--best-practices)
- [17- Common mistakes](#17--common-mistakes)
- [18- FAQ](#18--faq)
- [19- جمع‌بندی](#19--جمعبندی)
- [20- اطلاعات پایانی سند](#20--اطلاعات-پایانی-سند)

# 1- مقدمه

این سند معماری داده و ساختار Database پروژه Crumbs را توضیح می‌دهد. هدف آن این است که توسعه‌دهنده یا تیم تحویل‌گیرنده بداند داده‌های اصلی پروژه چگونه در appهای دامنه توزیع شده‌اند، رابطه‌های مهم کدام‌اند، چه constraintهایی از یکپارچگی داده محافظت می‌کنند و هنگام توسعه schema چه اصولی باید رعایت شود.

این سند جایگزین فایل‌های `models.py` نیست و قرار نیست همه فیلدهای همه مدل‌ها را تکرار کند. تمرکز سند بر ساختار دامنه، رابطه‌های مهم، شناسه‌های کسب‌وکاری، enumهای اصلی، constraintها، indexها و چرخه حیات داده است.

## 1-1- فلسفه Database

| اصل | توضیح |
| --- | --- |
| دامنه‌محوری | مدل‌ها در appهای دامنه نگهداری می‌شوند و هر app مالک بخشی از داده است. |
| یکپارچگی داده | constraintها، foreign keyها، statusها و serviceها برای جلوگیری از داده ناسازگار استفاده می‌شوند. |
| تراکنش‌پذیری | checkout، پرداخت و رزرو موجودی باید با transaction و در صورت نیاز lock اجرا شوند. |
| خوانایی عملیاتی | داده‌های سفارش، پرداخت، موجودی و پیامک باید برای admin و عملیات قابل ردیابی باشند. |
| سازگاری با تحویل | مدل‌های legacy مثل برخی بخش‌های delivery حفظ شده‌اند تا داده و مسیرهای قبلی شکسته نشوند. |

# 2- نمای کلی دیتابیس

پایگاه‌داده اصلی پروژه PostgreSQL است. Django ORM ساختار مدل‌ها، relationها، migrationها و queryهای اصلی را مدیریت می‌کند. Redis برای Cache و Celery استفاده می‌شود، اما داده پایدار کسب‌وکار در PostgreSQL نگهداری می‌شود.

## 2-1- نمای دامنه‌ای

```text
User
  |-------------------.
  |                   |
  v                   v
Cart --------------> Order ----------------> Payment
  |                   |                       |
  v                   v                       v
CartItem           OrderItem              PaymentEvent
  |                   |
  v                   v
Product ---------- Inventory
  |                   |
  v                   v
Intelligence       StockReservation

Order
  |-------------------.
  |                   |
  v                   v
LoyaltyTransaction GrowthEvent

User
  |-------------------.
  |                   |
  v                   v
CustomerProfile    LoyaltyAccount
```

این diagram همه مدل‌ها را نشان نمی‌دهد؛ فقط ستون فقرات داده‌های عملیاتی را نمایش می‌دهد. جزئیات مدل‌های رشد، هوش تجاری، پیامک، همکاری و علاقه‌مندی در بخش‌های بعدی توضیح داده می‌شود.

## 2-2- نقش PostgreSQL

| نقش | توضیح |
| --- | --- |
| ذخیره داده دامنه | سفارش، پرداخت، محصول، موجودی، کاربر، پیامک و گزارش‌ها |
| حفظ relationها | اتصال بین user، cart، order، product، payment و inventory |
| اجرای constraintها | جلوگیری از داده تکراری یا نامعتبر |
| پشتیبانی از گزارش‌گیری | snapshotها، آمار روزانه و مدل‌های intelligence |
| پشتیبانی از transaction | محافظت از checkout، پرداخت و رزرو موجودی |

## 2-3- سازمان‌دهی دامنه‌ای

| گروه داده | app مالک |
| --- | --- |
| حساب و آدرس | `accounts` |
| محصول و دسته‌بندی | `products` |
| سبد خرید | `cart` |
| سفارش | `orders` |
| پرداخت | `payments` |
| موجودی و ظرفیت | `inventory` |
| fulfillment و وضعیت legacy | `delivery` با app label به نام `fulfillment` |
| رشد و درآمد | `growth` |
| وفاداری | `loyalty` |
| هوش تجاری | `intelligence` |
| پیامک | `notifications` با app label به نام `sms` |
| همکاری | `careers` |
| علاقه‌مندی | `wishlist` |
| داده‌های عملیاتی مشترک | `core` |

# 3- دامنه‌های اصلی داده

هر دامنه داده باید یک مسئولیت روشن داشته باشد. توسعه‌دهنده نباید داده یک دامنه را بدون دلیل در app دیگر نگهداری کند.

| دامنه | نقش کسب‌وکاری | مدل‌های شاخص |
| --- | --- | --- |
| Accounts | نگهداری پروفایل مشتری و آدرس‌ها | `CustomerProfile`، `Address` |
| Products | کاتالوگ محصول و دسته‌بندی | `Category`، `Product` |
| Cart | سبد خرید کاربر یا مهمان | `Cart`، `CartItem` |
| Orders | ثبت سفارش، اقلام، وضعیت و شماره روزانه | `Order`، `OrderItem` |
| Payments | پرداخت، provider و رویداد پرداخت | `Payment`، `PaymentEvent` |
| Inventory | موجودی، ظرفیت و رزرو | `ProductInventory`، `DailyProductionCapacity`، `StockReservation` |
| Delivery | داده‌های legacy ارسال و لاگ وضعیت | `DeliveryZone`، `OrderStatusLog` |
| Growth | کوپن، referral، campaign، event و revenue | `Coupon`، `Referral`، `GrowthEvent`، `RevenueAttribution` |
| Loyalty | امتیاز و tier مشتری | `LoyaltyAccount`، `LoyaltyTransaction` |
| Intelligence | آمار محصول، forecast و پیشنهاد فروش | `ProductDailyStats`، `ProductDemandForecast`، `UpsellImpression` |
| Notifications | قالب پیامک و لاگ ارسال | `SMSTemplate`، `SMSLog` |
| Careers | درخواست همکاری و رزومه | `CareerApplication` |
| Wishlist | ارتباط کاربر با محصول ذخیره‌شده | `WishlistItem` |
| Core | لاگ task و snapshot تحلیل روزانه | `BackgroundTaskLog`، `DailyAnalyticsSnapshot` |

# 4- مدل‌های هر دامنه

این بخش مدل‌های اصلی را در سطح معماری توضیح می‌دهد. برای جزئیات فیلدها باید به فایل‌های `models.py` مراجعه شود.

## 4-1- Accounts

| مورد | توضیح |
| --- | --- |
| Purpose | نگهداری داده تکمیلی کاربر و آدرس‌ها |
| Main models | `CustomerProfile`، `Address` |
| Relationships | `CustomerProfile` با user رابطه one-to-one دارد؛ `Address` با user رابطه many-to-one دارد. |
| Business responsibility | فراهم کردن phone، آدرس و داده‌های اولیه لازم برای checkout و حساب کاربری |

## 4-2- Products

| مورد | توضیح |
| --- | --- |
| Purpose | کاتالوگ فروشگاه |
| Main models | `Category`، `Product` |
| Relationships | هر `Product` به یک `Category` متصل است؛ `Product` با سفارش، سبد، موجودی، wishlist و intelligence ارتباط دارد. |
| Business responsibility | نگهداری نام، slug، قیمت، تصویر، وضعیت عرضه و دسته‌بندی |

## 4-3- Cart

| مورد | توضیح |
| --- | --- |
| Purpose | نگهداری سبد خرید کاربر یا session مهمان |
| Main models | `Cart`، `CartItem` |
| Relationships | `Cart` به user یا `session_key` وابسته است؛ `CartItem` به `Cart` و `Product` وصل می‌شود. |
| Business responsibility | مدیریت اقلام پیش از checkout، coupon/referral روی سبد و اتصال به سفارش checkout فعال |

## 4-4- Orders

| مورد | توضیح |
| --- | --- |
| Purpose | ثبت سفارش و وضعیت عملیاتی آن |
| Main models | `Order`، `OrderItem` |
| Relationships | `Order` به user، coupon و delivery zone اختیاری وصل است؛ `OrderItem` به `Order` و `Product` وصل است. |
| Business responsibility | شماره سفارش، شماره روزانه، وضعیت، پرداخت، fulfillment، مبلغ و اقلام سفارش |

## 4-5- Payments

| مورد | توضیح |
| --- | --- |
| Purpose | نگهداری پرداخت‌ها و رویدادهای provider |
| Main models | `Payment`، `PaymentEvent` |
| Relationships | `Payment` به `Order` وصل است؛ `PaymentEvent` رویدادهای provider را با شناسه یکتا نگهداری می‌کند. |
| Business responsibility | پیگیری provider، status، مبلغ، شناسه‌های provider، URL پرداخت و idempotency callback |

## 4-6- Inventory

| مورد | توضیح |
| --- | --- |
| Purpose | کنترل stock، ظرفیت تولید روزانه و reservation |
| Main models | `ProductInventory`، `DailyProductionCapacity`، `StockReservation` |
| Relationships | `ProductInventory` با `Product` رابطه one-to-one دارد؛ `StockReservation` می‌تواند به `Product`، `Order` و `Cart` وصل شود. |
| Business responsibility | جلوگیری از oversell، نگهداری مقدار رزروشده، تأیید و آزادسازی reservation |

## 4-7- Delivery

| مورد | توضیح |
| --- | --- |
| Purpose | نگهداری داده‌های legacy ارسال و لاگ وضعیت سفارش |
| Main models | `DeliveryZone`، `OrderStatusLog` |
| Relationships | `OrderStatusLog` به `Order` وصل است؛ `DeliveryZone` می‌تواند به سفارش‌های legacy وصل شود. |
| Business responsibility | حفظ سازگاری با fulfillment قدیمی و ثبت تغییر وضعیت سفارش |

## 4-8- Growth

| مورد | توضیح |
| --- | --- |
| Purpose | رشد، کوپن، referral، attribution و snapshotهای درآمد |
| Main models | `Coupon`، `CouponRedemption`، `ReferralCode`، `Referral`، `GrowthEvent`، `RevenueAttribution` |
| Relationships | بسیاری از مدل‌ها به user، order، cart یا product وصل می‌شوند. |
| Business responsibility | مدیریت تخفیف، کد معرف، eventهای funnel، segment و تحلیل درآمد |

## 4-9- Loyalty

| مورد | توضیح |
| --- | --- |
| Purpose | امتیاز و سطح وفاداری مشتری |
| Main models | `LoyaltyAccount`، `LoyaltyTransaction` |
| Relationships | `LoyaltyAccount` با user رابطه one-to-one دارد؛ `LoyaltyTransaction` به account و سفارش اختیاری وصل است. |
| Business responsibility | نگهداری امتیاز فعلی، امتیاز عمر مشتری، سطح و history تغییر امتیاز |

## 4-10- Intelligence

| مورد | توضیح |
| --- | --- |
| Purpose | داده‌های تحلیلی و توصیه‌گر rule-based |
| Main models | `ProductDailyStats`، `ProductDemandForecast`، `ProductBakeRecommendation`، `CustomerIntelligenceProfile`، `UpsellImpression` |
| Relationships | مدل‌های محصولی به `Product` و مدل‌های مشتری به user یا order وصل می‌شوند. |
| Business responsibility | نگهداری آمار روزانه، forecast، توصیه پخت، profile تحلیلی و impression پیشنهادها |

## 4-11- Notifications

| مورد | توضیح |
| --- | --- |
| Purpose | قالب پیامک و log ارسال پیام |
| Main models | `SMSTemplate`، `SMSLog` |
| Relationships | `SMSLog` می‌تواند به user و order وصل شود. |
| Business responsibility | ثبت پیامک‌های ارسالی، وضعیت ارسال، provider و template استفاده‌شده |

## 4-12- Careers

| مورد | توضیح |
| --- | --- |
| Purpose | ذخیره درخواست همکاری |
| Main models | `CareerApplication` |
| Relationships | مستقل از سفارش و کاربر است. |
| Business responsibility | نگهداری اطلاعات متقاضی، موقعیت شغلی، نوع همکاری، رزومه و status بررسی |

## 4-13- Wishlist

| مورد | توضیح |
| --- | --- |
| Purpose | نگهداری محصولات ذخیره‌شده توسط کاربر |
| Main models | `WishlistItem` |
| Relationships | هر مورد به user و product وصل است. |
| Business responsibility | جلوگیری از ذخیره تکراری یک product برای یک user |

## 4-14- Core

| مورد | توضیح |
| --- | --- |
| Purpose | داده‌های عملیاتی مشترک |
| Main models | `BackgroundTaskLog`، `DailyAnalyticsSnapshot` |
| Relationships | `BackgroundTaskLog` مستقل است و برای مشاهده وضعیت taskها استفاده می‌شود. |
| Business responsibility | observability داخلی، ثبت نتیجه task و snapshot تحلیل روزانه |

# 5- ارتباط بین مدل‌ها

رابطه‌های داده‌ای مهم باید بر اساس flowهای کسب‌وکار فهمیده شوند. همه relationها اهمیت یکسان ندارند؛ برخی برای نمایش ساده‌اند و برخی از یکپارچگی checkout، payment و inventory محافظت می‌کنند.

## 5-1- User، Cart و Order

```text
User
  | one-to-one
  v
Cart
  | one-to-many
  v
CartItem
  |
  v
Product

Cart
  | optional active checkout
  v
Order
```

| رابطه | دلیل |
| --- | --- |
| user به `Cart` | هر کاربر واردشده یک سبد فعال دارد. |
| `Cart` به `CartItem` | اقلام سبد تا پیش از checkout نگهداری می‌شوند. |
| `CartItem` به `Product` | هر قلم سبد به محصول واقعی وصل است. |
| `Cart.active_checkout_order` به `Order` | هنگام checkout فعال، mutation سبد کنترل می‌شود. |

## 5-2- Order، OrderItem و Payment

```text
Order
  | one-to-many
  v
OrderItem
  |
  v
Product

Order
  | one-to-many
  v
Payment
```

| رابطه | دلیل |
| --- | --- |
| `Order` به `OrderItem` | snapshot اقلام سفارش در لحظه ثبت نگهداری می‌شود. |
| `OrderItem` به `Product` | ارتباط تاریخی با محصول حفظ می‌شود، در حالی که نام و قیمت در قلم سفارش هم ذخیره شده‌اند. |
| `Order` به `Payment` | یک سفارش می‌تواند چند payment record داشته باشد، مخصوصاً در retry یا providerهای مختلف. |
| `PaymentEvent` | eventهای provider با `event_id` یکتا برای جلوگیری از پردازش تکراری نگهداری می‌شوند. |

## 5-3- Product و Inventory

```text
Product
  | one-to-one
  v
ProductInventory

Product
  | one-to-many
  v
DailyProductionCapacity

Product
  | one-to-many
  v
StockReservation
```

| رابطه | دلیل |
| --- | --- |
| `Product` به `ProductInventory` | stock کلی و مقدار reserved برای هر محصول نگهداری می‌شود. |
| `Product` به `DailyProductionCapacity` | ظرفیت تولید برای تاریخ مشخص کنترل می‌شود. |
| `StockReservation` به `Cart` یا `Order` | رزرو می‌تواند قبل یا بعد از ساخت سفارش معنا داشته باشد. |

## 5-4- Customer، Loyalty و Growth

```text
User
  | one-to-one
  v
LoyaltyAccount
  | one-to-many
  v
LoyaltyTransaction
  |
  v
Order

User
  | one-to-one
  v
ReferralCode
  | one-to-many
  v
Referral
```

| رابطه | دلیل |
| --- | --- |
| user به `LoyaltyAccount` | امتیاز و tier کاربر به حساب وفاداری متصل است. |
| `LoyaltyTransaction` به `Order` | امتیاز کسب‌شده یا تغییر مرتبط با سفارش قابل ردیابی است. |
| user به `ReferralCode` | هر کاربر می‌تواند کد معرف اختصاصی داشته باشد. |
| `Referral` به `first_order` | تبدیل referral به سفارش اول قابل پیگیری است. |

## 5-5- Growth و Intelligence

```text
Product
  |-------------------.
  |                   |
  v                   v
ProductDailyStats   ProductDemandForecast
  |                   |
  v                   v
ProductBakeRecommendation

User
  |
  v
CustomerIntelligenceProfile

Order
  |
  v
RevenueAttribution
```

| رابطه | دلیل |
| --- | --- |
| product stats | آمار محصول برای گزارش و توصیه استفاده می‌شود. |
| forecast و bake recommendation | forecast، stock و capacity به تصمیم عملیاتی پخت کمک می‌کنند. |
| user intelligence profile | رفتار مشتری و affinityها برای پیشنهادهای rule-based نگهداری می‌شوند. |
| revenue attribution | سهم coupon، referral، SMS یا promotion از درآمد سفارش ثبت می‌شود. |

# 6- کلیدها و شناسه‌ها

شناسه‌های فنی و کسب‌وکاری در Crumbs نقش متفاوت دارند. Primary key داخلی برای relationهای پایگاه‌داده استفاده می‌شود، اما کاربر و عملیات معمولاً با شناسه‌های کسب‌وکاری مانند `order_number` یا `daily_sequence` کار می‌کنند.

## 6-1- Primary Keys و Foreign Keys

| نوع | توضیح |
| --- | --- |
| Primary key | توسط Django برای مدل‌ها مدیریت می‌شود و برای relation داخلی استفاده می‌شود. |
| Foreign key | رابطه بین دامنه‌ها را مشخص می‌کند؛ مانند `Order` به user یا `OrderItem` به `Product`. |
| One-to-one | برای رابطه‌هایی مثل user به `CustomerProfile`، user به `LoyaltyAccount` و product به `ProductInventory` استفاده می‌شود. |
| Many-to-one | برای اقلام سفارش، اقلام سبد، پرداخت‌ها، eventها و logها استفاده می‌شود. |

## 6-2- شناسه‌های کسب‌وکاری

| شناسه | مدل | کاربرد |
| --- | --- | --- |
| `order_number` | `Order` | شماره یکتای سفارش برای رسید و پیگیری |
| `daily_sequence` | `Order` | شماره روزانه برای عملیات کافه |
| `daily_sequence_date` | `Order` | تاریخ شماره روزانه |
| `slug` | `Category`، `Product` | ساخت URL فروشگاه |
| `code` | `Coupon`، `ReferralCode`، `SMSTemplate` | شناسه قابل استفاده در عملیات و campaign |
| `event_id` | `PaymentEvent` | جلوگیری از پردازش تکراری event provider |
| `task_id` | `BackgroundTaskLog` | ردیابی task پس‌زمینه |

## 6-3- Daily order number

`daily_sequence` برای عملیات کافه استفاده می‌شود و همراه با `daily_sequence_date` یکتا نگه داشته می‌شود. این شناسه برای staff خواناتر از شناسه داخلی database است.

# 7- وضعیت‌ها و Enumها

Enumها در مدل‌ها برای محدود کردن مقدار status و خوانایی کد استفاده می‌شوند. تغییر enum باید با دقت انجام شود، چون ممکن است روی داده ذخیره‌شده، admin، template، service و تست اثر بگذارد.

## 7-1- سفارش

| Enum | مقدارهای اصلی |
| --- | --- |
| `Order.Status` | `pending_payment`، `awaiting_payment`، `paid`، `confirmed_by_shop`، `preparing`، `packaged`، `out_for_delivery`، `delivered`، `cancelled`، `refunded` |
| `Order.PaymentStatus` | `pending_payment`، `paid`، `cod_pending`، `cod_confirmed`، `cash_received`، `failed`، `refund_requested`، `refund_processed` |
| `Order.PaymentMethod` | `cod`، `online`، `cash`، `counter_card` |
| `Order.FulfillmentType` | `pickup`، `courier`، `express`، `cod` |

## 7-2- پرداخت و موجودی

| Enum | مقدارها |
| --- | --- |
| `Payment.Provider` | `zarinpal`، `stripe`، `cod`، `cash`، `counter_card` |
| `Payment.Status` | `pending`، `processing`، `succeeded`، `failed`، `cancelled`، `refunded` |
| `StockReservation.Status` | `active`، `confirmed`، `released`، `expired` |

## 7-3- محصول، وفاداری و همکاری

| Enum | مقدارها |
| --- | --- |
| `Product.AvailabilityStatus` | `available`، `out_of_stock`، `coming_soon` |
| `LoyaltyAccount.Tier` | `normal`، `silver`، `gold` |
| `LoyaltyTransaction.Type` | `earn`، `redeem`، `adjust` |
| `CareerApplication.Status` | `new`، `reviewing`، `interview`، `rejected`، `hired` |

## 7-4- رشد، پیامک و هوش تجاری

| Enum | مقدارها |
| --- | --- |
| `Coupon.DiscountType` | `percentage`، `fixed` |
| `Coupon.CampaignType` | `general`، `first_order`، `seasonal`، `abandoned_cart` |
| `Referral.Status` | `pending`، `completed`، `rewarded` |
| `GrowthEvent.EventType` | `product_view`، `add_to_cart`، `checkout_start`، `checkout_complete`، `sms_sent`، `sms_conversion` |
| `SMSTemplate.Category` | `order`، `payment`، `marketing`، `abandoned_cart` |
| `SMSLog.Status` | `pending`، `sent`، `failed`، `skipped` |
| `ProductBakeRecommendation.Status` | `ok`، `low_stock`، `overstock_risk` |
| `IntelligenceSnapshot.Period` | `daily`، `weekly` |
| `UpsellImpression.Slot` | `home`، `product`، `cart`، `checkout`، `sms` |

# 8- Constraintها

Constraintها بخشی از منطق محافظت از داده هستند. این بخش فقط constraintهای مهم را توضیح می‌دهد و همه جزئیات فیلدها را تکرار نمی‌کند.

| Constraint | مدل | هدف |
| --- | --- | --- |
| `cart_requires_user_or_session` | `Cart` | هر سبد باید یا user داشته باشد یا `session_key`. |
| `unique_product_per_cart` | `CartItem` | یک product در یک cart تکراری نشود. |
| `cart_item_quantity_positive` | `CartItem` | تعداد قلم سبد حداقل ۱ باشد. |
| `unique_product_slug_per_category` | `Product` | slug محصول در هر دسته یکتا باشد. |
| `orders_unique_daily_sequence_per_date` | `Order` | شماره روزانه در هر تاریخ تکراری نشود. |
| `order_item_quantity_positive` | `OrderItem` | تعداد قلم سفارش حداقل ۱ باشد. |
| `unique_daily_capacity_per_product` | `DailyProductionCapacity` | ظرفیت روزانه محصول برای یک تاریخ تکراری نشود. |
| `unique_user_segment` | `CustomerSegmentMembership` | عضویت user در segment تکراری نشود. |
| `unique_product_daily_stat` | `ProductDailyStats` | آمار روزانه هر محصول برای یک روز یکتا باشد. |
| `unique_product_forecast` | `ProductDemandForecast` | forecast محصول برای تاریخ و window مشخص تکراری نشود. |
| `unique_bake_recommendation_per_day` | `ProductBakeRecommendation` | توصیه پخت روزانه برای محصول تکراری نشود. |
| `unique_co_purchase_pair` | `ProductCoPurchase` | زوج خرید همزمان تکراری نشود. |
| `unique_intelligence_snapshot` | `IntelligenceSnapshot` | snapshot برای تاریخ و دوره تکراری نشود. |
| `unique_wishlist_item_per_user` | `WishlistItem` | یک محصول برای یک user چند بار wishlist نشود. |

## 8-1- Database integrity

| ابزار | کاربرد |
| --- | --- |
| Foreign key | حفظ رابطه بین دامنه‌ها |
| Unique constraint | جلوگیری از داده تکراری |
| Check constraint | جلوگیری از مقدارهای غیرمعتبر مانند quantity صفر |
| `on_delete` | تعیین رفتار هنگام حذف داده مرجع |
| Enum choices | محدود کردن مقدار statusها و نوع‌ها |

# 9- Indexها

Indexها برای queryهای پرتکرار، فیلترهای admin، گزارش‌ها و flowهای عملیاتی استفاده می‌شوند. افزودن index باید بر اساس الگوی query واقعی انجام شود، نه به‌صورت پیش‌فرض برای همه فیلدها.

## 9-1- حوزه‌هایی که index در آن‌ها مهم است

| حوزه | نمونه فیلد یا مدل | دلیل |
| --- | --- | --- |
| سفارش | `status`، `payment_status`، `payment_method`، `created_at` | فیلتر admin و داشبورد عملیات |
| شماره روزانه | `daily_sequence_date`، `daily_sequence` | جست‌وجوی سریع سفارش روز |
| محصول | `category`، `slug`، `is_featured`، `availability_status` | فروشگاه، دسته‌بندی و صفحه اصلی |
| پرداخت | `provider`، `status`، `created_at` | cleanup، callback و بررسی خطا |
| موجودی | `status`، `production_date`، `order` | reservation lifecycle |
| رشد | `event_type`، `created_at`، `status` | گزارش funnel و analytics |
| پیامک | `status`، `template_code`، `created_at` | retry و گزارش ارسال |
| task | `task_name`، `status`، `created_at` | observability و task center |

## 9-2- Search و Filtering

Admin و داشبوردهای عملیاتی معمولاً بر اساس status، تاریخ، شماره سفارش، provider، محصول یا کاربر فیلتر می‌شوند. بنابراین indexهای موجود بیشتر در مسیرهای عملیاتی و گزارش‌گیری ارزش دارند.

# 10- Transaction strategy

تراکنش‌ها در Crumbs برای جلوگیری از داده ناسازگار در checkout، پرداخت و موجودی ضروری هستند. هر تغییری که همزمان چند model را تغییر می‌دهد یا به race condition حساس است باید transaction boundary مشخص داشته باشد.

## 10-1- نقاط حساس

| جریان | دلیل نیاز به transaction |
| --- | --- |
| Checkout | ساخت سفارش، قفل سبد، نهایی‌سازی stock و ایجاد payment به هم وابسته‌اند. |
| Payment callback | provider ممکن است callback تکراری ارسال کند و باید idempotent پردازش شود. |
| Counter payment | دریافت وجه در کافه باید با وضعیت سفارش هماهنگ بماند. |
| Inventory reservation | رزرو، release، confirm و fulfill نباید باعث oversell شود. |
| Daily order number | شماره روزانه باید در یک تاریخ تکراری نشود. |

## 10-2- Atomic operations

| الگو | کاربرد |
| --- | --- |
| `transaction.atomic` | اجرای چند تغییر مرتبط به‌صورت یک واحد |
| `select_for_update` | قفل رکوردهای حساس مانند order، payment یا inventory |
| Idempotency check | جلوگیری از پردازش دوباره callback یا task |
| Service boundary | نگهداری transaction در لایه service، نه template یا admin مستقیم |

# 11- Migration strategy

Migrationها تاریخچه تکامل schema هستند. تغییر در model بدون migration معتبر باعث اختلاف بین کد و پایگاه‌داده می‌شود.

## 11-1- دستورهای اصلی

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py check_migration_history
```

## 11-2- Best practices برای Migration

| توصیه | دلیل |
| --- | --- |
| Migration کوچک بسازید | review و rollback ذهنی ساده‌تر می‌شود. |
| تغییر داده سنگین را جدا کنید | کاهش ریسک lock طولانی |
| فیلد required را با برنامه اضافه کنید | جلوگیری از شکست روی داده موجود |
| rename را با دقت انجام دهید | جلوگیری از از دست رفتن داده |
| migration را پس از تولید تست کنید | اطمینان از سازگاری history |

## 11-3- Rollback considerations

Rollback migration همیشه ساده نیست. اگر migration داده را حذف یا تبدیل کرده باشد، rollback ممکن است داده قبلی را بازنگرداند. برای تغییرهای پرریسک باید پیش از deploy از `docs/BACKUP_RESTORE.md` استفاده شود.

# 12- Data lifecycle

چرخه داده در پروژه بر اساس جریان‌های اصلی کسب‌وکار تعریف شده است. همه داده‌ها حذف نرم عمومی ندارند؛ در بسیاری از بخش‌ها status، log یا history برای ردیابی نگهداری می‌شود.

## 12-1- Creation و Update

| داده | زمان ایجاد | مسیر تغییر |
| --- | --- | --- |
| `Cart` | هنگام تعامل کاربر یا session | serviceهای cart |
| `Order` | در checkout | serviceهای orders و delivery checkout |
| `Payment` | هنگام شروع پرداخت | `PaymentService` |
| `StockReservation` | هنگام افزودن به سبد یا ساخت سفارش | serviceهای inventory |
| `SMSLog` | هنگام ارسال پیامک | service و taskهای notifications |
| `GrowthEvent` | هنگام eventهای funnel | serviceهای growth |

## 12-2- Reservation lifecycle

```text
active
  | confirm
  v
confirmed
  | fulfill
  v
consumed by order flow

active
  | release / expire
  v
released or expired
```

| وضعیت | معنی |
| --- | --- |
| `active` | رزرو فعال است و هنوز قطعی نشده است. |
| `confirmed` | رزرو به سفارش معتبر وصل شده است. |
| `released` | رزرو آزاد شده است. |
| `expired` | رزرو به علت زمان یا cleanup منقضی شده است. |

## 12-3- Order lifecycle

چرخه سفارش با `Order.Status` کنترل می‌شود. وضعیت‌های فعال فعلی برای checkout و pickup استفاده می‌شوند و مقدارهای legacy برای سازگاری نگهداری شده‌اند.

| مرحله | داده‌های مرتبط |
| --- | --- |
| ثبت سفارش | `Order`، `OrderItem`، `StockReservation` |
| پرداخت | `Payment`، `PaymentEvent`، `payment_status` |
| آماده‌سازی | `status` و `OrderStatusLog` |
| تحویل | وضعیت‌های `packaged` و `delivered` |
| لغو یا refund | status و payment status مرتبط |

## 12-4- Payment lifecycle

| مرحله | مدل |
| --- | --- |
| ایجاد payment | `Payment` با status اولیه |
| اتصال به provider | ذخیره شناسه یا URL provider |
| callback یا webhook | `PaymentEvent` و service پرداخت |
| موفقیت یا شکست | به‌روزرسانی `Payment` و `Order` |
| cleanup | taskهای payments برای پرداخت‌های stale |

# 13- Performance considerations

Performance در Database فقط با index حل نمی‌شود. انتخاب relation درست، query مناسب، استفاده از eager loading و پرهیز از محاسبه سنگین در template اهمیت دارد.

## 13-1- N+1 avoidance

| موقعیت | راهکار |
| --- | --- |
| نمایش سفارش و کاربر | `select_related` برای relationهای تک‌مقداری |
| نمایش سفارش و اقلام | `prefetch_related` برای `items` |
| نمایش محصول و دسته‌بندی | `select_related` برای `category` |
| نمایش محصول و موجودی | استفاده از relation `inventory` با query مناسب |
| admin list سنگین | بهینه‌سازی queryset در ModelAdmin |

## 13-2- Aggregation و Snapshot

مدل‌های snapshot مانند `DailyAnalyticsSnapshot`، `DailyRevenueSnapshot`، `FunnelAnalyticsSnapshot` و `IntelligenceSnapshot` برای نگهداری خروجی محاسبات دوره‌ای استفاده می‌شوند. هدف آن‌ها کاهش محاسبه تکراری روی داده خام است.

## 13-3- Queryهای حساس

| Query | دلیل حساسیت |
| --- | --- |
| فیلتر سفارش بر اساس status و تاریخ | داشبورد عملیات و admin |
| پرداخت‌های provider/status | callback، cleanup و خطایابی |
| reservation بر اساس status و تاریخ تولید | کنترل موجودی و ظرفیت |
| گزارش محصول بر اساس تاریخ | analytics و intelligence |
| SMS log بر اساس status | retry و مانیتورینگ ارسال |

# 14- توسعه Database

توسعه Database باید محافظه‌کارانه انجام شود. تغییر schema می‌تواند روی migration، تست، داده تولیدی، admin و گزارش‌ها اثر بگذارد.

## 14-1- افزودن Model جدید

| مرحله | توضیح |
| --- | --- |
| تعیین app مالک | model باید در دامنه درست قرار گیرد. |
| تعریف relationها | foreign key و on_delete باید دلیل کسب‌وکاری داشته باشد. |
| تعیین شناسه کسب‌وکاری | اگر کاربر یا عملیات به شناسه نیاز دارد، field مناسب تعریف شود. |
| افزودن constraint | یکتایی و invariantهای واقعی در database محافظت شوند. |
| افزودن index | فقط برای queryهای قابل انتظار و پرتکرار |
| migration | با `python manage.py makemigrations` ساخته شود. |
| تست | سناریوی ایجاد، validation و relation پوشش داده شود. |
| admin | اگر داده عملیاتی است، admin مناسب اضافه شود. |

## 14-2- افزودن Field

| نوع field | نکته |
| --- | --- |
| nullable | برای rollout امن‌تر مناسب است. |
| non-null | باید default یا data migration داشته باشد. |
| status | بهتر است با TextChoices تعریف شود. |
| monetary | باید DecimalField باشد. |
| JSON | فقط برای داده نیمه‌ساختاریافته واقعی استفاده شود. |
| indexed | فقط اگر query واقعی دارد. |

## 14-3- حفظ compatibility

| تغییر | راهکار |
| --- | --- |
| حذف فیلد | ابتدا استفاده از کد حذف شود، سپس migration حذف فیلد انجام شود. |
| تغییر enum | داده موجود، admin، template و service بررسی شوند. |
| تغییر relation | on_delete، داده موجود و migration بررسی شوند. |
| تغییر constraint | ابتدا داده موجود با constraint جدید سازگار شود. |
| تغییر index | اثر روی queryها و زمان migration بررسی شود. |

# 15- Backup considerations

Backup و Restore به‌صورت عملی در `docs/BACKUP_RESTORE.md` توضیح داده شده است. این سند فقط ملاحظات Database را خلاصه می‌کند.

| موضوع | نکته |
| --- | --- |
| پیش از deploy | اجرای Backup کامل توصیه می‌شود. |
| پیش از migration پرریسک | Backup پایگاه‌داده ضروری است. |
| Media | جدا از Database پشتیبان‌گیری می‌شود. |
| Restore | destructive است و می‌تواند سفارش‌ها یا پرداخت‌های جدید را از بین ببرد. |
| نگهداری خارج از سرور | Backup فقط داخل سرور کافی نیست. |

# 16- Best Practices

| شماره | توصیه |
| --- | --- |
| 1 | پیش از افزودن model، app مالک دامنه را مشخص کنید. |
| 2 | رابطه‌های one-to-one را فقط برای داده واقعاً یکتا استفاده کنید. |
| 3 | برای statusها از TextChoices استفاده کنید. |
| 4 | برای شناسه‌های کسب‌وکاری مثل `order_number` uniqueness را حفظ کنید. |
| 5 | برای quantity از constraint مثبت بودن استفاده کنید. |
| 6 | برای relationهای عملیاتی `related_name` معنی‌دار انتخاب کنید. |
| 7 | مقدارهای مالی را با DecimalField نگهداری کنید. |
| 8 | queryهای پرتکرار admin را با index مناسب پشتیبانی کنید. |
| 9 | index را فقط برای query واقعی اضافه کنید. |
| 10 | transaction را در service نگهداری کنید. |
| 11 | برای race condition از `select_for_update` در transaction استفاده کنید. |
| 12 | callbackهای payment را idempotent طراحی کنید. |
| 13 | eventهای خارجی را با شناسه یکتا ذخیره کنید. |
| 14 | snapshotهای تحلیلی را از داده خام جدا نگه دارید. |
| 15 | JSONField را برای داده بی‌ساختار بی‌دلیل استفاده نکنید. |
| 16 | پیش از migration سنگین، حجم داده و lock را بررسی کنید. |
| 17 | migrationهای schema و data را در صورت ریسک بالا جدا کنید. |
| 18 | حذف model یا field را بدون بررسی داده تولیدی انجام ندهید. |
| 19 | برای هر relation مهم تست ایجاد و حذف بنویسید. |
| 20 | admin را برای داده‌های عملیاتی خوانا و امن نگه دارید. |
| 21 | برای گزارش‌های پرتکرار از snapshot یا aggregation کنترل‌شده استفاده کنید. |
| 22 | مقدارهای legacy را بدون migration و تصمیم دامنه حذف نکنید. |
| 23 | در مدل‌های پرداخت و سفارش از تغییر مستقیم خارج از service پرهیز کنید. |
| 24 | برای tableهای بزرگ، migration را در محیط مشابه تولید تست کنید. |
| 25 | پس از تغییر schema، `python manage.py check_migration_history` را اجرا کنید. |

# 17- Common mistakes

| شماره | ضدالگو | پیامد |
| --- | --- | --- |
| 1 | افزودن field بدون migration | ناسازگاری کد و Database |
| 2 | حذف migration قدیمی | شکست محیط‌های نصب‌شده |
| 3 | تغییر enum بدون migration یا data check | باقی ماندن مقدار نامعتبر |
| 4 | تغییر مستقیم `Order.status` خارج از service | شکستن lifecycle |
| 5 | تغییر مستقیم موجودی بدون reservation service | oversell یا stock نادرست |
| 6 | ساخت payment بدون `PaymentService` | ناسازگاری payment و order |
| 7 | افزودن index برای همه فیلدها | افزایش هزینه write و migration |
| 8 | نداشتن index برای فیلترهای پرتکرار | کندی admin و dashboard |
| 9 | استفاده از JSONField برای داده رابطه‌ای | سخت شدن query و constraint |
| 10 | استفاده از string خام برای status | خطای تایپی و نبود refactor امن |
| 11 | قرار دادن داده حساس در metadata | ریسک امنیتی |
| 12 | حذف cascade اشتباه | حذف ناخواسته داده عملیاتی |
| 13 | استفاده از `CASCADE` بدون دلیل | ریسک حذف زنجیره‌ای |
| 14 | فراموش کردن `PROTECT` برای داده مالی یا سفارش | از بین رفتن history |
| 15 | تغییر constraint بدون پاک‌سازی داده موجود | شکست migration |
| 16 | migration ترکیبی بزرگ | سختی rollback و review |
| 17 | محاسبه سنگین روی هر request | کندی صفحه‌های پرترافیک |
| 18 | query در template | N+1 و نبود تست‌پذیری |
| 19 | نبود تست برای constraint جدید | کشف خطا در production |
| 20 | restore پایگاه‌داده بدون بررسی سفارش‌های جدید | از دست رفتن داده واقعی |
| 21 | ذخیره response کامل provider بدون پالایش | نشت داده حساس |
| 22 | حذف داده legacy بدون سند | شکستن سازگاری تاریخی |
| 23 | تغییر نام field بدون برنامه migration | از دست رفتن داده یا خطای کد |
| 24 | استفاده از تاریخ naive | خطای timezone |
| 25 | بی‌توجهی به `related_name` | queryهای ناخوانا و ناسازگار |

# 18- FAQ

## 18-1- آیا این سند جایگزین `models.py` است؟

خیر. این سند معماری داده و رابطه‌ها را توضیح می‌دهد. جزئیات فیلدها در فایل‌های `models.py` قرار دارد.

## 18-2- چرا همه فیلدهای همه مدل‌ها در سند نیامده است؟

هدف سند توضیح ساختار دامنه و رابطه‌هاست، نه بازتولید کد. تکرار کامل فیلدها باعث ناسازگاری سریع سند با کد می‌شود.

## 18-3- مدل اصلی سفارش کدام است؟

مدل اصلی سفارش `Order` است و اقلام آن در `OrderItem` نگهداری می‌شوند.

## 18-4- رابطه سفارش و پرداخت چگونه است؟

`Payment` با foreign key به `Order` وصل است. یک سفارش می‌تواند چند payment record داشته باشد.

## 18-5- موجودی محصول کجا نگهداری می‌شود؟

موجودی کلی در `ProductInventory` و رزروها در `StockReservation` نگهداری می‌شوند.

## 18-6- شماره روزانه سفارش چگونه محافظت می‌شود؟

ترکیب `daily_sequence_date` و `daily_sequence` با constraint `orders_unique_daily_sequence_per_date` یکتا می‌شود.

## 18-7- چرا بعضی مدل‌های delivery هنوز وجود دارند؟

مدل‌های legacy مثل `DeliveryZone` برای سازگاری داده و مسیرهای قدیمی حفظ شده‌اند، هرچند checkout عمومی فعلی بر pickup متمرکز است.

## 18-8- آیا Redis بخشی از Database اصلی است؟

خیر. Redis برای Cache، Session Cache و Celery استفاده می‌شود. داده پایدار کسب‌وکار در PostgreSQL است.

## 18-9- چه زمانی باید index اضافه شود؟

وقتی query پرتکرار، فیلتر admin، گزارش یا lookup عملیاتی مشخص وجود داشته باشد.

## 18-10- پیش از تغییر schema چه کاری لازم است؟

app مالک، relationها، constraintها، migration، داده موجود، تست‌ها و اثر روی admin و serviceها باید بررسی شوند.

# 19- جمع‌بندی

Database پروژه Crumbs بر اساس دامنه‌های مستقل طراحی شده است. سفارش، پرداخت، موجودی، محصول، رشد، وفاداری، پیامک و هوش تجاری هر کدام مدل‌های مالک خود را دارند و ارتباط بین آن‌ها از طریق foreign key، one-to-one، constraint و serviceهای دامنه کنترل می‌شود.

نقاط حساس پایگاه‌داده شامل checkout، payment callback، reservation موجودی، شماره روزانه سفارش، coupon/referral و snapshotهای تحلیلی هستند. توسعه این بخش‌ها باید با transaction، تست، migration امن و رعایت مرز appها انجام شود.

# 20- اطلاعات پایانی سند

| مورد | مقدار |
| --- | --- |
| Document Version | 1.0 |
| Document Owner | Amirhossein Nasimi |
| Related Documents | `README.md`، `docs/01-معرفی-پروژه.md`، `docs/02-امکانات-پروژه.md`، `docs/03-معماری-سیستم.md`، `docs/06-راهنمای-استقرار.md`، `docs/07-راهنمای-توسعه.md`، `docs/BACKUP_RESTORE.md` |

| سند مرتبط | کاربرد |
| --- | --- |
| `README.md` | معرفی پروژه، نصب و مسیرهای شروع |
| `docs/01-معرفی-پروژه.md` | دامنه پروژه و وضعیت فعلی |
| `docs/02-امکانات-پروژه.md` | کاتالوگ قابلیت‌ها و وضعیت آن‌ها |
| `docs/03-معماری-سیستم.md` | معماری سیستم، appها و sequenceها |
| `docs/06-راهنمای-استقرار.md` | استقرار، production stack و کنترل‌های Go Live |
| `docs/07-راهنمای-توسعه.md` | استاندارد توسعه، service layer و تست‌ها |
| `docs/BACKUP_RESTORE.md` | Backup و Restore پایگاه‌داده و Media |
