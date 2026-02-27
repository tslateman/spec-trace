"""Django management command for detecting requirement conflicts."""

from django.core.management.base import BaseCommand

from requirements.models import TestRun
from requirements.services.conflict_detector import ConflictDetector


class Command(BaseCommand):
    """Detect conflicts between requirements based on test patterns."""

    help = "Detect mutual exclusion and other conflicts between requirements"

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            "--min-runs",
            type=int,
            default=10,
            help="Minimum test runs before analyzing (default: 10)",
        )
        parser.add_argument(
            "--min-overlap",
            type=int,
            default=5,
            help="Minimum runs where both requirements tested (default: 5)",
        )
        parser.add_argument(
            "--latest",
            action="store_true",
            help="Only analyze runs from the latest test run onwards",
        )
        parser.add_argument(
            "--alert",
            action="store_true",
            help="Log high-confidence conflicts and print alerts",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be detected without logging to database",
        )

    def handle(self, *args, **options):
        """Execute the conflict detection workflow."""
        detector = ConflictDetector(
            min_runs=options["min_runs"],
            min_overlap=options["min_overlap"],
        )

        # Get runs to analyze
        runs = None
        if options.get("latest"):
            runs = list(TestRun.objects.order_by("-imported_at")[: options["min_runs"] * 2])
            if runs:
                self.stdout.write(f"Analyzing {len(runs)} recent test runs...")

        # Detect mutual exclusion conflicts
        self.stdout.write("Detecting mutual exclusion conflicts...")
        conflicts = detector.detect_mutual_exclusion(runs)

        if not conflicts:
            self.stdout.write(self.style.SUCCESS("No conflicts detected"))
            return

        self.stdout.write(f"Found {len(conflicts)} potential conflicts:")

        for conflict in conflicts:
            confidence_style = {
                "high": self.style.ERROR,
                "medium": self.style.WARNING,
                "low": self.style.NOTICE,
            }.get(conflict.confidence, self.style.NOTICE)

            self.stdout.write(
                confidence_style(
                    f"  [{conflict.confidence.upper()}] "
                    f"{conflict.requirement_a_external_id} ↔ {conflict.requirement_b_external_id} "
                    f"({conflict.pattern})"
                )
            )
            self.stdout.write(
                f"    Runs analyzed: {conflict.runs_analyzed}, "
                f"Inverse ratio: {conflict.details.get('inverse_ratio', 0):.1%}"
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDRY RUN - conflicts not logged to database"))
            return

        if options["alert"]:
            # Log conflicts to database
            log_result = detector.log_conflicts(conflicts, skip_existing=True)
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nLogged {log_result['created_count']} new conflicts "
                    f"({log_result['skipped_count']} already existed)"
                )
            )

            # Print high-confidence alerts
            high_confidence = [c for c in conflicts if c.confidence == "high"]
            if high_confidence:
                self.stdout.write(
                    self.style.ERROR(
                        f"\n⚠️  {len(high_confidence)} HIGH CONFIDENCE CONFLICTS REQUIRE ATTENTION:"
                    )
                )
                for conflict in high_confidence:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  - {conflict.requirement_a_external_id}"
                            f" ↔ {conflict.requirement_b_external_id}"
                        )
                    )
