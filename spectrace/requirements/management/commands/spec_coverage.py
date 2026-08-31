"""Management command to report spec coverage metrics."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Avg, Count, Q

from ...models import Requirement
from ...projects import AmbiguousProjectError, resolve_project


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

        metrics = Requirement.objects.filter(project=project).aggregate(
            total=Count("id"),
            non_draft=Count("id", filter=~Q(status="draft")),
            passing=Count("id", filter=Q(verification_status="passing")),
            avg_structure=Avg("structure_completeness"),
        )

        total = metrics["total"]
        non_draft = metrics["non_draft"]
        passing = metrics["passing"]
        avg_structure = metrics["avg_structure"] or 0.0

        if total > 0:
            spec_rate = non_draft / total
            verif_rate = passing / total
        else:
            spec_rate = 0.0
            verif_rate = 0.0

        struct_rate = avg_structure

        data = {
            "project": project,
            "spec_rate": spec_rate,
            "struct_rate": struct_rate,
            "verif_rate": verif_rate,
            "total": total,
            "non_draft": non_draft,
            "passing": passing,
        }

        if options["format"] == "json":
            self._output_json(data)
        else:
            self._output_text(data)

    def _output_json(self, data):
        output = {
            "project": data["project"],
            "specification_rate": data["spec_rate"],
            "structure_rate": data["struct_rate"],
            "verification_rate": data["verif_rate"],
            "counts": {
                "total": data["total"],
                "non_draft": data["non_draft"],
                "passing": data["passing"],
            },
        }
        self.stdout.write(json.dumps(output, indent=2))

    def _output_text(self, data):
        spec_pct = data["spec_rate"] * 100
        struct_pct = data["struct_rate"] * 100
        verif_pct = data["verif_rate"] * 100

        spec_line = (
            f"Specification rate: {spec_pct:.1f}% ({data['non_draft']}/{data['total']} non-draft)"
        )
        struct_line = f"Structure rate:     {struct_pct:.1f}% (avg FRET completeness)"
        verif_line = (
            f"Verification rate:  {verif_pct:.1f}% ({data['passing']}/{data['total']} passing)"
        )

        self.stdout.write(f"Project: {data['project']}")
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
