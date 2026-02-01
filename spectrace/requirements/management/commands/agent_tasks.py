"""Management command to list agent tasks."""

import json
import sys

from django.core.management.base import BaseCommand

from requirements.services.agent_tasks import list_tasks


class Command(BaseCommand):
    help = 'List agent tasks with optional filtering'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            type=str,
            help='Filter by status (draft, unclaimed, claimed, in_progress, etc.)',
        )
        parser.add_argument(
            '--sprint',
            type=int,
            help='Filter by sprint ID',
        )
        parser.add_argument(
            '--agent',
            type=str,
            help='Filter by claimed agent ID',
        )
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )

    def handle(self, *args, **options):
        tasks = list_tasks(
            status=options['status'],
            sprint_id=options['sprint'],
            agent_id=options['agent'],
        )

        if options['format'] == 'json':
            self.stdout.write(json.dumps({'tasks': tasks}, indent=2))
        else:
            self._output_text(tasks)

    def _output_text(self, tasks):
        """Output human-readable results."""
        if not tasks:
            self.stdout.write('No tasks found.')
            return

        self.stdout.write(f'Found {len(tasks)} task(s):\n')

        for task in tasks:
            status_color = self._get_status_style(task['status'])
            claimed = f" (claimed by {task['claimed_by']})" if task['claimed_by'] else ""
            self.stdout.write(
                status_color(f"  {task['external_id']}: {task['title']}")
            )
            self.stdout.write(f"    Status: {task['status']}{claimed}")
            if task['sprint']:
                self.stdout.write(f"    Sprint: {task['sprint']}")
            self.stdout.write('')

    def _get_status_style(self, status):
        """Get appropriate style for status."""
        if status in ('merged', 'approved'):
            return self.style.SUCCESS
        elif status in ('abandoned', 'blocked'):
            return self.style.ERROR
        elif status in ('claimed', 'in_progress', 'ready_for_review'):
            return self.style.WARNING
        else:
            return self.style.NOTICE
