"""Health and readiness endpoint tests."""

import json

import pytest
from django.test import Client, override_settings


@pytest.fixture
def health_client():
    return Client()


@pytest.mark.django_db
class TestHealthLiveness:
    def test_health_returns_200_without_db_checks(self, health_client):
        response = health_client.get("/health/")

        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "status": "ok",
            "service": "crumbs",
            "type": "liveness",
        }

    def test_health_does_not_import_database_on_request(self, health_client, mocker):
        ensure = mocker.patch("django.db.connection.ensure_connection")

        response = health_client.get("/health/")

        assert response.status_code == 200
        ensure.assert_not_called()


@pytest.mark.django_db
class TestReadinessCheck:
    def test_ready_returns_200_with_expected_checks(self, health_client, mocker):
        mocker.patch("core.health_views._check_database", return_value=("ok", True))
        mocker.patch("core.health_views._check_redis", return_value=("skipped", True))
        mocker.patch("core.health_views._check_celery_broker", return_value=("skipped", True))
        mocker.patch("core.health_views._check_migrations", return_value=("ok", True))

        response = health_client.get("/ready/")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ready"
        assert payload["type"] == "readiness"
        assert payload["service"] == "crumbs"
        assert payload["ready"] is True
        assert set(payload["checks"]) == {
            "database",
            "redis",
            "celery_broker",
            "migrations",
        }
        assert payload["checks"]["database"] == "ok"
        assert payload["checks"]["migrations"] == "ok"

    def test_ready_returns_503_when_database_check_fails(self, health_client, mocker):
        mocker.patch(
            "core.health_views._check_database",
            return_value=("error", False),
        )
        mocker.patch(
            "core.health_views._check_redis",
            return_value=("ok", True),
        )
        mocker.patch(
            "core.health_views._check_celery_broker",
            return_value=("ok", True),
        )
        mocker.patch(
            "core.health_views._check_migrations",
            return_value=("ok", True),
        )

        response = health_client.get("/ready/")

        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "not_ready"
        assert payload["checks"]["database"] == "error"

    def test_ready_returns_503_when_redis_check_fails(self, health_client, mocker):
        mocker.patch(
            "core.health_views._check_database",
            return_value=("ok", True),
        )
        mocker.patch(
            "core.health_views._check_redis",
            return_value=("error", False),
        )
        mocker.patch(
            "core.health_views._check_celery_broker",
            return_value=("ok", True),
        )
        mocker.patch(
            "core.health_views._check_migrations",
            return_value=("ok", True),
        )

        response = health_client.get("/ready/")

        assert response.status_code == 503
        assert response.json()["checks"]["redis"] == "error"

    @override_settings(REDIS_URL="")
    def test_ready_skips_redis_when_not_configured(self, health_client, mocker):
        mocker.patch("core.health_views._check_database", return_value=("ok", True))
        mocker.patch("core.health_views._check_celery_broker", return_value=("skipped", True))
        mocker.patch("core.health_views._check_migrations", return_value=("ok", True))

        response = health_client.get("/ready/")

        assert response.status_code == 200
        assert response.json()["checks"]["redis"] == "skipped"


@pytest.mark.django_db
class TestHealthFull:
    def test_health_full_disabled_by_default_in_non_debug(self, health_client, settings):
        settings.DEBUG = False

        response = health_client.get("/health/full/")

        assert response.status_code == 404

    @override_settings(DEBUG=True)
    def test_health_full_returns_extended_payload_when_enabled(self, health_client, mocker):
        mocker.patch("core.health_views._check_database", return_value=("ok", True))
        mocker.patch("core.health_views._check_redis", return_value=("skipped", True))
        mocker.patch("core.health_views._check_celery_broker", return_value=("skipped", True))
        mocker.patch("core.health_views._check_migrations", return_value=("ok", True))

        response = health_client.get("/health/full/")

        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "full"
        assert payload["service"] == "crumbs"
        assert "environment" in payload
        assert "database_vendor" in payload
        assert "checks" in payload
        assert "debug" in payload
        assert "SECRET" not in json.dumps(payload).upper()
