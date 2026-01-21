"""Django management command for importing pytest JUnit XML results."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from requirements.importer import import_junit_xml, link_results_to_requirements
from requirements.status import update_all_verification_statuses


class Command(BaseCommand):
    """Import pytest JUnit XML results and compute verification status."""

    help = 'Import pytest JUnit XML results and compute verification status'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            'junit_xml',
            type=str,
            help='Path to pytest JUnit XML file'
        )
        parser.add_argument(
            '--links',
            type=str,
            help='Path to extract_links JSON output (optional)'
        )
        parser.add_argument(
            '--no-status-update',
            action='store_true',
            help='Skip updating verification status after import'
        )

    def handle(self, *args, **options):
        """Execute the import workflow."""
        junit_path = Path(options['junit_xml'])
        if not junit_path.exists():
            raise CommandError(f"JUnit XML file not found: {junit_path}")

        # Import test results
        self.stdout.write(f"Importing test results from {junit_path}...")
        test_run = import_junit_xml(str(junit_path))
        self.stdout.write(self.style.SUCCESS(
            f"Imported {test_run.total_tests} tests "
            f"(passed={test_run.passed}, failed={test_run.failed}, "
            f"errors={test_run.errors}, skipped={test_run.skipped})"
        ))

        # Link to requirements if links JSON provided
        links_path = options.get('links')
        if links_path:
            links_path = Path(links_path)
            if not links_path.exists():
                raise CommandError(f"Links JSON file not found: {links_path}")

            self.stdout.write(f"Linking results to requirements using {links_path}...")
            summary = link_results_to_requirements(test_run, str(links_path))
            self.stdout.write(self.style.SUCCESS(
                f"Linked {summary['linked_count']} test results to requirements"
            ))
            if summary['unlinked_tests']:
                self.stdout.write(self.style.WARNING(
                    f"  {len(summary['unlinked_tests'])} tests not linked to any requirement"
                ))

        # Update verification status
        if not options['no_status_update']:
            self.stdout.write("Computing verification status for all requirements...")
            counts = update_all_verification_statuses(test_run)
            self.stdout.write(self.style.SUCCESS(
                f"Status updated: passing={counts['passing']}, "
                f"failing={counts['failing']}, untested={counts['untested']}"
            ))

        self.stdout.write(self.style.SUCCESS("Import complete!"))
