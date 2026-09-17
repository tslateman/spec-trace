"""Draft tasks from a roadmap item or from the requirements no test covers."""

import re
from dataclasses import dataclass
from pathlib import Path

ITEM_HEADING = re.compile(r"^### (\d+)\.\s+(.+)$", re.MULTILINE)
DONE_WHEN = re.compile(r"\*\*Done when:\*\*\s*(.+?)(?:\n\n|\Z)", re.DOTALL)
CRITERION = re.compile(r",\s+and\s+|(?<=\.)\s+(?=[A-Z`])")
REQUIREMENT_ID = re.compile(r"\bREQ-[A-Z0-9][A-Z0-9-]*\b")
PATH_TOKEN = re.compile(
    r"[\w./-]*[\w-]+\.(?:md|py|ts|tsx|yml|yaml|json|sh|toml)|[\w.-]+(?:/[\w.-]+)+"
)
GATE_FIELDS = ("requirements", "scope_in", "done_when")


class PlannerRefusal(Exception):
    """The planner found nothing a reviewer could judge."""


@dataclass(frozen=True)
class RoadmapItem:
    """One numbered roadmap item: its heading, its prose, and its completion sentence."""

    number: str
    title: str
    body: str
    done_when: str
    source: str


def read_roadmap(path: Path) -> list[RoadmapItem]:
    """Read every numbered item from a roadmap file, newest section first."""
    text = path.read_text()
    headings = list(ITEM_HEADING.finditer(text))
    items = []
    for heading, following in zip(headings, [*headings[1:], None], strict=True):
        section = text[heading.end() : following.start() if following else len(text)]
        done_when = DONE_WHEN.search(section)
        body = section[: done_when.start()] if done_when else section
        items.append(
            RoadmapItem(
                number=heading.group(1),
                title=heading.group(2).strip(),
                body=body.strip(),
                done_when=done_when.group(1).strip() if done_when else "",
                source=path.name,
            )
        )
    return items


def find_item(items: list[RoadmapItem], name: str) -> RoadmapItem:
    """Find one item by its number or by text from its title."""
    wanted = name.strip().lower()
    for item in items:
        if item.number == wanted or wanted in item.title.lower():
            return item
    raise PlannerRefusal(f"the roadmap names no item matching {name!r}")


def criteria(done_when: str) -> list[str]:
    """Split a roadmap item's completion sentence into falsifiable criteria."""
    return [sentence(part) for part in CRITERION.split(done_when) if part.strip()]


def sentence(part: str) -> str:
    text = " ".join(part.split()).rstrip(".")
    return text[:1].upper() + text[1:]


def named_paths(body: str, repo: Path) -> list[str]:
    """Collect the paths an item names that the checkout actually holds."""
    found = []
    for match in PATH_TOKEN.finditer(body):
        token = match.group(0).rstrip(".,")
        if token not in found and (repo / token).exists():
            found.append(token)
    return found


def first_paragraph(text: str) -> str:
    """Take a spec body's opening prose, leaving its heading behind."""
    for block in text.split("\n\n"):
        stripped = block.strip()
        if stripped and not stripped.startswith("#"):
            return " ".join(stripped.split())
    return ""


def requirement_ids(text: str) -> list[str]:
    found = []
    for match in REQUIREMENT_ID.finditer(text):
        if match.group(0) not in found:
            found.append(match.group(0))
    return found


def merged(first, second) -> list[str]:
    return list(dict.fromkeys([*first, *second]))


def slug(title: str, width: int = 48) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    kept = []
    for word in words:
        if len("-".join([*kept, word])) > width:
            break
        kept.append(word)
    return "-".join(kept)


def complete_spec(draft: dict) -> dict:
    """Return the draft when it carries what the spec gate reads, else refuse."""
    missing = [field for field in GATE_FIELDS if not draft[field]]
    if missing:
        raise PlannerRefusal(
            f"{draft['task_id']} cannot leave draft until its spec names {', '.join(missing)}"
        )
    return draft


def roadmap_draft(
    item: RoadmapItem,
    agent_id: str,
    repo: Path,
    requirements=(),
    scope_in=(),
    scope_out=(),
    prefix: str = "plan",
    max_attempts: int = 2,
) -> dict:
    """Build one draft task from a roadmap item.

    The item's prose becomes the description a reviewer judges, its completion
    sentence becomes `done_when`, and the paths it names that the checkout holds
    become `scope_in`. `requirements` and `scope_in` add to what the item names.
    """
    return complete_spec(
        {
            "agent_id": agent_id,
            "task_id": f"{prefix}-{item.number}-{slug(item.title)}",
            "title": item.title,
            "description": item.body,
            "requirements": merged(requirement_ids(f"{item.body}\n{item.done_when}"), requirements),
            "done_when": criteria(item.done_when),
            "scope_in": merged(named_paths(item.body, repo), scope_in),
            "scope_out": list(scope_out),
            "spec_ref": f"{item.source}#{item.number}-{slug(item.title)}",
            "max_attempts": max_attempts,
        }
    )


def untested_requirements(client, project: str | None = None, limit: int = 5) -> list[dict]:
    """Read the requirements the Worker counts as gaps: specified, and no test covers them."""
    params = {"verification_status": "untested", "per_page": limit}
    if project:
        params["project"] = project
    response = client.session.get(
        f"{client.api_url}/api/v1/specs/", params=params, timeout=client.timeout
    )
    response.raise_for_status()
    return response.json()["data"]["requirements"]


def gap_draft(
    requirement: dict,
    agent_id: str,
    scope_in=(),
    scope_out=(),
    prefix: str = "plan",
    max_attempts: int = 2,
) -> dict:
    """Build one draft task that covers a single untested requirement with a test."""
    external_id = requirement["external_id"]
    source_file = requirement["source_file"]
    return complete_spec(
        {
            "agent_id": agent_id,
            "task_id": f"{prefix}-{external_id.lower()}",
            "title": f"Cover {external_id} with a passing linked test",
            "description": (
                f"{external_id} {requirement['title']} is {requirement['verification_status']}:"
                f" no test claims it. {first_paragraph(requirement['description'])}"
            ).strip(),
            "requirements": [external_id],
            "done_when": [
                f"A test links to {external_id} and passes",
                f"The Worker reports {external_id} as passing",
            ],
            "scope_in": merged([source_file] if source_file else [], scope_in),
            "scope_out": list(scope_out),
            "spec_ref": f"{source_file}#{external_id}" if source_file else external_id,
            "max_attempts": max_attempts,
        }
    )


def gap_drafts(
    requirements: list[dict],
    agent_id: str,
    scope_in=(),
    scope_out=(),
    prefix: str = "plan",
    max_attempts: int = 2,
) -> list[dict]:
    """Build one draft task per untested requirement."""
    if not requirements:
        raise PlannerRefusal("the Worker reports no untested requirement to draft from")
    return [
        gap_draft(requirement, agent_id, scope_in, scope_out, prefix, max_attempts)
        for requirement in requirements
    ]
