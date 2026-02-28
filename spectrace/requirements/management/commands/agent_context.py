"""Management command to assemble full spec context for an AgentTask."""

import json
import os
import shutil
import subprocess

from django.core.management.base import BaseCommand, CommandError

from requirements.models import AgentTask, TestRequirementLink
from requirements.validator import detect_orphan_requirements, detect_stale_links


class Command(BaseCommand):
    help = "Assemble spec context for an agent task (markdown or JSON)"

    def add_arguments(self, parser):
        parser.add_argument(
            "task_id",
            type=str,
            help="AgentTask external_id",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Write output to file",
        )

    def handle(self, *args, **options):
        task_id = options["task_id"]

        try:
            task = AgentTask.objects.get(external_id=task_id)
        except AgentTask.DoesNotExist:
            raise CommandError(f"Task not found: {task_id}")

        context = self._build_context(task)

        if options["format"] == "json":
            content = json.dumps(context, indent=2, default=str)
        else:
            content = self._render_markdown(context)

        self.stdout.write(content)

        if options["output"]:
            with open(options["output"], "w") as f:
                f.write(content)

    def _build_context(self, task):
        """Build structured context dict from task and linked requirements."""
        context = {
            "task_id": task.external_id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "done_when": task.done_when or [],
            "scope_in": task.scope_in or [],
            "scope_out": task.scope_out or [],
            "requirements": [],
        }

        for req in task.requirements.all().order_by("external_id"):
            test_links = TestRequirementLink.objects.filter(requirement=req).order_by("test_nodeid")

            # Tree hierarchy via treebeard
            parent = req.get_parent()
            children = req.get_children()

            tree = {}
            if parent:
                tree["parent"] = {
                    "external_id": parent.external_id,
                    "title": parent.title,
                }
            if children.exists():
                tree["children"] = [
                    {"external_id": c.external_id, "title": c.title}
                    for c in children.order_by("external_id")
                ]

            fret = {}
            for field in ("scope", "condition", "component", "timing", "response"):
                value = getattr(req, field, "")
                if value:
                    fret[field] = value

            req_data = {
                "external_id": req.external_id,
                "title": req.title,
                "description": req.description,
                "verification_status": req.verification_status,
                "priority": req.priority,
                "tags": req.tags or [],
                "source_file": req.source_file,
                "test_results": [
                    {"test_nodeid": link.test_nodeid, "last_status": link.last_status}
                    for link in test_links
                ],
                "tree": tree,
            }

            if fret:
                req_data["fret"] = fret

            context["requirements"].append(req_data)

        # Drift detection (inline)
        context["drift"] = self._detect_drift()

        # Lore overlay (optional)
        lore_data = self._build_lore_overlay(task)
        if lore_data is not None:
            context["lore"] = lore_data

        return context

    def _detect_drift(self):
        """Run inline drift detection and return results dict."""
        stale = detect_stale_links()
        orphans = detect_orphan_requirements()

        stale_dict = stale.to_dict()
        orphan_dict = orphans.to_dict()

        return {
            "stale_links": stale_dict,
            "orphan_requirements": orphan_dict,
        }

    def _build_lore_overlay(self, task):
        """Build lore overlay from all linked requirements' tags and titles."""
        cli = _find_lore_cli()
        if not cli:
            self.stderr.write("Warning: Lore CLI not found, skipping Lore overlay")
            return None

        tags = set()
        titles = []
        for req in task.requirements.all():
            tags.update(req.tags or [])
            titles.append(req.title)

        if not tags and not titles:
            return None

        query = " ".join(sorted(tags) + titles)
        return _lore_overlay(cli, query)

    def _render_markdown(self, context):
        """Render context dict as markdown."""
        lines = []
        lines.append("# Agent Context Bundle")
        lines.append("")
        lines.append(f"## Task: {context['title']}")
        lines.append(f"- ID: {context['task_id']}")
        lines.append(f"- Status: {context['status']}")

        if context["done_when"]:
            lines.append("- Done When:")
            for criterion in context["done_when"]:
                lines.append(f"  - [ ] {criterion}")

        if context["scope_in"]:
            lines.append(f"- Scope In: {', '.join(context['scope_in'])}")
        if context["scope_out"]:
            lines.append(f"- Scope Out: {', '.join(context['scope_out'])}")

        if context["description"]:
            lines.append("")
            lines.append(context["description"])

        lines.append("")

        if context["requirements"]:
            lines.append("## Linked Specs")
            lines.append("")

            for req in context["requirements"]:
                lines.append(f"### Spec: {req['title']}")
                lines.append(f"- ID: {req['external_id']}")
                lines.append(f"- Status: {req['verification_status']}")
                if req["priority"]:
                    lines.append(f"- Priority: {req['priority']}")
                if req["tags"]:
                    lines.append(f"- Tags: {', '.join(req['tags'])}")
                if req["source_file"]:
                    lines.append(f"- Source: {req['source_file']}")

                if "fret" in req:
                    fret_parts = [f"{k}={v}" for k, v in req["fret"].items()]
                    lines.append(f"- FRET: {', '.join(fret_parts)}")

                if req["description"]:
                    lines.append("")
                    lines.append(req["description"])

                # Tree hierarchy
                tree = req.get("tree", {})
                if tree:
                    lines.append("")
                    lines.append("#### Tree Hierarchy")
                    if "parent" in tree:
                        p = tree["parent"]
                        lines.append(f"- Parent: {p['external_id']}: {p['title']}")
                    if "children" in tree:
                        lines.append("- Children:")
                        for c in tree["children"]:
                            lines.append(f"  - {c['external_id']}: {c['title']}")

                # Test results
                if req["test_results"]:
                    lines.append("")
                    lines.append("#### Test Results")
                    for tr in req["test_results"]:
                        lines.append(f"- {tr['test_nodeid']}: {tr['last_status']}")

                lines.append("")

        # Drift section
        drift = context.get("drift", {})
        drift_items = []
        for category_key in ("stale_links", "orphan_requirements"):
            cat = drift.get(category_key, {})
            for issue in cat.get("errors", []) + cat.get("warnings", []):
                drift_items.append(issue)

        if drift_items:
            lines.append("## Drift")
            for item in drift_items:
                lines.append(f"- [{item['type']}] {item['id']}: {item['message']}")
            lines.append("")

        # Lore section
        if "lore" in context and context["lore"]:
            lines.append("## Lore Context")
            lore = context["lore"]
            if isinstance(lore, list):
                for entry in lore:
                    if isinstance(entry, dict):
                        lines.append(f"- {entry.get('title', entry.get('content', str(entry)))}")
                    else:
                        lines.append(f"- {entry}")
            elif isinstance(lore, dict):
                for key, val in lore.items():
                    lines.append(f"- {key}: {val}")
            else:
                lines.append(str(lore))
            lines.append("")

        return "\n".join(lines)


def _find_lore_cli():
    """LORE_CLI env var -> PATH lookup -> None."""
    env_path = os.environ.get("LORE_CLI")
    if env_path and os.path.isfile(env_path):
        return env_path
    path_hit = shutil.which("lore")
    if path_hit:
        return path_hit
    return None


def _lore_overlay(cli, query, project="spec-trace", limit=10):
    """Shell out to Lore CLI and return parsed JSON, or None on failure."""
    try:
        result = subprocess.run(
            [
                cli,
                "overlay",
                "--query",
                query,
                "--project",
                project,
                "--limit",
                str(limit),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None
