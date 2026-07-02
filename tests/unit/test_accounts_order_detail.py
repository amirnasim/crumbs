import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from orders.models import Order
from tests.factories import create_order, create_product, create_user

User = get_user_model()


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def owner(db):
    return create_user(username="owner", email="owner@example.com")


@pytest.fixture
def other_user(db):
    return create_user(username="other", email="other@example.com")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="pass12345",
        is_staff=True,
    )


@pytest.fixture
def order(owner, product):
    return create_order(owner, product)


@pytest.mark.django_db
class TestOrderDetailAccess:
    def test_owner_can_view_order_detail(self, client, owner, order):
        client.force_login(owner)

        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))

        assert response.status_code == 200
        assert order.order_number.encode() in response.content

    def test_other_user_cannot_view_order(self, client, other_user, order):
        client.force_login(other_user)

        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_anonymous_user_redirected_to_login_without_session(self, client, order):
        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_anonymous_user_with_session_can_view_counter_order(self, client, user, product):
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.CASH,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.AWAITING_PAYMENT,
        )
        session = client.session
        session["checkout_order_access"] = [order.order_number]
        session.save()

        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))

        assert response.status_code == 200
        assert order.order_number.encode() in response.content

    def test_staff_can_view_any_order(self, client, staff_user, owner, order):
        client.force_login(staff_user)

        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))

        assert response.status_code == 200
        assert order.order_number.encode() in response.content


@pytest.mark.django_db
class TestOrderDetailContent:
    def test_order_items_and_totals_displayed(self, client, owner, order, product):
        client.force_login(owner)

        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))

        assert response.status_code == 200
        content = response.content.decode()
        item = order.items.first()
        assert item is not None
        assert product.name in content
        assert order.email in content
        assert order.phone in content
        assert str(item.quantity) in content
        assert "جمع جزء" in content
        assert response.context["order"].subtotal == order.subtotal

    def test_order_list_links_to_detail(self, client, owner, order):
        client.force_login(owner)

        response = client.get(reverse("accounts:order_list"))

        assert response.status_code == 200
        detail_url = reverse("accounts:order_detail", args=[order.order_number])
        assert detail_url in response.content.decode()
