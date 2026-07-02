from django.conf import settings

from cart.services import get_or_create_cart
from core.table_session import get_table_from_session


def cart_context(request):
    if not request.session.session_key:
        request.session.create()

    if request.user.is_authenticated:
        cart, _ = get_or_create_cart(user=request.user)
    else:
        cart, _ = get_or_create_cart(session_key=request.session.session_key)

    return {
        "cart_item_count": cart.total_items,
        "cart_subtotal": cart.get_subtotal(),
    }


def table_session_context(request):
    return {"cafe_table_number": get_table_from_session(request)}


def seo_context(request):
    site_url = settings.SITE_URL.rstrip("/")
    site_name = settings.SITE_NAME

    static_titles = {
        "core:home": "خانه",
        "core:about": "داستان ما",
        "core:contact": "تماس",
        "products:product_list": "منو",
        "careers:careers": "همکاری با ما",
        "core:cart": "سبد خرید",
        "core:checkout": "ثبت سفارش",
        "accounts:login": "ورود",
        "accounts:register": "ثبت‌نام",
        "accounts:profile": "حساب کاربری",
        "accounts:order_list": "سفارش‌های من",
    }

    static_descriptions = {
        "core:home": (
            "CRUMBS — کوکی و قهوه دست‌ساز با مواد واقعی. "
            "batches کوچک، طعم گرم، سفارش و تحویل از کانتر."
        ),
        "core:about": "داستان CRUMBS — کوکی و قهوه دست‌ساز با مواد واقعی و batches کوچک",
        "core:contact": "تماس با کرامبز — سوالات، سفارش‌ها و همکاری‌ها",
        "products:product_list": (
            "منوی CRUMBS — کوکی، قهوه، غذا، سالاد و نوشیدنی. "
            "سفارش آنلاین و تحویل از کانتر."
        ),
        "careers:careers": "همکاری با تیم Crumbs — ارسال درخواست استخدام",
        "core:cart": "سبد خرید کرامبز — مرور اقلام و ادامه ثبت سفارش از کانتر.",
        "core:checkout": "ثبت سفارش حضوری در کرامبز — پرداخت آنلاین یا در صندوق، تحویل از کانتر.",
        "accounts:login": "ورود به حساب کاربری کرامبز — مشاهده سفارش‌ها و مدیریت پروفایل.",
        "accounts:register": "ایجاد حساب کاربری در کرامبز — سفارش سریع‌تر و پیگیری سفارش‌ها.",
        "accounts:profile": "مدیریت حساب کاربری کرامبز — سفارش‌ها و اطلاعات پروفایل.",
        "accounts:order_list": "تاریخچه سفارش‌های کرامبز.",
    }

    view_name = getattr(request.resolver_match, "view_name", None)
    page_title = static_titles.get(view_name)
    seo_og_title = f"{page_title} | {site_name}" if page_title else site_name
    seo_meta_description = static_descriptions.get(
        view_name,
        settings.SEO_DEFAULT_DESCRIPTION,
    )

    return {
        "SITE_NAME": site_name,
        "SITE_URL": site_url,
        "SEO_DEFAULT_DESCRIPTION": settings.SEO_DEFAULT_DESCRIPTION,
        "canonical_url": request.build_absolute_uri(request.path),
        "seo_og_title": seo_og_title,
        "seo_meta_description": seo_meta_description,
    }
