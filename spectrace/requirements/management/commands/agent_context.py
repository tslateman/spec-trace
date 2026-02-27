"""Management command to assemble full spec context for an AgentTask."""

import json

from django.core.management.base import BaseCommand, CommandError

from requirements.models import AgentTask, TestRequirementLink


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

    def handle(self, *args, **options):
        task_id = options["task_id"]

        try:
            task = AgentTask.objects.get(external_id=task_id)
        except AgentTask.DoesNotExist:
            raise CommandError(f"Task not found: {task_id}")

        context = self._build_context(task)

        if options["format"] == "json":
            self.stdout.write(json.dumps(context, indent=2, default=str))
        else:
            self.stdout.write(self._render_markdown(context))

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
            depends_on = list(
                req.depends_on.values_list("external_id", flat=True).order_by("external_id")
            )
            depended_by = list(
                req.depended_by.values_list("external_id", flat=True).order_by("external_id")
            )

            fret = {}
            for field in ("scope", "condition", "component", "timing", "response"):
                value = getattr(req, field, "")
                if value:
                    fret[field] = value

            req_data = {
                "external_id": req.external_id,
                "title": req.title,
                "verification_status": req.verification_status,
                "priority": req.priority,
                "test_results": [
                    {"test_nodeid": link.test_nodeid, "last_status": link.last_status}
                    for link in test_links
                ],
                "depends_on": depends_on,
                "depended_by": depended_by,
            }

            if fret:
                req_data["fret"] = fret

            context["requirements"].append(req_data)

        return context

    def _render_markdown(self, context):
        """Render context dict as markdown."""
        lines = []
        lines.append(f"# Task: {context['title']}")
        lines.append("")

        if context["description"]:
            lines.append("## Description")
            lines.append(context["description"])
            lines.append("")

        if context["done_when"]:
            lines.append("## Done When")
            for criterion in context["done_when"]:
                lines.append(f"- [ ] {criterion}")
            lines.append("")

        if context["scope_in"] or context["scope_out"]:
            lines.append("## Scope")
            if context["scope_in"]:
                lines.append(f"**In scope:** {', '.join(context['scope_in'])}")
            if context["scope_out"]:
                lines.append(f"**Out of scope:** {', '.join(context['scope_out'])}")
            lines.append("")

        if context["requirements"]:
            lines.append("## Linked Requirements")
            lines.append("")

            for req in context["requirements"]:
                lines.append(f"### {req['external_id']}: {req['title']}")
                lines.append(f"- Status: {req['verification_status']}")
                if req["priority"]:
                    lines.append(f"- Priority: {req['priority']}")

                if "fret" in req:
                    fret_parts = [f"{k}={v}" for k, v in req["fret"].items()]
                    lines.append(f"- FRET: {', '.join(fret_parts)}")

                if req["test_results"]:
                    lines.append("")
                    lines.append("#### Test Results")
                    for tr in req["test_results"]:
                        lines.append(f"- {tr['test_nodeid']}: {tr['last_status']}")

                if req["depends_on"] or req["depended_by"]:
                    lines.append("")
                    lines.append("#### Dependencies")
                    if req["depends_on"]:
                        lines.append(f"- Depends on: {', '.join(req['depends_on'])}")
                    if req["depended_by"]:
                        lines.append(f"- Depended by: {', '.join(req['depended_by'])}")

                lines.append("")

        return "\n".join(lines)
