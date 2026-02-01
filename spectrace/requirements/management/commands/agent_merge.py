"""Management command to mark an approved task as merged."""

import json
import sys

from django.core.management.base import BaseCommand

from requirements.services.agent_tasks import merge_task, TransitionError


class Command(BaseCommand):
    help = 'Mark an approved task as merged (APPROVED → MERGED)'

    def add_arguments(self, parser):
        parser.add_argument(
            'task_id',
            type=str,
            help='Task external ID to merge',
        )
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )

    def handle(self, *args, **options):
        task_id = options['task_id']

        try:
            result = merge_task(task_id)

            if options['format'] == 'json':
                self.stdout.write(json.dumps(result.to_dict(), indent=2))
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ {result.message}")
                )

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
