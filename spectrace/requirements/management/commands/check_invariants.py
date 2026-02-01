"""Management command to check data invariants for SpecTrace."""

import json
import sys

from django.core.management.base import BaseCommand

from requirements.invariants import (
    check_all_invariants,
    check_inv_a_status_consistency,
    check_inv_b_slo_override,
    check_inv_d_link_uniqueness,
    check_inv_e_review_flag,
    check_inv_f_flow_completion,
    check_inv_g_claimed_has_agent,
    check_inv_h_claimed_has_lease,
    check_inv_i_nondraft_has_history,
    check_inv_j_approved_has_review,
    check_inv_k_no_self_review,
)
from requirements.models import TestRun


class Command(BaseCommand):
    help = 'Check data invariants for consistency and correctness'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix auto-fixable violations',
        )
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--check',
            choices=[
                'all', 'INV-A', 'INV-B', 'INV-D', 'INV-E', 'INV-F',
                'INV-G', 'INV-H', 'INV-I', 'INV-J', 'INV-K',
            ],
            default='all',
            help='Which invariant to check (default: all)',
        )
        parser.add_argument(
            '--strict',
            action='store_true',
            help='Treat warnings as errors (exit code 1 on warnings)',
        )

    def handle(self, *args, **options):
        fix = options['fix']
        output_format = options['format']
        check = options['check']
        strict = options['strict']

        # Get latest test run for status computation
        latest_run = TestRun.objects.order_by('-imported_at').first()

        # Run checks
        if check == 'all':
            result = check_all_invariants(latest_run, fix)
        elif check == 'INV-A':
            result = check_inv_a_status_consistency(latest_run, fix)
        elif check == 'INV-B':
            result = check_inv_b_slo_override(fix)
        elif check == 'INV-D':
            result = check_inv_d_link_uniqueness()
        elif check == 'INV-E':
            result = check_inv_e_review_flag(fix)
        elif check == 'INV-F':
            result = check_inv_f_flow_completion()
        elif check == 'INV-G':
            result = check_inv_g_claimed_has_agent()
        elif check == 'INV-H':
            result = check_inv_h_claimed_has_lease()
        elif check == 'INV-I':
            result = check_inv_i_nondraft_has_history()
        elif check == 'INV-J':
            result = check_inv_j_approved_has_review()
        else:  # INV-K
            result = check_inv_k_no_self_review()

        # Output results
        if output_format == 'json':
            self.stdout.write(json.dumps(result.to_dict(), indent=2))
        else:
            self._output_text(result, check, fix)

        # Exit code
        if result.error_count > 0:
            sys.exit(1)
        elif strict and result.warning_count > 0:
            sys.exit(1)

    def _output_text(self, result, check, fix):
        """Output human-readable results."""
        if check == 'all':
            self.stdout.write('Checking all invariants...\n')
        else:
            self.stdout.write(f'Checking {check}...\n')

        if not result.violations:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ No violations found ({result.checks_performed} checks)'
                )
            )
            return

        # Group by code
        by_code: dict[str, list] = {}
        for v in result.violations:
            by_code.setdefault(v.code, []).append(v)

        for code, violations in sorted(by_code.items()):
            errors = [v for v in violations if v.severity == 'error']
            warnings = [v for v in violations if v.severity == 'warning']

            self.stdout.write(f'\n{code}:')

            for v in errors:
                marker = '✗' if not v.fixable else ('✓ fixed' if fix else '✗ (fixable)')
                self.stdout.write(
                    self.style.ERROR(f'  {marker} {v.requirement_id}: {v.message}')
                )

            for v in warnings:
                marker = '⚠' if not v.fixable else ('✓ fixed' if fix else '⚠ (fixable)')
                self.stdout.write(
                    self.style.WARNING(f'  {marker} {v.requirement_id}: {v.message}')
                )

        # Summary
        self.stdout.write(
            f'\nSummary: {result.checks_performed} checks, '
            f'{result.error_count} errors, {result.warning_count} warnings'
        )

        if fix and result.fixed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Fixed {result.fixed_count} violations')
            )
        elif result.error_count > 0 or result.warning_count > 0:
            fixable = sum(1 for v in result.violations if v.fixable)
            if fixable > 0:
                self.stdout.write(
                    self.style.NOTICE(f'Run with --fix to auto-fix {fixable} violations')
                )
