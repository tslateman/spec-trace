"""Base command classes for import management commands."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class BaseImportCommand(BaseCommand):
    """Base class for import commands with common path validation and flags.

    Subclasses should implement:
    - add_extra_arguments(parser): Add command-specific arguments
    - do_import(options): Perform the actual import
    """

    # Subclasses should set these
    path_argument_name = "path"
    path_argument_help = "Path to import from"
    path_must_be_dir = True

    def add_arguments(self, parser):
        """Define common command arguments."""
        parser.add_argument(self.path_argument_name, type=str, help=self.path_argument_help)
        parser.add_argument(
            "--clear", action="store_true", help="Clear existing data before import"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without saving",
        )
        self.add_extra_arguments(parser)

    def add_extra_arguments(self, parser):
        """Override to add command-specific arguments."""
        pass

    def handle(self, *args, **options):
        """Execute the command with common validation."""
        path = Path(options[self.path_argument_name])

        if not path.exists():
            raise CommandError(f"Path not found: {path}")

        if self.path_must_be_dir and not path.is_dir():
            raise CommandError(f"Path is not a directory: {path}")

        return self.do_import(path, options)

    def do_import(self, path: Path, options: dict):
        """Perform the actual import. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement do_import()")
