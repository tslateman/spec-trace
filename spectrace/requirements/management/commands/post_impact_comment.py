"""Post the impact gate's report as a pull request comment, updating in place."""

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...services.github_comment import DEFAULT_API_URL, upsert_pr_comment
from ...services.impact_markdown import MARKER_PREFIX


def read_pr_number(event_path: str | None) -> int:
    """Read the pull request number from the GitHub Actions event payload.

    Raises:
        CommandError: If the payload is absent or describes no pull request.
    """
    if not event_path:
        raise CommandError("Pass --pr, or run with GITHUB_EVENT_PATH set by GitHub Actions")

    path = Path(event_path)
    if not path.is_file():
        raise CommandError(f"GITHUB_EVENT_PATH points at no file: {path}")

    event = json.loads(path.read_text())
    pull_request = event.get("pull_request")
    if not pull_request or "number" not in pull_request:
        raise CommandError(f"Event payload {path} carries no pull_request number")
    return int(pull_request["number"])


class Command(BaseCommand):
    help = "Post or update the impact gate comment on a pull request"

    def add_arguments(self, parser):
        parser.add_argument(
            "--body-file",
            required=True,
            help="File holding the Markdown report produced by code_impact_analysis",
        )
        parser.add_argument(
            "--repo",
            default=None,
            help="owner/name (defaults to GITHUB_REPOSITORY)",
        )
        parser.add_argument(
            "--pr",
            type=int,
            default=None,
            help="Pull request number (defaults to the GitHub Actions event payload)",
        )
        parser.add_argument(
            "--api-url",
            default=os.environ.get("GITHUB_API_URL", DEFAULT_API_URL),
            help="GitHub API base URL",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Validate the body and print the target without calling GitHub",
        )

    def handle(self, *args, **options):
        body_path = Path(options["body_file"])
        if not body_path.is_file():
            raise CommandError(f"No report at {body_path}. Did the analysis step run?")

        body = body_path.read_text()
        if MARKER_PREFIX not in body:
            raise CommandError(
                f"{body_path} carries no {MARKER_PREFIX} marker, so the analysis never "
                "finished. Refusing to post a report that would read as no impact."
            )

        repo = options["repo"] or os.environ.get("GITHUB_REPOSITORY")
        if not repo:
            raise CommandError("Pass --repo, or set GITHUB_REPOSITORY")

        pr_number = options["pr"] or read_pr_number(os.environ.get("GITHUB_EVENT_PATH"))

        if options["dry_run"]:
            self.stdout.write(
                f"Would upsert a {len(body)} character comment on {repo}#{pr_number}\n"
            )
            return

        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise CommandError("Set GITHUB_TOKEN to the workflow token")

        result = upsert_pr_comment(
            repo=repo,
            pr_number=pr_number,
            token=token,
            body=body,
            marker_prefix=MARKER_PREFIX,
            api_url=options["api_url"],
        )
        self.stdout.write(f"{result.action} comment {result.comment_id}: {result.url}\n")
