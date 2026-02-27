"""Django management command for detecting integration risks across agent tasks."""

import json

from django.core.management.base import BaseCommand

from requirements.models import AgentTask, AgentTaskStatus
from requirements.services.integration_risk_detector import IntegrationRiskDetector


class Command(BaseCommand):
    """Detect integration risks across in-flight agent tasks."""

    help = "Detect conflicts across in-flight agent tasks that could cause integration problems"

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        """Execute the integration risk detection workflow."""
        detector = IntegrationRiskDetector()

        active_count = AgentTask.objects.filter(
            status__in=[AgentTaskStatus.IN_PROGRESS, AgentTaskStatus.READY_FOR_REVIEW]
        ).count()

        risks = detector.detect_all()

        if options["format"] == "json":
            self._output_json(risks, active_count)
        else:
            self._output_text(risks, active_count)

    def _output_json(self, risks, active_count):
        """Output risks as JSON."""
        data = {
            "active_tasks": active_count,
            "risks": [
                {
                    "task_a_id": r.task_a_id,
                    "task_b_id": r.task_b_id,
                    "task_a_title": r.task_a_title,
                    "task_b_title": r.task_b_title,
                    "risk_type": r.risk_type,
                    "risk_level": r.risk_level,
                    "details": r.details,
                    "recommendation": r.recommendation,
                }
                for r in risks
            ],
            "summary": {
                "high": sum(1 for r in risks if r.risk_level == "high"),
                "medium": sum(1 for r in risks if r.risk_level == "medium"),
                "low": sum(1 for r in risks if r.risk_level == "low"),
            },
        }
        self.stdout.write(json.dumps(data, indent=2))

    def _output_text(self, risks, active_count):
        """Output risks as formatted text."""
        if not risks:
            self.stdout.write(self.style.SUCCESS("No integration risks detected."))
            return

        self.stdout.write("Integration Risk Report")
        self.stdout.write("=======================")
        self.stdout.write(f"\nActive tasks: {active_count}\n")

        level_order = {"high": 0, "medium": 1, "low": 2}
        sorted_risks = sorted(risks, key=lambda r: level_order.get(r.risk_level, 3))

        level_labels = {
            "high": "HIGH",
            "medium": "MEDIUM",
            "low": "LOW",
        }
        type_labels = {
            "overlapping_requirement": "Overlapping Requirements",
            "dependency_chain": "Dependency Chain",
            "scope_overlap": "Scope Overlap",
        }

        for risk in sorted_risks:
            level_label = level_labels.get(risk.risk_level, risk.risk_level.upper())
            type_label = type_labels.get(risk.risk_type, risk.risk_type)

            style_fn = {
                "high": self.style.ERROR,
                "medium": self.style.WARNING,
                "low": self.style.NOTICE,
            }.get(risk.risk_level, self.style.NOTICE)

            self.stdout.write(style_fn(f"{level_label}: {type_label}"))
            self.stdout.write(f"  Task A: {risk.task_a_id} — {risk.task_a_title}")
            self.stdout.write(f"  Task B: {risk.task_b_id} — {risk.task_b_title}")

            if risk.risk_type == "overlapping_requirement":
                shared = risk.details.get("shared_requirements", [])
                self.stdout.write(f"  Shared: {', '.join(shared)}")
            elif risk.risk_type == "dependency_chain":
                upstream = risk.details.get("upstream_task", "")
                self.stdout.write(f"  Upstream: {upstream}")
            elif risk.risk_type == "scope_overlap":
                paths = risk.details.get("overlapping_paths", [])
                for path in paths:
                    self.stdout.write(f"  Overlap: {path}")

            self.stdout.write(f"  → {risk.recommendation}\n")

        high = sum(1 for r in risks if r.risk_level == "high")
        medium = sum(1 for r in risks if r.risk_level == "medium")
        low = sum(1 for r in risks if r.risk_level == "low")
        self.stdout.write(f"Summary: {high} high, {medium} medium, {low} low")
