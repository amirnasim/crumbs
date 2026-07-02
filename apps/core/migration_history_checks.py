"""Safety checks for legacy core → careers migration history."""

from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db.migrations.loader import MigrationLoader

EXPECTED_CORE_MIGRATIONS = (
    "0001_background_tasks",
    "0002_career_application",
    "0003_delete_careerapplication",
    "0004_persian_verbose_names",
)

EXPECTED_CAREERS_MIGRATIONS = (
    "0001_initial",
    "0002_remove_social_urls",
    "0003_cafe_hiring_fields",
    "0004_persian_positions",
    "0005_cafe_hiring_form_update",
    "0006_align_model_verbose_names",
    "0007_positions_and_required_email",
)


def _apps_dir() -> Path:
    return Path(settings.BASE_DIR) / "apps"


def verify_model_registry() -> list[str]:
    errors: list[str] = []

    try:
        apps.get_app_config("core").get_model("CareerApplication")
    except LookupError:
        pass
    else:
        errors.append("core.CareerApplication must not be registered in the current model registry.")

    try:
        model = apps.get_model("careers", "CareerApplication")
    except LookupError:
        errors.append("careers.CareerApplication is missing from the model registry.")
    else:
        if model._meta.db_table != "careers_careerapplication":
            errors.append(
                "careers.CareerApplication uses unexpected db_table "
                f"{model._meta.db_table!r} (expected 'careers_careerapplication')."
            )

    return errors


def verify_migration_files() -> list[str]:
    errors: list[str] = []
    apps_root = _apps_dir()

    for migration_name in EXPECTED_CORE_MIGRATIONS:
        path = apps_root / "core" / "migrations" / f"{migration_name}.py"
        if not path.is_file():
            errors.append(f"Missing migration file: core/migrations/{migration_name}.py")

    for migration_name in EXPECTED_CAREERS_MIGRATIONS:
        path = apps_root / "careers" / "migrations" / f"{migration_name}.py"
        if not path.is_file():
            errors.append(f"Missing migration file: careers/migrations/{migration_name}.py")

    return errors


def verify_migration_graph(loader: MigrationLoader | None = None) -> list[str]:
    errors: list[str] = []
    loader = loader or MigrationLoader(None, ignore_no_migrations=False)

    for migration_name in EXPECTED_CORE_MIGRATIONS:
        key = ("core", migration_name)
        if key not in loader.disk_migrations:
            errors.append(f"Migration graph missing core.{migration_name}")

    for migration_name in EXPECTED_CAREERS_MIGRATIONS:
        key = ("careers", migration_name)
        if key not in loader.disk_migrations:
            errors.append(f"Migration graph missing careers.{migration_name}")

    return errors


def run_migration_history_checks() -> list[str]:
    errors: list[str] = []
    errors.extend(verify_model_registry())
    errors.extend(verify_migration_files())
    errors.extend(verify_migration_graph())
    return errors
