"""Legacy core → careers migration history safety checks."""

from io import StringIO
from pathlib import Path

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.migrations.loader import MigrationLoader

from careers.models import CareerApplication
from core.migration_history_checks import (
    EXPECTED_CAREERS_MIGRATIONS,
    EXPECTED_CORE_MIGRATIONS,
    run_migration_history_checks,
    verify_migration_files,
    verify_migration_graph,
    verify_model_registry,
)


@pytest.mark.django_db
class TestMigrationHistoryModels:
    def test_core_has_no_career_application_model(self):
        with pytest.raises(LookupError):
            apps.get_app_config("core").get_model("CareerApplication")

    def test_careers_career_application_model_exists(self):
        model = apps.get_model("careers", "CareerApplication")
        assert model is CareerApplication
        assert model._meta.db_table == "careers_careerapplication"


@pytest.mark.django_db
class TestMigrationHistoryFiles:
    def test_core_legacy_migration_files_exist(self):
        apps_root = Path(settings.BASE_DIR) / "apps"
        for migration_name in EXPECTED_CORE_MIGRATIONS:
            path = apps_root / "core" / "migrations" / f"{migration_name}.py"
            assert path.is_file(), f"missing {path}"

    def test_careers_migration_files_exist(self):
        apps_root = Path(settings.BASE_DIR) / "apps"
        for migration_name in EXPECTED_CAREERS_MIGRATIONS:
            path = apps_root / "careers" / "migrations" / f"{migration_name}.py"
            assert path.is_file(), f"missing {path}"


@pytest.mark.django_db
class TestMigrationHistoryGraph:
    def test_migration_graph_includes_core_and_careers_migrations(self):
        loader = MigrationLoader(None, ignore_no_migrations=False)
        errors = verify_migration_graph(loader)
        assert errors == []

    def test_showmigrations_lists_expected_core_migrations(self):
        loader = MigrationLoader(None, ignore_no_migrations=False)
        core_names = sorted(name for app, name in loader.disk_migrations if app == "core")
        assert core_names == list(EXPECTED_CORE_MIGRATIONS)

    def test_showmigrations_lists_expected_careers_migrations(self):
        loader = MigrationLoader(None, ignore_no_migrations=False)
        careers_names = sorted(name for app, name in loader.disk_migrations if app == "careers")
        assert careers_names == list(EXPECTED_CAREERS_MIGRATIONS)


@pytest.mark.django_db
class TestMigrationHistoryChecks:
    def test_run_migration_history_checks_passes(self):
        assert run_migration_history_checks() == []

    def test_verify_model_registry_passes(self):
        assert verify_model_registry() == []

    def test_verify_migration_files_passes(self):
        assert verify_migration_files() == []

    def test_check_migration_history_command_succeeds(self):
        out = StringIO()
        call_command("check_migration_history", stdout=out)
        assert "Migration history OK" in out.getvalue()

    def test_check_migration_history_command_fails_on_errors(self, mocker):
        mocker.patch(
            "core.management.commands.check_migration_history.run_migration_history_checks",
            return_value=["example migration history error"],
        )
        with pytest.raises(CommandError, match="Migration history check failed"):
            call_command("check_migration_history")
