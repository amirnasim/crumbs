from django.core.management.base import BaseCommand, CommandError

from core.migration_history_checks import run_migration_history_checks


class Command(BaseCommand):
    help = (
        "Verify legacy core/careers migration history: model registry, migration files, "
        "and migration graph."
    )

    def handle(self, *args, **options):
        errors = run_migration_history_checks()
        if errors:
            for message in errors:
                self.stderr.write(self.style.ERROR(message))
            raise CommandError(f"Migration history check failed ({len(errors)} issue(s)).")

        self.stdout.write(
            self.style.SUCCESS(
                "Migration history OK: core has no CareerApplication model; "
                "careers.CareerApplication exists; core 0001–0003 and careers 0001–0007 "
                "migrations are present."
            )
        )
