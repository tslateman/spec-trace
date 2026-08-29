"""Django management command for parsing corpus files into versioned entries."""

from pathlib import Path

from django.core.management.base import CommandError

from requirements.services.corpus_parser import CorpusParseError, CorpusParser

from .base import BaseImportCommand


class Command(BaseImportCommand):
    """Parse markdown corpus files and import versioned entries into database."""

    help = "Parse markdown corpus files and import versioned entries into database"
    path_argument_name = "corpus_dir"
    path_argument_help = "Path to corpus directory (e.g., corpus/)"

    def do_import(self, path: Path, options: dict):
        """Execute the import."""
        if options["clear"]:
            raise CommandError(
                "--clear is not supported for the corpus: entry versions are immutable "
                "and reviews reference them"
            )

        parser = CorpusParser()

        try:
            entries = parser.parse_directory(path)
        except CorpusParseError as exc:
            raise CommandError(str(exc)) from exc

        if options["dry_run"]:
            self.stdout.write(f"Found {len(entries)} corpus entries:")
            for entry in entries:
                self.stdout.write(
                    f"  {entry['external_id']}@{entry['version']} "
                    f"[{entry['kind']}/{entry['status']}]: {entry['title']}"
                )
            return

        try:
            counts = parser.import_to_database(path)
        except CorpusParseError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {counts['entries_created']} new entries, "
                f"{counts['versions_created']} new versions "
                f"({counts['versions_unchanged']} unchanged)"
            )
        )
