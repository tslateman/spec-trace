"""Django management command for importing test-Linear issue links."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from requirements.models import Requirement, TestRequirementLink


def _requirement_ids(link: dict) -> list[str]:
    """Return the requirement external IDs a link record names.

    Accepts both link shapes: `linear_issue_ids` from the pytest plugin and
    `requirement_id` from the `extract_links` command.
    """
    if "linear_issue_ids" in link:
        return link["linear_issue_ids"]
    requirement_id = link.get("requirement_id")
    return [requirement_id] if requirement_id else []


class Command(BaseCommand):
    """Import test-Linear issue links from .spectrace/links.json."""

    help = "Import test-Linear issue links from pytest marker extraction"

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            "links_json",
            type=str,
            help="Path to links JSON file (e.g., .spectrace/links.json)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without making changes",
        )

    def handle(self, *args, **options):
        """Execute the import workflow."""
        links_path = Path(options["links_json"])
        if not links_path.exists():
            raise CommandError(f"Links JSON file not found: {links_path}")

        # Load links JSON
        with open(links_path) as f:
            data = json.load(f)

        links = data.get("links", [])
        if not links:
            self.stdout.write(self.style.WARNING("No links found in JSON file"))
            return

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        # Track statistics
        created_count = 0
        updated_count = 0
        not_found_issues = set()

        for link in links:
            test_nodeid = link["test_nodeid"]
            issue_ids = _requirement_ids(link)

            for issue_id in issue_ids:
                # Look up requirement by external_id (Linear identifier like CAN-1234)
                try:
                    requirement = Requirement.objects.get(external_id=issue_id)
                except Requirement.DoesNotExist:
                    not_found_issues.add(issue_id)
                    continue

                if dry_run:
                    self.stdout.write(f"  Would link: {test_nodeid} → {issue_id}")
                    continue

                # Create or update the link
                link_obj, created = TestRequirementLink.objects.update_or_create(
                    test_nodeid=test_nodeid,
                    requirement=requirement,
                    defaults={
                        "needs_review": False,
                        "review_reason": "",
                    },
                )

                if created:
                    created_count += 1
                    link_obj.needs_review = True
                    link_obj.review_reason = "new link"
                    link_obj.save()
                else:
                    updated_count += 1

        # Report results
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Would create/update links for {len(links)} tests")
            )
        elif created_count == 0 and updated_count == 0:
            raise CommandError(
                f"{len(links)} links in {links_path} resolved to no requirement. "
                f"Unmatched IDs: {', '.join(sorted(not_found_issues)) or 'none named'}"
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {created_count} new links, updated {updated_count} existing links"
                )
            )

        if not_found_issues:
            self.stdout.write(
                self.style.WARNING(
                    f"Requirements not found for issue IDs: {', '.join(sorted(not_found_issues))}"
                )
            )
            self.stdout.write(
                "  Hint: Run 'python manage.py import_linear' to import requirements from Linear"
            )
