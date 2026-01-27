"""Management command to detect drift in test-requirement links."""

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from requirements.validator import (
    detect_all_drift,
    detect_orphan_requirements,
    detect_spec_drift,
    detect_stale_links,
    detect_unmarked_tests,
)


class Command(BaseCommand):
    help = 'Detect drift between specs, tests, and their linkages'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tests',
            type=str,
            help='Path to test directory (for unmarked test detection)',
        )
        parser.add_argument(
            '--specs',
            type=str,
            help='Path to specs directory (for spec drift detection)',
        )
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--check',
            choices=['all', 'unmarked', 'stale', 'orphan', 'drift'],
            default='all',
            help='Which drift check to run (default: all)',
        )
        parser.add_argument(
            '--strict',
            action='store_true',
            help='Treat warnings as errors (exit code 1 on warnings)',
        )

    def handle(self, *args, **options):
        output_format = options['format']
        check = options['check']
        strict = options['strict']

        test_dir = Path(options['tests']) if options['tests'] else None
        specs_dir = Path(options['specs']) if options['specs'] else None

        # Run checks
        if check == 'all':
            result = detect_all_drift(test_dir, specs_dir)
        elif check == 'unmarked':
            if not test_dir:
                self.stderr.write(
                    self.style.ERROR('--tests required for unmarked check')
                )
                sys.exit(2)
            result = detect_unmarked_tests(test_dir)
        elif check == 'stale':
            result = detect_stale_links()
        elif check == 'orphan':
            result = detect_orphan_requirements()
        else:  # drift
            if not specs_dir:
                self.stderr.write(
                    self.style.ERROR('--specs required for drift check')
                )
                sys.exit(2)
            result = detect_spec_drift(specs_dir)

        # Output results
        if output_format == 'json':
            self.stdout.write(json.dumps(result.to_dict(), indent=2))
        else:
            self._output_text(result, check)

        # Exit code
        if result.has_errors:
            sys.exit(1)
        elif strict and result.has_warnings:
            sys.exit(1)

    def _output_text(self, result, check):
        """Output human-readable results."""
        check_names = {
            'all': 'all drift checks',
            'unmarked': 'unmarked tests',
            'stale': 'stale links',
            'orphan': 'orphan requirements',
            'drift': 'spec drift',
        }
        self.stdout.write(f'Running {check_names[check]}...\n')

        if not result.errors and not result.warnings:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ No drift detected ({result.items_checked} items checked)'
                )
            )
            return

        # Group by type
        by_type: dict[str, list] = {}
        for issue in result.errors + result.warnings:
            by_type.setdefault(issue.type, []).append(issue)

        for issue_type, issues in sorted(by_type.items()):
            type_label = issue_type.upper().replace('_', ' ')
            self.stdout.write(f'\n{type_label}:')

            for issue in issues:
                is_error = issue in result.errors
                style = self.style.ERROR if is_error else self.style.WARNING
                marker = '✗' if is_error else '⚠'

                self.stdout.write(style(f'  {marker} {issue.id}'))
                self.stdout.write(f'    {issue.message}')

                # Show relevant details
                if issue.type == 'stale_link':
                    self.stdout.write(
                        f"    Last status: {issue.details.get('last_status', 'unknown')}"
                    )
                elif issue.type == 'spec_drift':
                    affected = issue.details.get('affected_requirements', [])
                    if affected:
                        self.stdout.write(f'    Affects: {", ".join(affected[:5])}')
                        if len(affected) > 5:
                            self.stdout.write(f'    ...and {len(affected) - 5} more')

        # Summary
        self.stdout.write(
            f'\nSummary: {result.items_checked} items checked, '
            f'{len(result.errors)} errors, {len(result.warnings)} warnings'
        )
