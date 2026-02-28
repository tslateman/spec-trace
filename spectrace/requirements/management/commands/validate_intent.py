"""Management command to record an intent validation result."""

import json
import os
import sys

from django.core.management.base import BaseCommand, CommandError

from requirements.intent_validator import record_validation, ValidationError


class Command(BaseCommand):
    help = "Record an intent-to-execution validation result from an external evaluation."

    def add_arguments(self, parser):
        parser.add_argument(
            "task_id",
            type=str,
            help="Task external ID to validate against",
        )
        parser.add_argument(
            "--commit-sha",
            type=str,
            required=True,
            help="Commit SHA or diff hash evaluated",
        )
        parser.add_argument(
            "--eval-json",
            type=str,
            required=True,
            help="Path to JSON file containing evaluation results",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        task_id = options["task_id"]
        commit_sha = options["commit_sha"]
        eval_json_path = options["eval_json"]
        fmt = options["format"]

        if not os.path.exists(eval_json_path):
            raise CommandError(f"Evaluation JSON file not found: {eval_json_path}")

        try:
            with open(eval_json_path, "r") as f:
                eval_data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON in evaluation file: {e}")

        try:
            result = record_validation(task_id, commit_sha, eval_data)
        except ValidationError as e:
            raise CommandError(str(e))

        if fmt == "json":
            output = {
                "id": result.id,
                "task_id": task_id,
                "commit_sha": commit_sha,
                "passed": result.passed,
                "scores": {
                    "strategic": result.strategic_score,
                    "opportunity": result.opportunity_score,
                    "drift": result.drift_score,
                },
                "failure_reasons": result.failure_reasons,
            }
            self.stdout.write(json.dumps(output, indent=2))
        else:
            status = self.style.SUCCESS("PASSED") if result.passed else self.style.ERROR("FAILED")
            self.stdout.write(f"Validation Result: {status}")
            self.stdout.write(f"  Strategic: {result.strategic_score}")
            self.stdout.write(f"  Opportunity: {result.opportunity_score}")
            self.stdout.write(f"  Drift: {result.drift_score}")
            
            if not result.passed and result.failure_reasons:
                self.stdout.write("\nFailure Reasons:")
                for reason in result.failure_reasons:
                    self.stdout.write(f"  - {reason}")

        if not result.passed:
            sys.exit(1)
