"""Django management command for reporting test results to Linear."""
import os

from django.core.management.base import BaseCommand, CommandError

from requirements.models import TestRun
from requirements.services.linear_reporter import LinearReporter


class Command(BaseCommand):
    """Report test results to Linear issues."""

    help = 'Report test results to Linear issues as comments and labels'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            '--test-run-id',
            type=int,
            help='Specific TestRun ID to report (default: latest)'
        )
        parser.add_argument(
            '--latest',
            action='store_true',
            help='Report for the most recent test run'
        )
        parser.add_argument(
            '--no-comments',
            action='store_true',
            help='Skip adding comments to Linear issues'
        )
        parser.add_argument(
            '--no-labels',
            action='store_true',
            help='Skip updating labels on Linear issues'
        )
        parser.add_argument(
            '--include-closed',
            action='store_true',
            help='Include completed/canceled issues (default: skip)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reported without making changes'
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='Linear API key (default: LINEAR_API_KEY env var)'
        )

    def handle(self, *args, **options):
        """Execute the reporting workflow."""
        # Get API key
        api_key = options.get('api_key') or os.environ.get('LINEAR_API_KEY')
        if not api_key:
            raise CommandError(
                "Linear API key required. Set LINEAR_API_KEY env var or use --api-key"
            )

        # Get test run
        if options.get('test_run_id'):
            try:
                test_run = TestRun.objects.get(id=options['test_run_id'])
            except TestRun.DoesNotExist:
                raise CommandError(f"TestRun not found: {options['test_run_id']}")
        elif options.get('latest'):
            test_run = TestRun.objects.order_by('-imported_at').first()
            if not test_run:
                raise CommandError("No test runs found")
        else:
            raise CommandError("Must specify --test-run-id or --latest")

        self.stdout.write(f"Reporting results from TestRun {test_run.id}...")
        self.stdout.write(f"  Imported at: {test_run.imported_at}")
        if test_run.git_sha:
            self.stdout.write(f"  Git SHA: {test_run.git_sha}")

        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))
            return

        # Create reporter and report
        reporter = LinearReporter(api_key)
        result = reporter.report_test_results(
            test_run=test_run,
            add_comments=not options['no_comments'],
            update_labels=not options['no_labels'],
            skip_closed=not options['include_closed'],
        )

        if result.success:
            self.stdout.write(self.style.SUCCESS(result.message))
        else:
            self.stdout.write(self.style.ERROR(f"Errors occurred: {result.message}"))
            if result.errors:
                for error in result.errors:
                    self.stdout.write(self.style.ERROR(f"  - {error}"))
