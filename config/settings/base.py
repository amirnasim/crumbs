"""
Shared Django settings for CRUMBS.

Environment-specific overrides live in dev.py and prod.py.
"""

from datetime import time
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

APPS_DIR = BASE_DIR / "apps"
sys.path.insert(0, str(APPS_DIR))

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)


def env_time(name: str, default: str) -> time:
    value = os.environ.get(name, default)
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required.")

DEBUG = env_bool("DEBUG", default=False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
]

THIRD_PARTY_APPS: list[str] = []

LOCAL_APPS = [
    "core.apps.CoreConfig",
    "products.apps.ProductsConfig",
    "cart.apps.CartConfig",
    "orders.apps.OrdersConfig",
    "payments.apps.PaymentsConfig",
    "accounts.apps.AccountsConfig",
    "wishlist.apps.WishlistConfig",
    "notifications.apps.NotificationsConfig",
    "loyalty.apps.LoyaltyConfig",
    "growth.apps.GrowthConfig",
    "intelligence.apps.IntelligenceConfig",
    "inventory.apps.InventoryConfig",
    "delivery.apps.DeliveryConfig",
    "careers.apps.CareersConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware (production-safe ordering)
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "core.middleware.CafeTableSessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.cart_context",
                "core.context_processors.table_session_context",
                "core.context_processors.seo_context",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "crumbs"),
        "USER": os.environ.get("POSTGRES_USER", "crumbs"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 0),
        "OPTIONS": {
            "connect_timeout": env_int("DB_CONNECT_TIMEOUT", 10),
        },
    }
}

# ---------------------------------------------------------------------------
# Auth / i18n
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fa"
LANGUAGES = [
    ("fa", "فارسی"),
]
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:profile"
LOGOUT_REDIRECT_URL = "core:home"

# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------

SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")
SITE_NAME = os.environ.get("SITE_NAME", "کرامبز")
SEO_DEFAULT_DESCRIPTION = os.environ.get(
    "SEO_DEFAULT_DESCRIPTION",
    "کرامبز — کوکی و قهوه لوکس دست‌ساز. سفارش آنلاین و تحویل از کانتر.",
)

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

REDIS_URL = os.environ.get("REDIS_URL", "")
CACHE_TIMEOUT_CATALOG = env_int("CACHE_TIMEOUT_CATALOG", 300)

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "IGNORE_EXCEPTIONS": True,
            },
            "KEY_PREFIX": "crumbs",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "crumbs-local",
        }
    }

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"

# ---------------------------------------------------------------------------
# Celery (Redis broker DB 0; Django cache uses REDIS_URL DB 1)
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ROUTES = {
    "notifications.tasks.*": {"queue": "sms"},
    "orders.tasks.*": {"queue": "orders"},
    "growth.tasks.*": {"queue": "analytics"},
    "intelligence.tasks.*": {"queue": "analytics"},
    "loyalty.tasks.*": {"queue": "default"},
    "inventory.tasks.*": {"queue": "default"},
}
CELERY_TASK_ANNOTATIONS = {
    "notifications.tasks.send_sms_event_task": {
        "rate_limit": "30/m",
    },
}

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "send-abandoned-cart-sms": {
        "task": "growth.tasks.send_abandoned_cart_sms",
        "schedule": crontab(minute=0),
    },
    "refresh-customer-segments": {
        "task": "growth.tasks.refresh_customer_segments_task",
        "schedule": crontab(hour=3, minute=0),
    },
    "expire-stale-reservations": {
        "task": "inventory.tasks.expire_stale_reservations_task",
        "schedule": crontab(minute="*/15"),
    },
    "cleanup-stale-online-payments": {
        "task": "payments.tasks.cleanup_stale_online_payments_task",
        "schedule": crontab(minute="*/15"),
    },
    "retry-failed-sms": {
        "task": "notifications.tasks.retry_failed_sms_task",
        "schedule": crontab(minute="*/30"),
    },
    "daily-sales-analytics": {
        "task": "growth.tasks.daily_sales_analytics_job",
        "schedule": crontab(hour=4, minute=0),
    },
    "daily-revenue-snapshot": {
        "task": "growth.tasks.daily_revenue_snapshot_job",
        "schedule": crontab(hour=4, minute=15),
    },
    "funnel-analytics-snapshot": {
        "task": "growth.tasks.funnel_analytics_snapshot_job",
        "schedule": crontab(hour=4, minute=30),
    },
    "refresh-clv-profiles": {
        "task": "growth.tasks.refresh_clv_profiles_task",
        "schedule": crontab(hour=5, minute=0),
    },
    "daily-product-stats": {
        "task": "intelligence.tasks.daily_product_stats_task",
        "schedule": crontab(hour=2, minute=0),
    },
    "user-behavior-aggregation": {
        "task": "intelligence.tasks.user_behavior_aggregation_task",
        "schedule": crontab(hour=2, minute=30),
    },
    "demand-forecast": {
        "task": "intelligence.tasks.demand_forecast_task",
        "schedule": crontab(hour=3, minute=0),
    },
    "inventory-optimization": {
        "task": "intelligence.tasks.inventory_optimization_task",
        "schedule": crontab(hour=3, minute=30),
    },
    "update-customer-intelligence": {
        "task": "intelligence.tasks.update_customer_intelligence_task",
        "schedule": crontab(hour=5, minute=30),
    },
    "intelligence-snapshot": {
        "task": "intelligence.tasks.intelligence_snapshot_task",
        "schedule": crontab(hour=6, minute=0),
    },
    "personalized-sms-offers": {
        "task": "intelligence.tasks.personalized_sms_offers_task",
        "schedule": crontab(hour=11, minute=0, day_of_week="2,5"),
    },
}

# Rate limiting (POST endpoints)
RATE_LIMIT_PATHS = {
    "/accounts/login/": (10, 60),
    "/checkout/": (5, 60),
}

# ---------------------------------------------------------------------------
# SMS (Iran-focused)
# ---------------------------------------------------------------------------

SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "console")
SMS_ENABLED = env_bool("SMS_ENABLED", default=True)
KAVENEGAR_API_KEY = os.environ.get("KAVENEGAR_API_KEY", "")
KAVENEGAR_SENDER = os.environ.get("KAVENEGAR_SENDER", "")
SMS_QUIET_HOURS_START = env_time("SMS_QUIET_HOURS_START", "22:00")
SMS_QUIET_HOURS_END = env_time("SMS_QUIET_HOURS_END", "08:00")
SMS_RATE_LIMIT_PER_USER_PER_DAY = env_int("SMS_RATE_LIMIT_PER_USER_PER_DAY", 3)
SMS_DEDUPE_WINDOW_SECONDS = env_int("SMS_DEDUPE_WINDOW_SECONDS", 300)
CART_RESERVATION_MINUTES = env_int("CART_RESERVATION_MINUTES", 30)

# ---------------------------------------------------------------------------
# Email notifications
# ---------------------------------------------------------------------------

NOTIFICATIONS_EMAIL_ENABLED = env_bool("NOTIFICATIONS_EMAIL_ENABLED", default=True)
NOTIFICATIONS_EMAIL_PROVIDER = os.environ.get("NOTIFICATIONS_EMAIL_PROVIDER", "django")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@crumbs.local")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
CAREERS_STAFF_EMAIL = os.environ.get("CAREERS_STAFF_EMAIL", "")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

# ---------------------------------------------------------------------------
# Loyalty
# ---------------------------------------------------------------------------

LOYALTY_POINTS_PER_1000_TOMAN = env_int("LOYALTY_POINTS_PER_1000_TOMAN", 10)
LOYALTY_SILVER_THRESHOLD = env_int("LOYALTY_SILVER_THRESHOLD", 1000)
LOYALTY_GOLD_THRESHOLD = env_int("LOYALTY_GOLD_THRESHOLD", 5000)

# ---------------------------------------------------------------------------
# Growth / Abandoned cart
# ---------------------------------------------------------------------------

ABANDONED_CART_HOURS = env_int("ABANDONED_CART_HOURS", 2)
ABANDONED_CART_STEP2_HOURS = env_int("ABANDONED_CART_STEP2_HOURS", 24)
ABANDONED_CART_MAX_REMINDERS = env_int("ABANDONED_CART_MAX_REMINDERS", 3)
ABANDONED_CART_HIGH_VALUE_THRESHOLD = env_int("ABANDONED_CART_HIGH_VALUE_THRESHOLD", 500000)

# Referral program
REFERRAL_REWARD_POINTS = env_int("REFERRAL_REWARD_POINTS", 100)
REFERRAL_ONBOARDING_COUPON = os.environ.get("REFERRAL_ONBOARDING_COUPON", "WELCOME10")

# ---------------------------------------------------------------------------
# Fulfillment (Iran-first)
# ---------------------------------------------------------------------------

DEFAULT_PAYMENT_METHOD = os.environ.get("DEFAULT_PAYMENT_METHOD", "online")

# ---------------------------------------------------------------------------
# Payments (Iran-first: Zarinpal primary, Stripe optional)
# ---------------------------------------------------------------------------

_settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
_in_test_settings = _settings_module.endswith(".test")

DEFAULT_PAYMENT_PROVIDER = (
    os.environ.get("DEFAULT_PAYMENT_PROVIDER")
    or os.environ.get("PAYMENT_PROVIDER")
    or ("stripe" if _in_test_settings else "zarinpal")
)
# Backward-compatible alias used across the codebase.
PAYMENT_PROVIDER = DEFAULT_PAYMENT_PROVIDER

ONLINE_PAYMENT_CURRENCY = os.environ.get("ONLINE_PAYMENT_CURRENCY", "irr").lower()

# Zarinpal (primary online provider for Iran)
ZARINPAL_MERCHANT_ID = os.environ.get("ZARINPAL_MERCHANT_ID", "")
ZARINPAL_SANDBOX = env_bool("ZARINPAL_SANDBOX", default=not _in_test_settings)
ZARINPAL_CALLBACK_URL = os.environ.get("ZARINPAL_CALLBACK_URL", "")

# Stripe (optional / sandbox only — disabled by default in production)
STRIPE_ENABLED = env_bool(
    "STRIPE_ENABLED",
    default=_in_test_settings,
)
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.environ.get("STRIPE_CURRENCY", "irr").lower()

PAYMENT_SUCCESS_URL = os.environ.get(
    "PAYMENT_SUCCESS_URL",
    "http://localhost:8000/admin/orders/order/",
)
PAYMENT_CANCEL_URL = os.environ.get(
    "PAYMENT_CANCEL_URL",
    "http://localhost:8000/admin/orders/order/",
)

# ---------------------------------------------------------------------------
# Logging (overridden in dev.py / prod.py)
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "crumbs.tasks": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "crumbs.payments": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "crumbs.orders": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
