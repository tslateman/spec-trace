"""Management command to view historical intent validation stats."""

import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Avg
from django.utils import timezone

from requirements.models import IntentValidationResult


class Command(BaseCommand):
    help = "View historical statistics for intent-to-execution validation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeframe",
            type=str,
            default="30d",
            help="Timeframe to analyze (e.g., '30d', '7d', '24h')",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        timeframe_str = options["timeframe"]
        fmt = options["format"]

        # Parse timeframe
        days = 30
        if timeframe_str.endswith("d"):
            days = int(timeframe_str[:-1])
        elif timeframe_str.endswith("h"):
            days = int(timeframe_str[:-1]) / 24.0

        cutoff = timezone.now() - timedelta(days=days)

        # Base query
        qs = IntentValidationResult.objects.filter(created_at__gte=cutoff)
        total_count = qs.count()

        if total_count == 0:
            if fmt == "json":
                self.stdout.write(json.dumps({"error": "No validation results found in timeframe"}))
            else:
                self.stdout.write(
                    self.style.WARNING(f"No validation results found in the last {timeframe_str}.")
                )
            return

        # Calculate stats
        passed_count = qs.filter(passed=True).count()
        failed_count = total_count - passed_count
        pass_rate = (passed_count / total_count) * 100

        avgs = qs.aggregate(
            avg_strategic=Avg("strategic_score"),
            avg_opportunity=Avg("opportunity_score"),
            avg_drift=Avg("drift_score"),
        )

        # Get common failure reasons
        # Django JSONField querying is complex, so we'll aggregate in Python for this
        failure_reasons_tally = {}
        for result in qs.filter(passed=False):
            for reason in result.failure_reasons:
                failure_reasons_tally[reason] = failure_reasons_tally.get(reason, 0) + 1

        top_failures = sorted(failure_reasons_tally.items(), key=lambda x: x[1], reverse=True)[:5]

        if fmt == "json":
            output = {
                "timeframe": timeframe_str,
                "total_evaluations": total_count,
                "passed": passed_count,
                "failed": failed_count,
                "pass_rate_percentage": round(pass_rate, 2),
                "average_scores": {
                    "strategic": round(avgs["avg_strategic"] or 0, 1),
                    "opportunity": round(avgs["avg_opportunity"] or 0, 1),
                    "drift": round(avgs["avg_drift"] or 0, 1),
                },
                "top_failure_reasons": [{"reason": k, "count": v} for k, v in top_failures],
            }
            self.stdout.write(json.dumps(output, indent=2))
        else:
            self.stdout.write(self.style.SUCCESS(f"Intent Validation Stats (Last {timeframe_str})"))
            self.stdout.write("=" * 40)
            self.stdout.write(f"Total Evaluations: {total_count}")
            self.stdout.write(
                f"Pass Rate: {pass_rate:.1f}% ({passed_count} passed, {failed_count} failed)"
            )
            self.stdout.write("-" * 40)
            self.stdout.write("Average Scores:")
            self.stdout.write(f"  Strategic Alignment: {avgs['avg_strategic']:.1f}/100")
            self.stdout.write(f"  Opportunity Cost:    {avgs['avg_opportunity']:.1f}/100")
            self.stdout.write(f"  Intent Drift:        {avgs['avg_drift']:.1f}/100")

            if top_failures:
                self.stdout.write("-" * 40)
                self.stdout.write("Top Failure Reasons:")
                for reason, count in top_failures:
                    self.stdout.write(f"  - {reason} ({count} occurrences)")
