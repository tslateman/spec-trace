"""Management command to report spec coverage metrics."""

import json

from django.core.management.base import BaseCommand, CommandError

from ...models import Requirement
from ...projects import AmbiguousProjectError, resolve_project
from ...services.coverage_metrics import coverage_metrics


class Command(BaseCommand):
    help = "Report spec coverage for one project: specification, structure, verification rates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--project",
            type=str,
            default=None,
            help="Project to report on (default: this installation's project)",
        )

    def handle(self, *args, **options):
        try:
            project = resolve_project(options["project"], Requirement.project_names())
        except AmbiguousProjectError as e:
            raise CommandError(f"{e} Pass --project.") from e

        metrics = coverage_metrics(project)

        if options["format"] == "json":
            self._output_json(metrics)
        else:
            self._output_text(metrics)

    def _output_json(self, metrics):
        output = {
            "project": metrics["project"],
            "specification_rate": metrics["specification_rate"],
            "structure_rate": metrics["structure_rate"],
            "verification_rate": metrics["verification_rate"],
            "counts": {
                "total": metrics["total"],
                "non_draft": metrics["non_draft"],
                "passing": metrics["passing"],
            },
        }
        self.stdout.write(json.dumps(output, indent=2))

    def _output_text(self, metrics):
        spec_pct = metrics["specification_rate"] * 100
        struct_pct = metrics["structure_rate"] * 100
        verif_pct = metrics["verification_rate"] * 100

        spec_line = (
            f"Specification rate: {spec_pct:.1f}%"
            f" ({metrics['non_draft']}/{metrics['total']} non-draft)"
        )
        struct_line = f"Structure rate:     {struct_pct:.1f}% (avg FRET completeness)"
        verif_line = (
            f"Verification rate:  {verif_pct:.1f}%"
            f" ({metrics['passing']}/{metrics['total']} passing)"
        )

        self.stdout.write(f"Project: {metrics['project']}")
        self.stdout.write(self._colorize(spec_line, spec_pct))
        self.stdout.write(self._colorize(struct_line, struct_pct))
        self.stdout.write(self._colorize(verif_line, verif_pct))

    def _colorize(self, text, pct):
        if pct >= 80:
            return self.style.SUCCESS(text)
        elif pct >= 40:
            return self.style.WARNING(text)
        else:
            return self.style.ERROR(text)
