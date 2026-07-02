"""Production SEO and performance optimizations."""

import pytest
from django.urls import reverse


PUBLIC_INDEXABLE = (
    "core:home",
    "products:product_list",
    "core:about",
    "core:contact",
    "careers:careers",
)

PRIVATE_NOINDEX = (
    "core:cart",
    "core:checkout",
    "accounts:login",
    "accounts:register",
)


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", PUBLIC_INDEXABLE)
def test_public_pages_are_indexable_with_seo_tags(client, url_name):
    response = client.get(reverse(url_name))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'name="robots" content="index, follow"' in content
    assert 'property="og:title"' in content
    assert 'name="twitter:card"' in content
    assert 'rel="canonical"' in content
    assert 'application/ld+json' in content


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", PRIVATE_NOINDEX)
def test_private_flow_pages_are_noindex(client, url_name):
    if url_name == "core:checkout":
        pytest.skip("Checkout redirects when cart is empty")
    response = client.get(reverse(url_name))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'name="robots" content="noindex, nofollow"' in content


@pytest.mark.django_db
def test_home_preloads_hero_poster(client):
    content = client.get(reverse("core:home")).content.decode()

    assert 'rel="preload" as="image"' in content
    assert "1727928" in content
    assert 'fetchpriority="high"' in content


@pytest.mark.django_db
def test_home_hero_video_uses_metadata_preload(client):
    content = client.get(reverse("core:home")).content.decode()

    assert 'preload="metadata"' in content


@pytest.mark.django_db
def test_shop_page_has_menu_structured_data(client):
    content = client.get(reverse("products:product_list")).content.decode()

    assert '"@type": "Menu"' in content
    assert "کوکی" in content


@pytest.mark.django_db
def test_product_detail_has_product_structured_data(client, product):
    response = client.get(product.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert '"@type": "Product"' in content
    assert '"@type": "BreadcrumbList"' in content
    assert 'fetchpriority="high"' in content
    assert 'loading="lazy"' not in content.split("product-detail-media")[1].split("product-detail-info")[0]


@pytest.mark.django_db
def test_product_cards_lazy_load_images(client, product):
    from django.core.cache import cache
    from django.core.files.uploadedfile import SimpleUploadedFile

    cache.clear()
    product.image.save(
        "cookie.jpg",
        SimpleUploadedFile("cookie.jpg", b"fake-image", content_type="image/jpeg"),
        save=True,
    )
    content = client.get(reverse("products:product_list")).content.decode()

    assert product.name in content
    assert 'loading="lazy"' in content
    assert 'decoding="async"' in content


@pytest.mark.django_db
def test_fonts_load_non_blocking(client):
    content = client.get(reverse("core:home")).content.decode()

    assert 'rel="preload" as="style"' in content
    assert "Vazirmatn" in content
    assert 'media="print" onload="this.media=\'all\'"' in content


@pytest.mark.django_db
def test_site_structured_data_includes_restaurant_and_organization(client):
    content = client.get(reverse("core:home")).content.decode()

    assert '"@type": "Restaurant"' in content
    assert '"@type": "Organization"' in content
    assert '"@type": "WebSite"' in content
    assert "021-1234-5678" in content


@pytest.mark.django_db
def test_account_pages_skip_structured_data(client, user):
    client.force_login(user)
    content = client.get(reverse("accounts:profile")).content.decode()

    assert 'name="robots" content="noindex, nofollow"' in content
    assert "application/ld+json" not in content


@pytest.mark.django_db
def test_header_logo_is_high_priority_not_lazy(client):
    content = client.get(reverse("core:home")).content.decode()

    header_start = content.index('id="site-header"')
    header_end = content.index("</header>", header_start)
    header = content[header_start:header_end]
    assert 'fetchpriority="high"' in header
    assert 'loading="lazy"' not in header
