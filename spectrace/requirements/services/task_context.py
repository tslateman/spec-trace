"""Render a Worker task-context bundle, and overlay Lore onto it.

The Worker assembles the bundle from D1. It has no subprocess, so the Lore
overlay and the markdown rendering run here, on the machine that holds the
checkout.
"""

import json
import os
import shutil
import subprocess

LORE_TIMEOUT_SECONDS = 30


def find_lore_cli() -> str | None:
    """LORE_CLI env var, then `lore` on PATH, then None."""
    env_path = os.environ.get("LORE_CLI")
    if env_path and os.path.isfile(env_path):
        return env_path
    return shutil.which("lore")


OVERLAY_TERM_FLOOR = 3


def overlay_query(tags: set[str], titles: list[str]) -> str:
    """Build the OR query Lore's search reads; every term ANDed matches nothing."""
    terms = []
    words = sorted(tags) + [word for title in titles for word in title.split()]
    for word in words:
        term = "".join(character for character in word if character.isalnum() or character in "-_")
        term = term.lower()
        if len(term) >= OVERLAY_TERM_FLOOR and term not in terms:
            terms.append(term)
    return " OR ".join(terms)


def lore_overlay(context: dict, project: str = "spec-trace", limit: int = 10) -> dict | list | None:
    """Query Lore for the linked requirements' tags and titles.

    Returns None when Lore is absent, the bundle links no requirement, or the
    query fails. Reads never block the bundle.
    """
    cli = find_lore_cli()
    if not cli:
        return None

    tags = set()
    titles = []
    for requirement in context.get("requirements", []):
        tags.update(requirement.get("tags") or [])
        titles.append(requirement["title"])

    query = overlay_query(tags, titles)
    if not query:
        return None

    command = [
        cli,
        "overlay",
        "--query",
        query,
        "--project",
        project,
        "--limit",
        str(limit),
        "--json",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=LORE_TIMEOUT_SECONDS
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None
    return None


def render_markdown(context: dict) -> str:
    """Render a task-context bundle as the markdown an agent reads."""
    lines = ["# Agent Context Bundle", ""]
    lines.extend(_task_lines(context))
    lines.append("")

    if context["requirements"]:
        lines.extend(["## Linked Specs", ""])
        for requirement in context["requirements"]:
            lines.extend(_requirement_lines(requirement))

    lines.extend(_drift_lines(context.get("drift", {})))
    lines.extend(_lore_lines(context.get("lore")))
    return "\n".join(lines)


def _task_lines(context: dict) -> list[str]:
    lines = [
        f"## Task: {context['title']}",
        f"- ID: {context['task_id']}",
        f"- Status: {context['status']}",
    ]
    if context["done_when"]:
        lines.append("- Done When:")
        lines.extend(f"  - [ ] {criterion}" for criterion in context["done_when"])
    if context["scope_in"]:
        lines.append(f"- Scope In: {', '.join(context['scope_in'])}")
    if context["scope_out"]:
        lines.append(f"- Scope Out: {', '.join(context['scope_out'])}")
    if context.get("spec_ref"):
        lines.append(f"- Spec: {context['spec_ref']}")
    if context["description"]:
        lines.extend(["", context["description"]])
    return lines


def _requirement_lines(requirement: dict) -> list[str]:
    lines = [
        f"### Spec: {requirement['title']}",
        f"- ID: {requirement['external_id']}",
        f"- Status: {requirement['verification_status']}",
    ]
    if requirement["priority"]:
        lines.append(f"- Priority: {requirement['priority']}")
    if requirement["tags"]:
        lines.append(f"- Tags: {', '.join(requirement['tags'])}")
    if requirement["source_file"]:
        lines.append(f"- Source: {requirement['source_file']}")
    if requirement.get("fret"):
        fret = ", ".join(f"{field}={value}" for field, value in requirement["fret"].items())
        lines.append(f"- FRET: {fret}")
    if requirement["description"]:
        lines.extend(["", requirement["description"]])

    tree = requirement.get("tree") or {}
    if tree:
        lines.extend(["", "#### Tree Hierarchy"])
        if "parent" in tree:
            parent = tree["parent"]
            lines.append(f"- Parent: {parent['external_id']}: {parent['title']}")
        if "children" in tree:
            lines.append("- Children:")
            lines.extend(
                f"  - {child['external_id']}: {child['title']}" for child in tree["children"]
            )

    if requirement["test_results"]:
        lines.extend(["", "#### Test Results"])
        lines.extend(
            f"- {result['test_nodeid']}: {result['last_status']}"
            for result in requirement["test_results"]
        )

    lines.append("")
    return lines


def _drift_lines(drift: dict) -> list[str]:
    issues = [
        issue
        for section in ("stale_links", "orphan_requirements")
        for issue in drift.get(section, {}).get("errors", [])
        + drift.get(section, {}).get("warnings", [])
    ]
    if not issues:
        return []
    lines = ["## Drift"]
    lines.extend(f"- [{issue['type']}] {issue['id']}: {issue['message']}" for issue in issues)
    lines.append("")
    return lines


def _lore_lines(lore) -> list[str]:
    if not lore:
        return []
    lines = ["## Lore Context"]
    if isinstance(lore, dict) and "items" in lore:
        lore = lore["items"]
    if isinstance(lore, list):
        for entry in lore:
            if isinstance(entry, dict):
                lines.append(f"- {entry.get('title', entry.get('content', str(entry)))}")
            else:
                lines.append(f"- {entry}")
    elif isinstance(lore, dict):
        lines.extend(f"- {key}: {value}" for key, value in lore.items())
    else:
        lines.append(str(lore))
    lines.append("")
    return lines
