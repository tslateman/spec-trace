"""Management command to set up flow status dashboard demo data."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from requirements.flows.definitions import REGISTERED_FLOWS
from requirements.models import (
    VerificationFlow,
    VerificationFlowRun,
    VerificationFlowStep,
    VerificationFlowSource,
    VerificationFlowStatus,
)


class Command(BaseCommand):
    help = 'Set up demo data for flow status dashboard'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing runs before creating demo data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Setting up flow status demo...'))

        # Sync all registered flows to DB
        for flow_def in REGISTERED_FLOWS:
            flow, created = VerificationFlow.objects.update_or_create(
                name=flow_def.name,
                defaults={
                    'display_name': flow_def.display_name,
                    'description': flow_def.description,
                    'steps': [
                        {
                            'name': s.name,
                            'handler': s.handler,
                            'display_name': s.display_name,
                        }
                        for s in flow_def.steps
                    ],
                    'version': flow_def.version,
                    'synced_at': timezone.now(),
                }
            )
            status = 'created' if created else 'synced'
            self.stdout.write(f'  Flow {status}: {flow.display_name}')

            # Clear existing runs if requested
            if options['clear']:
                deleted, _ = flow.runs.all().delete()
                if deleted:
                    self.stdout.write(f'  Cleared {deleted} existing runs')

            # Create demo runs for this flow
            self._create_passed_run(flow)
            self._create_failed_run_auth(flow)
            self._create_failed_run_config(flow)

        self.stdout.write(self.style.SUCCESS('\nDemo data ready!'))
        self.stdout.write(f'\nView at: /admin/flow-status/')

    def _create_passed_run(self, flow):
        """Create a fully passing run."""
        run = VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.PASSED,
            source=VerificationFlowSource.MANUAL,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now() - timedelta(hours=1) + timedelta(seconds=3),
        )

        steps = [
            ('config', True, 'LINEAR_API_KEY present, format valid', '', None),
            ('auth', True, 'Authenticated as: team@example.com', '', 200),
            ('permissions', True, 'Read access confirmed, 42 issues accessible', '', 200),
        ]
        self._create_steps(run, steps)
        self.stdout.write(f'  Created run #{run.id}: passed (all steps)')

    def _create_failed_run_auth(self, flow):
        """Create a run that fails at auth step."""
        run = VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.FAILED,
            source=VerificationFlowSource.SCHEDULED,
            started_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now() - timedelta(hours=2) + timedelta(seconds=2),
        )

        steps = [
            ('config', True, 'LINEAR_API_KEY present, format valid', '', None),
            ('auth', False, '', 'Authentication failed: API key rejected', 401),
        ]
        self._create_steps(run, steps)
        self.stdout.write(f'  Created run #{run.id}: failed at auth')

    def _create_failed_run_config(self, flow):
        """Create a run that fails at config step."""
        run = VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.FAILED,
            source=VerificationFlowSource.API,
            started_at=timezone.now() - timedelta(minutes=30),
            completed_at=timezone.now() - timedelta(minutes=30) + timedelta(seconds=1),
        )

        steps = [
            ('config', False, '', 'Missing required config: LINEAR_API_KEY not set', None),
        ]
        self._create_steps(run, steps)
        self.stdout.write(f'  Created run #{run.id}: failed at config')

    def _create_steps(self, run, steps):
        """Create step records for a run."""
        base_time = run.started_at
        for i, (name, passed, details, error, status_code) in enumerate(steps):
            VerificationFlowStep.objects.create(
                flow_run=run,
                step_order=i,
                name=name,
                passed=passed,
                details=details,
                error_message=error,
                response_status=status_code,
                started_at=base_time + timedelta(seconds=i),
                completed_at=base_time + timedelta(seconds=i + 1),
            )
