"""Management command to generate initial spectrace-map.yaml from git inference."""

import json
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from ...services.git_cochange import GitCoChangeAnalyzer


class Command(BaseCommand):
    help = "Generate spectrace-map.yaml from git co-change inference"

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
            help="Project name (e.g., lore, praxis)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output path (default: <project_root>/spectrace-map.yaml)",
        )
        parser.add_argument(
            "--lookback-days",
            type=int,
            default=90,
            help="Git history lookback in days (default: 90)",
        )
        parser.add_argument(
            "--min-count",
            type=int,
            default=3,
            help="Minimum co-change count (Rule of Three, default: 3)",
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

        # Run git co-change analysis
        try:
            analyzer = GitCoChangeAnalyzer(project_root, lookback_days=options["lookback_days"])
            co_changes = analyzer.compute_co_changes(min_count=options["min_count"])
        except ValueError as e:
            raise CommandError(str(e))

        # Build module -> requirements mapping from co-changes
        # Group files that change together into modules
        modules: dict[str, dict] = {}
        for cc in co_changes:
            for f in (cc.file_a, cc.file_b):
                if f not in modules:
                    modules[f] = {"requirements": [], "_co_changes": []}
                partner = cc.file_b if f == cc.file_a else cc.file_a
                modules[f]["_co_changes"].append(
                    {
                        "file": partner,
                        "count": cc.count,
                        "weight": cc.weight,
                    }
                )

        # Build YAML structure
        map_data = {
            "project": project_name,
            "modules": {},
        }
        for module_path in sorted(modules.keys()):
            map_data["modules"][module_path] = {
                "requirements": [],  # Empty — user fills in requirement IDs
                "_inferred_co_changes": [c["file"] for c in modules[module_path]["_co_changes"]],
            }

        output_path = (
            Path(options["output"]) if options["output"] else project_root / "spectrace-map.yaml"
        )

        with open(output_path, "w") as f:
            yaml.dump(map_data, f, default_flow_style=False, sort_keys=False)

        if output_format == "json":
            output = {
                "project": project_name,
                "modules": len(map_data["modules"]),
                "co_changes": len(co_changes),
                "output_path": str(output_path),
            }
            self.stdout.write(json.dumps(output, indent=2))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Generated spectrace-map.yaml for '{project_name}'")
            )
            self.stdout.write(f"  Modules discovered: {len(map_data['modules'])}")
            self.stdout.write(f"  Co-change pairs: {len(co_changes)}")
            self.stdout.write(f"  Output: {output_path}")
            self.stdout.write(
                "\nNext: Edit the file to add requirement IDs, "
                "then run `spectrace specs map validate` to verify."
            )
