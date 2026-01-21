"""Django management command for updating SLO status from observability platforms."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from requirements.openslo import update_slo_status_from_json
from requirements.status import update_all_slo_statuses


class Command(BaseCommand):
    """Update SLO status from observability platform JSON."""

    help = 'Update SLO status from observability platform JSON'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            '--from-json',
            type=str,
            required=True,
            help='Path to JSON file with SLO status data'
        )
        parser.add_argument(
            '--no-requirement-update',
            action='store_true',
            help='Skip updating requirement slo_status fields'
        )

    def handle(self, *args, **options):
        """Execute the status update workflow.

        Expected JSON format:
        {
            "slos": [
                {
                    "name": "api-availability",
                    "status": "met",
                    "current_value": 0.9995,
                    "error_budget_remaining": 0.75
                },
                ...
            ]
        }
        """
        json_path = Path(options['from_json'])
        if not json_path.exists():
            raise CommandError(f"JSON file not found: {json_path}")

        # Load JSON
        try:
            with open(json_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}")

        slos_data = data.get('slos', [])
        if not slos_data:
            self.stdout.write(self.style.WARNING("No SLOs found in JSON file"))
            return

        self.stdout.write(f"Updating status for {len(slos_data)} SLO(s)...")

        # Update SLO status
        summary = update_slo_status_from_json(data)

        self.stdout.write(self.style.SUCCESS(
            f"Updated {summary['updated']} SLO(s)"
        ))
        if summary['not_found']:
            self.stdout.write(self.style.WARNING(
                f"  {summary['not_found']} SLO(s) not found in database"
            ))

        # Update requirement slo_status
        if not options['no_requirement_update']:
            self.stdout.write("Updating requirement SLO status...")
            counts = update_all_slo_statuses()
            self.stdout.write(self.style.SUCCESS(
                f"Requirements updated: met={counts['met']}, "
                f"at_risk={counts['at_risk']}, breached={counts['breached']}, "
                f"not_linked={counts['not_linked']}"
            ))

        self.stdout.write(self.style.SUCCESS("Status update complete!"))
