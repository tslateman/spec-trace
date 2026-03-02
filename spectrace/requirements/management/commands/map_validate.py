"""Management command to validate spectrace-map.yaml files."""

import json
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from ...services.map_reader import MapReader


class Command(BaseCommand):
    help = "Validate spectrace-map.yaml syntax and requirement ID references"

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-root",
            type=str,
            default=".",
            help="Path to project root (default: current directory)",
        )
        parser.add_argument(
            "--project-name",
            type=str,
            required=True,
            help="Project name",
        )
        parser.add_argument(
            "--check-requirements",
            action="store_true",
            default=False,
            help="Verify requirement IDs exist in the database",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        project_root = Path(options["project_root"]).resolve()
        project_name = options["project_name"]
        output_format = options["format"]

        map_file = project_root / "spectrace-map.yaml"
        if not map_file.exists():
            raise CommandError(f"No spectrace-map.yaml found at {map_file}")

        try:
            with open(map_file) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise CommandError(f"Invalid YAML: {e}")

        reader = MapReader({project_name: project_root})
        errors = reader.validate_map(data)

        # Optionally check requirement IDs against DB
        req_warnings = []
        if options["check_requirements"] and not errors:
            from requirements.models import Requirement

            pairs = reader.read_map(project_name)
            req_ids = {p[1] for p in pairs}
            existing = set(
                Requirement.objects.filter(external_id__in=req_ids).values_list(
                    "external_id", flat=True
                )
            )
            missing = req_ids - existing
            for req_id in sorted(missing):
                req_warnings.append(f"Requirement '{req_id}' not found in database")

        if output_format == "json":
            output = {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": req_warnings,
                "file": str(map_file),
            }
            self.stdout.write(json.dumps(output, indent=2))
        else:
            if errors:
                self.stdout.write(self.style.ERROR(f"Validation failed for {map_file}:"))
                for err in errors:
                    self.stdout.write(f"  {err}")
            else:
                self.stdout.write(self.style.SUCCESS(f"Valid: {map_file}"))
                pairs = reader.read_map(project_name)
                self.stdout.write(f"  Modules: {len(set(p[0] for p in pairs))}")
                self.stdout.write(f"  Requirement links: {len(pairs)}")

            if req_warnings:
                self.stdout.write(self.style.WARNING("\nWarnings:"))
                for warn in req_warnings:
                    self.stdout.write(f"  {warn}")
