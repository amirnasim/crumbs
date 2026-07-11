"""Public storefront UI — branding, navigation, and layout polish."""

import pytest
from django.urls import reverse


PUBLIC_PAGES = (
    "core:home",
    "products:product_list",
    "core:about",
    "core:contact",
    "careers:careers",
    "core:cart",
)


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", PUBLIC_PAGES)
def test_public_pages_have_header_script_logo(client, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code == 200
    content = response.content.decode()

    assert "brand-logo--header" in content
    assert "crumbs-logo.png" in content
    assert "crumbs-logo-on-dark.png" not in content
    assert "header-brand" in content
    assert "header-nav" in content
    assert "brand-wordmark--header" not in content
    assert "Cookies & Coffee" not in content
    assert "theme-toggle" not in content


@pytest.mark.django_db
def test_mobile_header_shows_cart_count(client):
    content = client.get(reverse("core:home")).content.decode()

    assert "header-cart-count" in content
    assert "header-cart-count__value" in content
    assert "(0)" in content


@pytest.mark.django_db
def test_header_has_hamburger_toggle(client):
    content = client.get(reverse("core:home")).content.decode()

    assert 'id="nav-toggle"' in content
    assert "nav-toggle__close" in content
    assert 'id="menu-drawer-close"' not in content
    assert 'aria-label="باز کردن منو"' in content


@pytest.mark.django_db
def test_drawer_matches_fullscreen_reference_layout(client):
    content = client.get(reverse("core:home")).content.decode()
    drawer_start = content.index('id="menu-drawer"')
    drawer_end = content.index("</aside>", drawer_start)
    drawer = content[drawer_start:drawer_end]

    assert drawer.count("crumbs-logo.png") == 0
    assert "crumbs-logo-on-dark.png" not in drawer
    assert "brand-logo--header" not in drawer
    assert "menu-drawer__brand" not in drawer
    assert "menu-drawer__bar" not in drawer
    assert "menu-drawer__zone--middle" in drawer
    assert "menu-drawer__zone--bottom" in drawer
    assert "menu-drawer__zone--top" not in drawer
    assert "menu-drawer__subtitle" not in drawer
    assert "menu-drawer__contact-line" in drawer
    assert "menu-drawer__contact-icon" not in drawer
    assert "menu-drawer__account" not in drawer
    assert "خلاصه سبد" not in drawer
    assert ">CRUMBS<" not in drawer
    assert "Cookies & Coffee" not in drawer
    assert "021-1234-5678" in drawer
    assert "بلوار فرمانیه، ساختمان آرتا" in drawer
    assert "هر روز 07:30 – 22:30" in drawer
    assert "@crumbs.cafe" in drawer
    assert "menu-drawer__footer" in drawer
    assert "menu-drawer__credit" in drawer
    assert "Crumbs · Tehran" in drawer
    assert "Designed by Amirhossein Nasimi" in drawer
    assert "site-credit" not in drawer
    for label in ("خانه", "منو", "داستان ما", "تماس با ما", "همکاری با ما", "حساب من"):
        assert label in drawer
    assert 'data-nav="/cart"' not in drawer
    assert "سبد خرید" not in drawer


@pytest.mark.django_db
def test_homepage_hero_is_media_only(client):
    content = client.get(reverse("core:home")).content.decode()

    assert "story-hero__scroll" not in content
    assert "Fresh Cookies. Real Ingredients." not in content
    assert "story-hero__wordmark" not in content
    assert "Enter the Bakery" not in content


@pytest.mark.django_db
def test_premium_footer_uses_text_wordmark_only(client):
    content = client.get(reverse("core:home")).content.decode()
    footer_start = content.index("site-footer--premium")
    footer = content[footer_start:]

    assert "footer-wordmark" in footer
    assert "footer-tagline" in footer
    assert "کافه و بیکری دست‌ساز" in footer
    assert '<h2 class="footer-wordmark"' in footer
    assert '<p class="footer-tagline">' in footer
    assert "crumbs-logo.png" not in footer
    assert "Designed by Amirhossein Nasimi" in footer
    assert "Crumbs · Tehran" in footer


@pytest.mark.django_db
def test_footer_brand_block_css_hierarchy():
    from pathlib import Path

    from django.conf import settings

    css_path = Path(settings.BASE_DIR) / "static" / "css" / "crumbs.css"
    css = css_path.read_text(encoding="utf-8")

    assert ".footer-brand {" in css
    assert "align-items: flex-end" in css
    assert ".footer-tagline {" in css
    tagline_block = css[css.index(".footer-tagline {") : css.index(".footer-wordmark {")]
    assert "0.8125rem" in tagline_block
    assert "var(--weight-light)" in tagline_block
    assert "0.75)" in tagline_block
    wordmark_block = css[css.index(".footer-wordmark {") : css.index(".site-footer--premium .footer-tagline")]
    assert "0.875rem" in wordmark_block


@pytest.mark.django_db
def test_about_page_shows_establishment_year(client):
    response = client.get(reverse("core:about"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "تأسیس ۱۴۰۵" in content
    assert "تأسیس ۱۴۰۳" not in content


@pytest.mark.django_db
def test_interior_pages_do_not_repeat_logo_in_hero(client):
    for url_name in ("core:about", "core:contact", "careers:careers"):
        content = client.get(reverse(url_name)).content.decode()
        main_start = content.index('id="main-content"')
        main_end = content.index("</main>", main_start)
        main = content[main_start:main_end]

        assert main.count("crumbs-logo.png") == 0


@pytest.mark.django_db
def test_shop_page_has_persian_hero_and_category_nav(client):
    content = client.get(reverse("products:product_list")).content.decode()

    assert "منوی کافه" in content
    assert "کوکی" in content
    assert "قهوه" in content
    assert "page-shop" in content
