"""Management command for agents to submit work for review."""

import json
import sys

from django.core.management.base import BaseCommand

from requirements.services.agent_tasks import submit_for_review, TransitionError


class Command(BaseCommand):
    help = 'Submit work for review (IN_PROGRESS → READY_FOR_REVIEW)'

    def add_arguments(self, parser):
        parser.add_argument(
            'task_id',
            type=str,
            help='Task external ID to submit',
        )
        parser.add_argument(
            '--agent',
            type=str,
            required=True,
            help='Agent ID submitting the work',
        )
        parser.add_argument(
            '--commit-sha',
            type=str,
            required=True,
            help='Git commit SHA of the submission',
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
        commit_sha = options['commit_sha']

        try:
            result = submit_for_review(task_id, agent_id, commit_sha)

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
