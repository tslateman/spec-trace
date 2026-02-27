"""Django management command for parsing spec files and importing requirements."""

from pathlib import Path

from requirements.parser import SpecParser

from .base import BaseImportCommand


class Command(BaseImportCommand):
    """Parse markdown spec files and import requirements into database."""

    help = "Parse markdown spec files and import requirements into database"
    path_argument_name = "specs_dir"
    path_argument_help = "Path to specs directory (e.g., specs/)"

    def do_import(self, path: Path, options: dict):
        """Execute the import."""
        parser = SpecParser()

        if options["dry_run"]:
            requirements = parser.parse_directory(path)
            self.stdout.write(f"Found {len(requirements)} requirements:")
            for req in requirements:
                parent_info = f" (parent: {req['parent_id']})" if req["parent_id"] else ""
                self.stdout.write(f"  {req['external_id']}: {req['title']}{parent_info}")
            return

        count = parser.import_to_database(path, clear_existing=options["clear"])
        self.stdout.write(self.style.SUCCESS(f"Successfully imported {count} requirements"))
