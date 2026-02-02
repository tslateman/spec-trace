"""Management command to set up flow status dashboard demo data."""

from django.core.management.base import BaseCommand

from requirements.flow_status import setup_demo_data


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

        result = setup_demo_data(clear=options['clear'])

        self.stdout.write(f'  Flows synced: {result["flows_synced"]}')
        if result['runs_cleared']:
            self.stdout.write(f'  Runs cleared: {result["runs_cleared"]}')
        self.stdout.write(f'  Runs created: {len(result["runs_created"])}')

        self.stdout.write(self.style.SUCCESS('\nDemo data ready!'))
        self.stdout.write('\nView at: /admin/flow-status/')
