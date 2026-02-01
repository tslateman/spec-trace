"""Management command to consolidate knowledge after task/milestone completion.

Runs after agent_merge to:
1. Update docs/current-state.md with latest project state
2. Check for patterns to promote to CLAUDE.md
3. Validate invariants still hold

This command is idempotent and safe to run multiple times.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from requirements.models import AgentTask, AgentTaskStatus


class Command(BaseCommand):
    help = 'Consolidate knowledge after task completion (update docs, check invariants)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--skip-invariants',
            action='store_true',
            help='Skip invariant checks',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write("Consolidating project state...\n")

        # 1. Update current-state.md
        self._update_current_state(dry_run)

        # 2. Check invariants
        if not options['skip_invariants']:
            self._check_invariants()

        # 3. Report task pipeline status
        self._report_task_status()

        self.stdout.write(self.style.SUCCESS("\n✓ Consolidation complete"))

    def _update_current_state(self, dry_run: bool) -> None:
        """Update docs/current-state.md with latest state."""
        self.stdout.write("\n1. Checking docs/current-state.md...")

        # Find project root (where .git is)
        project_root = Path(settings.BASE_DIR).parent
        current_state_path = project_root / "docs" / "current-state.md"

        if not current_state_path.exists():
            self.stdout.write(self.style.WARNING(
                f"   {current_state_path} not found - skipping"
            ))
            return

        # Check if file has "Last updated" line and update it
        content = current_state_path.read_text()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if f"Last updated: {today}" in content:
            self.stdout.write(self.style.SUCCESS("   Already up to date"))
            return

        # Update the date
        new_content = re.sub(
            r"Last updated: \d{4}-\d{2}-\d{2}",
            f"Last updated: {today}",
            content
        )

        if new_content != content:
            if dry_run:
                self.stdout.write(f"   Would update 'Last updated' to {today}")
            else:
                current_state_path.write_text(new_content)
                self.stdout.write(self.style.SUCCESS(f"   Updated 'Last updated' to {today}"))

        # Remind about manual review
        self.stdout.write(self.style.WARNING(
            "   Review docs/current-state.md for accuracy after major changes"
        ))

    def _check_invariants(self) -> None:
        """Run invariant checks."""
        self.stdout.write("\n2. Checking invariants...")

        try:
            from requirements.invariants import check_all_invariants
            report = check_all_invariants()

            if not report.has_violations:
                self.stdout.write(
                    f"   All {report.checks_performed} invariant checks passed"
                )
            else:
                self.stderr.write(
                    f"   {len(report.violations)} invariant violations found"
                )
                for v in report.violations[:5]:  # Show first 5
                    self.stdout.write(f"   - {v.code}: {v.message}")
                if len(report.violations) > 5:
                    self.stdout.write(f"   ... and {len(report.violations) - 5} more")
        except Exception as e:
            self.stderr.write(f"   Could not check invariants: {e}")

    def _report_task_status(self) -> None:
        """Report current task pipeline status."""
        self.stdout.write("\n3. Task pipeline status...")

        try:
            counts = {
                'draft': AgentTask.objects.filter(status=AgentTaskStatus.DRAFT).count(),
                'claimed': AgentTask.objects.filter(status=AgentTaskStatus.CLAIMED).count(),
                'in_progress': AgentTask.objects.filter(status=AgentTaskStatus.IN_PROGRESS).count(),
                'pending_review': AgentTask.objects.filter(status=AgentTaskStatus.PENDING_REVIEW).count(),
                'merged': AgentTask.objects.filter(status=AgentTaskStatus.MERGED).count(),
            }

            active = counts['claimed'] + counts['in_progress'] + counts['pending_review']

            if active == 0 and counts['draft'] == 0:
                self.stdout.write(self.style.SUCCESS("   No active tasks"))
            else:
                self.stdout.write(f"   Draft: {counts['draft']}, Active: {active}, Merged: {counts['merged']}")

        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   Could not query tasks: {e}"))
