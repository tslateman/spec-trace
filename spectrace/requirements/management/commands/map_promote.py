"""Management command to promote inferred co-change edges to annotated mappings."""

import json
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Promote confirmed inferred edges to annotated in spectrace-map.yaml"

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-root",
            type=str,
            default=".",
            help="Path to project root (default: current directory)",
        )
        parser.add_argument(
            "module",
            type=str,
            help="Module path to promote (e.g., src/lore/reader.py)",
        )
        parser.add_argument(
            "requirement",
            type=str,
            help="Requirement ID to link (e.g., REQ-LORE-001)",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        project_root = Path(options["project_root"]).resolve()
        module_path = options["module"]
        req_id = options["requirement"]
        output_format = options["format"]

        map_file = project_root / "spectrace-map.yaml"
        if not map_file.exists():
            raise CommandError(
                f"No spectrace-map.yaml at {map_file}. Run `spectrace specs map init` first."
            )

        try:
            with open(map_file) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise CommandError(f"Invalid YAML: {e}")

        if not isinstance(data, dict) or "modules" not in data:
            raise CommandError("Invalid spectrace-map.yaml structure")

        modules = data["modules"]
        if not isinstance(modules, dict):
            raise CommandError("'modules' must be a mapping")

        # Ensure module entry exists
        if module_path not in modules:
            modules[module_path] = {"requirements": []}

        module_entry = modules[module_path]
        if not isinstance(module_entry, dict):
            module_entry = {"requirements": []}
            modules[module_path] = module_entry

        reqs = module_entry.get("requirements", [])
        if not isinstance(reqs, list):
            reqs = []
            module_entry["requirements"] = reqs

        if req_id in reqs:
            if output_format == "json":
                self.stdout.write(json.dumps({"promoted": False, "reason": "already exists"}))
            else:
                self.stdout.write(f"Requirement '{req_id}' already mapped to '{module_path}'")
            return

        reqs.append(req_id)
        reqs.sort()

        # Remove from _inferred_co_changes if present
        inferred = module_entry.get("_inferred_co_changes", [])
        if isinstance(inferred, list) and req_id in inferred:
            inferred.remove(req_id)

        with open(map_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        if output_format == "json":
            output = {
                "promoted": True,
                "module": module_path,
                "requirement": req_id,
                "file": str(map_file),
            }
            self.stdout.write(json.dumps(output, indent=2))
        else:
            self.stdout.write(self.style.SUCCESS(f"Promoted: {module_path} -> {req_id}"))
            self.stdout.write(f"  Updated: {map_file}")
