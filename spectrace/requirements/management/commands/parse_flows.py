"""Django management command for parsing and syncing YAML flow definitions."""
from pathlib import Path

from requirements.flows.parser import YAMLFlowParser
from requirements.flows.sync import sync_yaml_flows_to_db

from .base import BaseImportCommand


class Command(BaseImportCommand):
    """Parse YAML flow definitions and sync to database."""

    help = 'Parse YAML flow definitions and sync to database'
    path_argument_name = 'flows_dir'
    path_argument_help = 'Path to directory containing flow YAML files'

    def do_import(self, path: Path, options: dict):
        """Execute the parse and sync workflow."""
        self.stdout.write(f"Parsing flow files from {path}...")

        parser = YAMLFlowParser()
        flows = parser.parse_directory(path)

        if not flows:
            self.stdout.write(self.style.WARNING("No flow files found"))
            return

        self.stdout.write(f"Found {len(flows)} flow(s)")

        for flow in flows:
            req_count = len(flow.requirements)
            step_count = len(flow.steps)
            source = flow.source_file or 'code-defined'
            self.stdout.write(
                f"  - {flow.name}: steps={step_count}, "
                f"requirements={req_count}, source={source}"
            )

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS("Dry run complete - no changes made"))
            return

        # Sync to database
        results = sync_yaml_flows_to_db(
            flows,
            clear_existing=options['clear']
        )

        created = sum(1 for action in results.values() if action == 'created')
        updated = sum(1 for action in results.values() if action == 'updated')

        self.stdout.write(self.style.SUCCESS(
            f"Sync complete: {created} created, {updated} updated"
        ))
