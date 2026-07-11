"""Customer order status timeline mapping and display."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from orders.customer_status import (
    COUNTER_AWAITING_PAYMENT_MESSAGE,
    CUSTOMER_TIMELINE_STEPS,
    PACKAGED_READY_MESSAGE,
    TIMELINE_STEP_AWAITING_PAYMENT,
    TIMELINE_STEP_DELIVERED,
    TIMELINE_STEP_PREPARING,
    TIMELINE_STEP_READY,
    build_order_status_timeline,
    map_order_status_to_timeline_key,
)
from orders.models import Order
from tests.factories import create_order, create_user


@pytest.mark.parametrize(
    ("status", "expected_key"),
    [
        (Order.Status.AWAITING_PAYMENT, TIMELINE_STEP_AWAITING_PAYMENT),
        (Order.Status.PENDING_PAYMENT, TIMELINE_STEP_AWAITING_PAYMENT),
        (Order.Status.PAID, TIMELINE_STEP_PREPARING),
        (Order.Status.CONFIRMED_BY_SHOP, TIMELINE_STEP_PREPARING),
        (Order.Status.PREPARING, TIMELINE_STEP_PREPARING),
        (Order.Status.PACKAGED, TIMELINE_STEP_READY),
        (Order.Status.DELIVERED, TIMELINE_STEP_DELIVERED),
        (Order.Status.CANCELLED, None),
    ],
)
def test_map_order_status_to_timeline_key(status, expected_key):
    assert map_order_status_to_timeline_key(status) == expected_key


@pytest.mark.django_db
def test_build_timeline_marks_current_and_completed_steps(product):
    user = create_user(username="timeline-user")
    order = create_order(
        user,
        product,
        status=Order.Status.PREPARING,
        payment_status=Order.PaymentStatus.PAID,
    )

    timeline = build_order_status_timeline(order)

    assert timeline.current_key == TIMELINE_STEP_PREPARING
    assert timeline.steps[0].state == "complete"
    assert timeline.steps[1].state == "current"
    assert timeline.steps[2].state == "upcoming"
    assert timeline.steps[3].state == "upcoming"
    assert timeline.banner == ""


@pytest.mark.django_db
def test_counter_awaiting_payment_shows_counter_banner(product):
    user = create_user(username="counter-user")
    order = create_order(
        user,
        product,
        status=Order.Status.AWAITING_PAYMENT,
        payment_status=Order.PaymentStatus.PENDING_PAYMENT,
        payment_method=Order.PaymentMethod.CASH,
    )

    timeline = build_order_status_timeline(order)

    assert timeline.current_key == TIMELINE_STEP_AWAITING_PAYMENT
    assert timeline.banner == COUNTER_AWAITING_PAYMENT_MESSAGE


@pytest.mark.django_db
def test_packaged_order_shows_ready_banner(product):
    user = create_user(username="ready-user")
    order = create_order(
        user,
        product,
        status=Order.Status.PACKAGED,
        payment_status=Order.PaymentStatus.PAID,
    )

    timeline = build_order_status_timeline(order)

    assert timeline.current_key == TIMELINE_STEP_READY
    assert timeline.banner == PACKAGED_READY_MESSAGE


@pytest.mark.django_db
def test_timeline_has_four_persian_steps():
    assert len(CUSTOMER_TIMELINE_STEPS) == 4
    labels = [label for _, label in CUSTOMER_TIMELINE_STEPS]
    assert "در انتظار پرداخت" in labels
    assert "در حال آماده‌سازی" in labels
    assert "آماده تحویل از کانتر" in labels
    assert "آماده تحویل از کانتر" in labels
    assert "تحویل شد" in labels


@pytest.fixture
def client():
    return Client()


def _timeline_section(html: str) -> str:
    start = html.index('class="order-status-timeline"')
    end = html.index("</ol>", start)
    return html[start:end]


@pytest.mark.django_db
class TestOrderStatusTimelineLayout:
    def test_timeline_css_uses_grid_marker_column(self):
        css_path = Path(settings.BASE_DIR) / "static" / "css" / "crumbs.css"
        css = css_path.read_text(encoding="utf-8")

        assert ".order-status-timeline__step {" in css
        assert "grid-template-columns: 1.25rem minmax(0, 1fr)" in css
        assert "column-gap: 0.75rem" in css
        assert ".order-status-timeline__marker" in css
        assert ".order-status-timeline__label" in css
        assert ".order-status-timeline__step::before" not in css
        assert "padding-right: var(--space-5)" not in re.search(
            r"\.order-status-timeline__step\s*\{[^}]+\}",
            css,
            re.DOTALL,
        ).group(0)

    def test_confirmation_timeline_has_marker_and_label_columns(self, client, product):
        user = create_user(username="layout-confirm")
        order = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
        )
        session = client.session
        session["checkout_order_access"] = [order.order_number]
        session.save()

        response = client.get(reverse("core:order_confirmation", args=[order.order_number]))
        timeline = _timeline_section(response.content.decode())

        assert response.status_code == 200
        assert timeline.count("order-status-timeline__marker") == 4
        assert timeline.count("order-status-timeline__label") == 4
        assert 'order-status-timeline__step--' in timeline
        assert "position: absolute" not in timeline

    def test_order_detail_timeline_has_marker_and_label_columns(self, client, product):
        user = create_user(username="layout-detail")
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
        )
        client.force_login(user)

        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))
        timeline = _timeline_section(response.content.decode())

        assert response.status_code == 200
        assert timeline.count("order-status-timeline__marker") == 4
        assert timeline.count("order-status-timeline__label") == 4
        assert "در حال آماده‌سازی" in timeline


@pytest.mark.django_db
class TestOrderStatusTimelineDisplay:
    def test_confirmation_page_shows_timeline_steps(self, client, product):
        user = create_user(username="guest-timeline")
        order = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        session = client.session
        session["checkout_order_access"] = [order.order_number]
        session.save()

        response = client.get(reverse("core:order_confirmation", args=[order.order_number]))

        content = response.content.decode()
        assert response.status_code == 200
        assert "order-status-timeline" in content
        assert PACKAGED_READY_MESSAGE in content
        assert "آماده تحویل از کانتر" in content

    def test_order_detail_shows_timeline_for_logged_in_user(self, client, product):
        user = create_user(username="detail-timeline")
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
        )
        client.force_login(user)

        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))

        content = response.content.decode()
        assert response.status_code == 200
        assert "در حال آماده‌سازی" in content
