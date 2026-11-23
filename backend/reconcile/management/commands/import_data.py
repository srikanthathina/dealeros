from django.core.management.base import BaseCommand, CommandError

from reconcile.importer import ImportDataError, import_data


class Command(BaseCommand):
    help = "Import locations and records from backend/data CSV files."

    def handle(self, *args, **options):
        try:
            counts = import_data()
        except (ImportDataError, OSError) as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Locations: {counts['locations']} read, {counts['locations']} saved; "
                f"System A: {counts['system_a']} read, {counts['system_a_saved']} saved "
                f"({counts['blank_actor_ids']} blank actor IDs); "
                f"System B: {counts['system_b']} read, {counts['system_b_saved']} saved "
                f"({counts['blank_values']} blank values, "
                f"{counts['normalized_refs']} normalized references)."
            )
        )
