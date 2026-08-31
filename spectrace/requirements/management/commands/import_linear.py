"""Django management command for importing requirements from Linear."""

import os

from django.core.management.base import CommandError

from requirements.linear import LinearClient
from requirements.parser import import_requirements_to_database
from requirements.projects import default_project

from .base import BaseImportCommand


class Command(BaseImportCommand):
    """Import requirements from Linear issues with a specific label."""

    help = "Import requirements from Linear issues with a specific label"
    path_must_be_dir = False  # Linear doesn't use a path

    def add_arguments(self, parser):
        """Override to add Linear-specific arguments (no path needed)."""
        parser.add_argument(
            "--label",
            default="requirement",
            help="Label to filter issues (default: requirement)",
        )
        parser.add_argument("--api-key", help="Linear API key (or set LINEAR_API_KEY env var)")
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing Linear-sourced requirements before import",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without saving",
        )
        parser.add_argument(
            "--project",
            type=str,
            default=None,
            help="Project that owns these issues (default: this installation's project)",
        )

    def handle(self, *args, **options):
        """Execute the command (overrides base to skip path validation)."""
        # Get API key from argument or environment
        api_key = options.get("api_key") or os.environ.get("LINEAR_API_KEY")
        if not api_key:
            raise CommandError(
                "Linear API key required. Provide --api-key or set LINEAR_API_KEY env var"
            )

        label = options["label"]
        client = LinearClient(api_key)

        self.stdout.write(f"Fetching issues with label '{label}' from Linear...")

        try:
            requirements = client.fetch_issues_by_label(label)
        except Exception as e:
            raise CommandError(f"Failed to fetch from Linear: {e}")

        if not requirements:
            self.stdout.write(self.style.WARNING("No issues found with that label"))
            return

        self.stdout.write(f"Found {len(requirements)} issues")

        if options["dry_run"]:
            self.stdout.write("\nDry run - would import:")
            for req in requirements:
                parent_info = f" (parent: {req['parent_id']})" if req["parent_id"] else ""
                self.stdout.write(f"  {req['external_id']}: {req['title']}{parent_info}")
            return

        # Import to database
        project = options["project"] or default_project()
        count = import_requirements_to_database(
            requirements,
            clear_existing=options["clear"],
            source_prefix="linear://" if options["clear"] else None,
            project=project,
        )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported {count} new requirements into {project}")
        )
