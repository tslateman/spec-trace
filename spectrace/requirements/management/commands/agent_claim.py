"""Management command for agents to claim tasks."""

import json
import sys

from django.core.management.base import BaseCommand, CommandError

from requirements.services.agent_tasks import claim_task, TransitionError


class Command(BaseCommand):
    help = 'Claim an unclaimed task for an agent'

    def add_arguments(self, parser):
        parser.add_argument(
            'task_id',
            type=str,
            help='Task external ID to claim',
        )
        parser.add_argument(
            '--agent',
            type=str,
            required=True,
            help='Agent ID claiming the task',
        )
        parser.add_argument(
            '--lease-minutes',
            type=int,
            default=30,
            help='Lease duration in minutes (default: 30)',
        )
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )

    def handle(self, *args, **options):
        task_id = options['task_id']
        agent_id = options['agent']
        lease_minutes = options['lease_minutes']

        try:
            result = claim_task(task_id, agent_id, lease_minutes)

            if options['format'] == 'json':
                self.stdout.write(json.dumps(result.to_dict(), indent=2))
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ {result.message}")
                )
                self.stdout.write(f"  Lease expires: {result.details['lease_expires']}")

        except TransitionError as e:
            if options['format'] == 'json':
                self.stdout.write(json.dumps({
                    'success': False,
                    'error': str(e),
                    'code': e.code,
                }, indent=2))
            else:
                self.stderr.write(self.style.ERROR(f"✗ {e}"))
            sys.exit(1)
