"""Cart and checkout in-cafe UX — wording and flow."""

import pytest
from django.test import Client
from django.urls import reverse

from tests.factories import create_cart_with_item, create_user

FORBIDDEN_CART_CHECKOUT_TERMS = (
    "delivery",
    "courier",
    "shipping",
    "پیک",
    "ارسال",
    "روش ارسال",
    "آدرس تحویل",
    "آدرس",
    "شهر",
    "کد پستی",
    "هزینه ارسال",
    "delivery fee",
    "delivery zone",
)

OLD_CHECKOUT_PROGRESS_LABELS = (
    "مراحل پرداخت",
    'checkout-progress__label">سبد<',
    'checkout-progress__label">تأیید<',
    'checkout-progress__label">اطلاعات<',
    'checkout-progress__label">پرداخت<',
)

CAFE_CHECKOUT_STEPS = (
    "اطلاعات سفارش",
    "روش پرداخت",
    "بررسی و ثبت سفارش",
)

CAFE_PAYMENT_LABELS = (
    "پرداخت آنلاین",
    "پرداخت با کارت در صندوق",
    "پرداخت نقدی در صندوق",
)


def _main_content(html: str) -> str:
    start = html.index('id="main-content"')
    end = html.index("</main>", start)
    return html[start:end]


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
class TestCartInCafeUX:
    def test_cart_page_has_new_cta_and_cafe_note(self, client, user, product):
        create_cart_with_item(user, product)
        client.force_login(user)

        response = client.get(reverse("core:cart"))
        content = _main_content(response.content.decode())

        assert response.status_code == 200
        assert "ادامه سفارش و پرداخت" in content
        assert "سفارش شما در کافه آماده می‌شود و از کانتر تحویل می‌گیرید." in content
        for term in FORBIDDEN_CART_CHECKOUT_TERMS:
            assert term not in content

    def test_cart_page_has_no_checkout_wizard_steps(self, client, user, product):
        create_cart_with_item(user, product)
        client.force_login(user)

        response = client.get(reverse("core:cart"))
        content = response.content.decode()

        assert "checkout-progress" not in content
        for label in OLD_CHECKOUT_PROGRESS_LABELS:
            assert label not in content

    def test_cart_shows_table_banner_from_session(self, client, user, product):
        create_cart_with_item(user, product)
        client.force_login(user)
        client.get("/shop/?table=01")

        response = client.get(reverse("core:cart"))
        content = response.content.decode()

        assert response.status_code == 200
        assert "میز شما:" in content
        assert "01" in content


@pytest.mark.django_db
class TestCheckoutInCafeUX:
    def test_checkout_shows_three_cafe_steps_only(self, client, user, product):
        create_cart_with_item(user, product)
        client.force_login(user)

        response = client.get(reverse("core:checkout"))
        content = response.content.decode()

        assert response.status_code == 200
        for step in CAFE_CHECKOUT_STEPS:
            assert step in content
        assert content.count("checkout-progress__step") == 3

    def test_checkout_has_no_old_payment_delivery_step_labels(self, client, user, product):
        create_cart_with_item(user, product)
        client.force_login(user)

        response = client.get(reverse("core:checkout"))
        content = _main_content(response.content.decode())

        for label in OLD_CHECKOUT_PROGRESS_LABELS:
            assert label not in content
        for term in FORBIDDEN_CART_CHECKOUT_TERMS:
            assert term not in content

    def test_checkout_payment_method_labels_are_persian_and_cafe_focused(self, client, user, product):
        create_cart_with_item(user, product)
        client.force_login(user)

        response = client.get(reverse("core:checkout"))
        content = response.content.decode()

        for label in CAFE_PAYMENT_LABELS:
            assert label in content

    def test_checkout_review_does_not_show_delivery_fee_or_address(self, client, user, product):
        create_cart_with_item(user, product)
        client.force_login(user)

        response = client.get(reverse("core:checkout"))
        content = _main_content(response.content.decode())

        assert "جمع جزء" in content
        assert "مجموع" in content
        assert "میز / یادداشت" in content
        assert "روش پرداخت" in content
        assert "هزینه ارسال" not in content
        assert "آدرس" not in content
        assert "شهر" not in content
        assert "کد پستی" not in content

    def test_checkout_table_banner_still_works(self, client, user, product):
        create_cart_with_item(user, product)
        client.get("/shop/?table=03")
        client.force_login(user)

        response = client.get(reverse("core:checkout"))
        content = response.content.decode()

        assert response.status_code == 200
        assert "میز شما:" in content
        assert "03" in content
