"""Management command to report spec coverage metrics."""

import json

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q

from ...models import Requirement


class Command(BaseCommand):
    help = "Report spec coverage: specification rate, structure rate, verification rate"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        metrics = Requirement.objects.aggregate(
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
