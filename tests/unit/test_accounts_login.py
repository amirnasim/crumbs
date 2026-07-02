"""Public login UX — phone-first identifier prepared for SMS auth."""

import pytest
from django.urls import reverse

from tests.factories import create_user


@pytest.fixture
def client():
    from django.test import Client

    return Client()


@pytest.mark.django_db
class TestLoginPageUX:
    def test_login_page_shows_phone_label(self, client):
        response = client.get(reverse("accounts:login"))
        content = response.content.decode()

        assert response.status_code == 200
        assert "شماره تلفن همراه" in content
        assert 'placeholder="مثلاً 09123456789"' in content

    def test_login_page_does_not_show_email_wording(self, client):
        response = client.get(reverse("accounts:login"))
        content = response.content.decode()

        assert "Email" not in content
        assert ">ایمیل<" not in content
        assert "for=\"id_email\"" not in content

    def test_login_with_username_still_works(self, client):
        user = create_user(username="buyer", password="pass12345")

        response = client.post(
            reverse("accounts:login"),
            {"username": user.username, "password": "pass12345"},
        )

        assert response.status_code == 302
        assert str(client.session["_auth_user_id"]) == str(user.pk)

    def test_login_with_profile_phone_resolves_to_username(self, client):
        user = create_user(username="phoneuser", password="pass12345", phone="09125556677")

        response = client.post(
            reverse("accounts:login"),
            {"username": "09125556677", "password": "pass12345"},
        )

        assert response.status_code == 302
        assert str(client.session["_auth_user_id"]) == str(user.pk)

    def test_login_prepared_sms_labels_present_in_template(self, client):
        response = client.get(reverse("accounts:login"))
        content = response.content.decode()

        assert "ورود با پیامک" in content
        assert "ارسال کد تأیید" in content
        assert "کد تأیید پیامکی" in content
