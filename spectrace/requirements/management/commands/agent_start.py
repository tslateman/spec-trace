"""Management command for agents to start work on a claimed task."""

import json
import sys

from django.core.management.base import BaseCommand

from requirements.services.agent_tasks import TransitionError, start_task


class Command(BaseCommand):
    help = "Start work on a claimed task (CLAIMED → IN_PROGRESS)"

    def add_arguments(self, parser):
        parser.add_argument(
            "task_id",
            type=str,
            help="Task external ID to start",
        )
        parser.add_argument(
            "--agent",
            type=str,
            required=True,
            help="Agent ID starting the task",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        task_id = options["task_id"]
        agent_id = options["agent"]

        try:
            result = start_task(task_id, agent_id)

            if options["format"] == "json":
                self.stdout.write(json.dumps(result.to_dict(), indent=2))
            else:
                self.stdout.write(self.style.SUCCESS(f"✓ {result.message}"))

        except TransitionError as e:
            if options["format"] == "json":
                self.stdout.write(
                    json.dumps(
                        {
                            "success": False,
                            "error": str(e),
                            "code": e.code,
                        },
                        indent=2,
                    )
                )
            else:
                self.stderr.write(self.style.ERROR(f"✗ {e}"))
            sys.exit(1)
