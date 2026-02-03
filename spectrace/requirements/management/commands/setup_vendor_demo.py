"""Django management command for setting up vendor demo data."""
from django.core.management.base import BaseCommand

from requirements.services.vendor_demo import setup_vendor_demo


class Command(BaseCommand):
    """Set up demo data for vendor coverage page."""

    help = 'Set up demo data for vendor coverage page with realistic scenarios'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            '--no-clear',
            action='store_true',
            help='Do not clear existing demo data first'
        )

    def handle(self, *args, **options):
        """Execute the vendor demo setup."""
        clear = not options['no_clear']

        self.stdout.write("Setting up vendor demo data...")
        result = setup_vendor_demo(clear=clear)

        self.stdout.write(self.style.SUCCESS(
            f"Demo setup complete!\n"
            f"  Vendors created: {result['vendors_created']}\n"
            f"  Validations created: {result['validations_created']}\n"
            f"  Results created: {result['results_created']}\n"
            f"  Runs cleared: {result['runs_cleared']}"
        ))
