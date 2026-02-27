"""Management command for reviewers to review submitted work."""

import json
import sys

from django.core.management.base import BaseCommand

from requirements.services.agent_tasks import TransitionError, review_task


class Command(BaseCommand):
    help = "Review submitted work (approve, request changes, or reject)"

    def add_arguments(self, parser):
        parser.add_argument(
            "task_id",
            type=str,
            help="Task external ID to review",
        )
        parser.add_argument(
            "--reviewer",
            type=str,
            required=True,
            help="Reviewer agent ID",
        )
        parser.add_argument(
            "--decision",
            type=str,
            required=True,
            choices=["approved", "changes_requested", "rejected"],
            help="Review decision",
        )
        parser.add_argument(
            "--feedback",
            type=str,
            default="",
            help="Review feedback text",
        )
        parser.add_argument(
            "--blocking-issues",
            type=str,
            nargs="*",
            default=[],
            help="List of blocking issues",
        )
        parser.add_argument(
            "--suggestions",
            type=str,
            nargs="*",
            default=[],
            help="List of non-blocking suggestions",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        task_id = options["task_id"]
        reviewer_id = options["reviewer"]
        decision = options["decision"]
        feedback = options["feedback"]
        blocking_issues = options["blocking_issues"]
        suggestions = options["suggestions"]

        try:
            result = review_task(
                task_id=task_id,
                reviewer_id=reviewer_id,
                decision=decision,
                feedback=feedback,
                blocking_issues=blocking_issues,
                suggestions=suggestions,
            )

            if options["format"] == "json":
                self.stdout.write(json.dumps(result.to_dict(), indent=2))
            else:
                style = self._get_decision_style(decision)
                self.stdout.write(style(f"✓ {result.message}"))
                if result.details.get("attempt_count", 0) > 1:
                    self.stdout.write(f"  Attempt count: {result.details['attempt_count']}")

        except TransitionError as e:
            if options["format"] == "json":
                self.stdout.write(
                    json.dumps(
                        {
                            "success": False,
                            "error": str(e),
                            "code": e.code,
                        },
                        indent=2,
                    )
                )
            else:
                self.stderr.write(self.style.ERROR(f"✗ {e}"))
            sys.exit(1)

    def _get_decision_style(self, decision):
        """Get appropriate style for decision."""
        if decision == "approved":
            return self.style.SUCCESS
        elif decision == "changes_requested":
            return self.style.WARNING
        else:  # rejected
            return self.style.ERROR
