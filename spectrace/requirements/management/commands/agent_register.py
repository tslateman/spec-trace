"""Management command to register an agent."""

import json

from django.core.management.base import BaseCommand

from requirements.services.agent_tasks import register_agent


class Command(BaseCommand):
    help = "Register or update an agent"

    def add_arguments(self, parser):
        parser.add_argument(
            "agent_id",
            type=str,
            help="Unique agent identifier",
        )
        parser.add_argument(
            "--role",
            type=str,
            required=True,
            choices=["planner", "coder", "reviewer"],
            help="Agent role (planner, coder, reviewer)",
        )
        parser.add_argument(
            "--config",
            type=str,
            default="{}",
            help="JSON configuration string",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        agent_id = options["agent_id"]
        role = options["role"]

        try:
            config = json.loads(options["config"])
        except json.JSONDecodeError:
            self.stderr.write(self.style.ERROR(f"✗ Invalid JSON in --config: {options['config']}"))
            return

        agent = register_agent(agent_id, role, config)

        if options["format"] == "json":
            self.stdout.write(
                json.dumps(
                    {
                        "success": True,
                        "agent_id": agent.agent_id,
                        "role": agent.role,
                        "is_active": agent.is_active,
                    },
                    indent=2,
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"✓ Agent '{agent_id}' registered as {role}"))
