"""Management command to generate contract snapshots."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...services.contract_snapshot import ContractSnapshot


class Command(BaseCommand):
    help = "Generate contract.snapshot.json for a project"

    def add_arguments(self, parser):
        parser.add_argument(
            "project_root",
            type=str,
            help="Path to the project root directory",
        )
        parser.add_argument(
            "--project-name",
            type=str,
            required=True,
            help="Name of the project (e.g., lore, praxis)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output path (default: <project_root>/contract.snapshot.json)",
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

        if not project_root.is_dir():
            raise CommandError(f"Project root does not exist: {project_root}")

        snapshot = ContractSnapshot.generate(project_root, project_name)

        output_path = (
            Path(options["output"])
            if options["output"]
            else project_root / "contract.snapshot.json"
        )
        snapshot.save(output_path)

        if output_format == "json":
            output = {
                "project": snapshot.project,
                "surfaces": len(snapshot.surfaces),
                "output_path": str(output_path),
            }
            self.stdout.write(json.dumps(output, indent=2))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Generated contract snapshot for '{project_name}'")
            )
            self.stdout.write(f"  Surfaces: {len(snapshot.surfaces)}")
            self.stdout.write(f"  Output: {output_path}")
            for name in sorted(snapshot.surfaces.keys()):
                fmt = snapshot.surfaces[name].get("format", "?")
                field_count = len(snapshot.surfaces[name].get("fields", []))
                self.stdout.write(f"    {name} ({fmt}, {field_count} fields)")
