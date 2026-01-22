"""Django management command for importing OpenSLO YAML files."""
from pathlib import Path

from requirements.openslo import OpenSLOParser, import_slos_to_database

from .base import BaseImportCommand


class Command(BaseImportCommand):
    """Import SLOs from OpenSLO YAML files."""

    help = 'Import SLOs from OpenSLO YAML files'
    path_argument_name = 'slos_dir'
    path_argument_help = 'Path to directory containing OpenSLO YAML files'

    def do_import(self, path: Path, options: dict):
        """Execute the import workflow."""
        self.stdout.write(f"Parsing OpenSLO files from {path}...")

        parser = OpenSLOParser()
        slos = parser.parse_directory(path)

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
