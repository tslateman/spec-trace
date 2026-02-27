"""Management command to expire stale task leases."""

import json

from django.core.management.base import BaseCommand

from requirements.services.agent_tasks import expire_stale_leases


class Command(BaseCommand):
    help = "Expire tasks with past lease timestamps (for cron jobs)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be expired without modifying",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        results = expire_stale_leases(dry_run=dry_run)

        if options["format"] == "json":
            self.stdout.write(
                json.dumps(
                    {
                        "dry_run": dry_run,
                        "expired_count": len(results),
                        "tasks": results,
                    },
                    indent=2,
                )
            )
        else:
            self._output_text(results, dry_run)

    def _output_text(self, results, dry_run):
        """Output human-readable results."""
        if not results:
            self.stdout.write("No expired leases found.")
            return

        action = "Would release" if dry_run else "Released"
        self.stdout.write(f"{action} {len(results)} task(s):\n")

        for task in results:
            if task.get("error"):
                self.stdout.write(self.style.ERROR(f"  ✗ {task['task_id']}: {task['error']}"))
            elif task.get("released") or dry_run:
                status = "(dry run)" if dry_run else "(released)"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {task['task_id']} claimed by {task['claimed_by']} {status}"
                    )
                )
