"""Management command to set up impact analysis demo data."""

from django.core.management.base import BaseCommand

from requirements.services.impact_analyzer import setup_impact_demo


class Command(BaseCommand):
    help = "Set up demo data for impact analysis (branch, test links, spec changes)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Setting up impact analysis demo..."))

        result = setup_impact_demo()

        if result["specs_committed"]:
            self.stdout.write("  Specs committed to git")
        self.stdout.write(f"  Test links created: {result['test_links_created']}")
        self.stdout.write(f"  Demo branch: {result['demo_branch']}")

        self.stdout.write(self.style.SUCCESS("\nDemo data ready!"))
        self.stdout.write(f"\nRun: spectrace impact {result['base_ref']} {result['head_ref']}")
