"""Django management command for importing in-app validation results."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from requirements.models import (
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    InAppValidationStatus,
    Requirement,
)


class Command(BaseCommand):
    """Import in-app validation results from JSON file."""

    help = 'Import in-app validation results from JSON file'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to validations JSON file'
        )
        parser.add_argument(
            '--no-status-update',
            action='store_true',
            help='Skip updating InAppValidation status from results'
        )

    def handle(self, *args, **options):
        """Execute the import workflow.

        Expected JSON format:
        {
            "source": "production-app",
            "validations": [
                {
                    "requirement_id": "REQ-AUTH-001",
                    "name": "Verify Login Flow",
                    "endpoint": "/api/auth/verify",
                    "status": "success",
                    "message": "All checks passed",
                    "checked_at": "2024-01-15T10:30:00Z"
                },
                ...
            ]
        }
        """
        json_path = Path(options['json_file'])
        if not json_path.exists():
            raise CommandError(f"JSON file not found: {json_path}")

        # Load JSON
        try:
            with open(json_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}")

        source = data.get('source', str(json_path))
        validations_data = data.get('validations', [])

        if not validations_data:
            self.stdout.write(self.style.WARNING("No validations found in JSON file"))
            return

        # Create validation run
        validation_run = InAppValidationRun.objects.create(
            source=source,
            total_validations=len(validations_data),
        )

        # Track statistics
        successful = 0
        failed = 0
        created_validations = 0
        skipped = 0

        for v in validations_data:
            requirement_id = v.get('requirement_id')
            if not requirement_id:
                self.stdout.write(self.style.WARNING(
                    f"Skipping validation without requirement_id: {v.get('name', 'unknown')}"
                ))
                skipped += 1
                continue

            # Find requirement
            try:
                requirement = Requirement.objects.get(external_id=requirement_id)
            except Requirement.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"Requirement not found: {requirement_id}"
                ))
                skipped += 1
                continue

            # Get or create InAppValidation
            validation, created = InAppValidation.objects.get_or_create(
                requirement=requirement,
                name=v.get('name', f'Validation for {requirement_id}'),
                defaults={
                    'endpoint': v.get('endpoint', ''),
                }
            )
            if created:
                created_validations += 1

            # Parse status
            status_str = v.get('status', 'unknown').lower()
            if status_str == 'success':
                status = InAppValidationStatus.SUCCESS
                successful += 1
            elif status_str == 'failure':
                status = InAppValidationStatus.FAILURE
                failed += 1
            else:
                status = InAppValidationStatus.UNKNOWN

            # Parse checked_at timestamp
            checked_at_str = v.get('checked_at')
            if checked_at_str:
                try:
                    from django.utils.dateparse import parse_datetime
                    checked_at = parse_datetime(checked_at_str)
                    if checked_at is None:
                        checked_at = timezone.now()
                except (ValueError, TypeError):
                    checked_at = timezone.now()
            else:
                checked_at = timezone.now()

            # Create result
            InAppValidationResult.objects.create(
                validation_run=validation_run,
                validation=validation,
                status=status,
                message=v.get('message', ''),
                checked_at=checked_at,
            )

            # Update validation status if requested
            if not options['no_status_update']:
                validation.status = status
                validation.last_checked = checked_at
                validation.message = v.get('message', '')
                validation.save()

        # Update run statistics
        validation_run.successful = successful
        validation_run.failed = failed
        validation_run.save()

        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(validations_data) - skipped} validations "
            f"(successful={successful}, failed={failed})"
        ))
        if created_validations:
            self.stdout.write(f"  Created {created_validations} new InAppValidation records")
        if skipped:
            self.stdout.write(self.style.WARNING(f"  Skipped {skipped} validations"))

        self.stdout.write(self.style.SUCCESS("Import complete!"))
