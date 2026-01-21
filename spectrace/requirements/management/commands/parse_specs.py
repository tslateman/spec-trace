"""Django management command for parsing spec files and importing requirements."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from requirements.parser import SpecParser


class Command(BaseCommand):
    """Parse markdown spec files and import requirements into database."""

    help = 'Parse markdown spec files and import requirements into database'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            'specs_dir',
            type=str,
            help='Path to specs directory (e.g., specs/)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing requirements before import'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and validate without saving to database'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        specs_dir = Path(options['specs_dir'])

        if not specs_dir.exists():
            raise CommandError(f"Specs directory not found: {specs_dir}")

        if not specs_dir.is_dir():
            raise CommandError(f"Path is not a directory: {specs_dir}")

        parser = SpecParser()

        if options['dry_run']:
            requirements = parser.parse_directory(specs_dir)
            self.stdout.write(f"Found {len(requirements)} requirements:")
            for req in requirements:
                parent_info = f" (parent: {req['parent_id']})" if req['parent_id'] else ""
                self.stdout.write(f"  {req['external_id']}: {req['title']}{parent_info}")
            return

        count = parser.import_to_database(
            specs_dir,
            clear_existing=options['clear']
        )
        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported {count} requirements")
        )
