"""Reading the link records a test runner writes, with no database attached."""

__all__ = ["requirement_ids_of"]


def requirement_ids_of(link: dict) -> list[str]:
    """Return the requirement external IDs a link record names.

    Accepts both link shapes: `linear_issue_ids` from the pytest plugin and
    `requirement_id` from the `extract_links` command.
    """
    if "linear_issue_ids" in link:
        return link["linear_issue_ids"]
    requirement_id = link.get("requirement_id")
    return [requirement_id] if requirement_id else []
