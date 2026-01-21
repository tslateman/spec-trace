"""Django management command for importing OpenSLO YAML files."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from requirements.openslo import OpenSLOParser, import_slos_to_database


class Command(BaseCommand):
    """Import SLOs from OpenSLO YAML files."""

    help = 'Import SLOs from OpenSLO YAML files'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            'slos_dir',
            type=str,
            help='Path to directory containing OpenSLO YAML files'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing SLOs before import'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse files but do not import to database'
        )

    def handle(self, *args, **options):
        """Execute the import workflow."""
        slos_dir = Path(options['slos_dir'])
        if not slos_dir.exists():
            raise CommandError(f"Directory not found: {slos_dir}")
        if not slos_dir.is_dir():
            raise CommandError(f"Not a directory: {slos_dir}")

        self.stdout.write(f"Parsing OpenSLO files from {slos_dir}...")

        parser = OpenSLOParser()
        slos = parser.parse_directory(slos_dir)

        if not slos:
            self.stdout.write(self.style.WARNING("No OpenSLO files found"))
            return

        self.stdout.write(f"Found {len(slos)} SLO(s)")

        for slo in slos:
            req_count = len(slo.get('requirement_ids', []))
            target = slo.get('target')
            target_str = f"{float(target) * 100:.2f}%" if target else 'N/A'
            self.stdout.write(
                f"  - {slo['name']}: target={target_str}, "
                f"linked_requirements={req_count}"
            )

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS("Dry run complete - no changes made"))
            return

        # Import to database
        created = import_slos_to_database(
            slos,
            clear_existing=options['clear']
        )

        self.stdout.write(self.style.SUCCESS(
            f"Import complete: {created} new SLO(s) created, "
            f"{len(slos) - created} updated"
        ))
