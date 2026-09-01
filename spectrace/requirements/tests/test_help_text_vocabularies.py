"""Every field whose help text names a vocabulary declares that vocabulary as choices.

`Requirement.status`, `TestRequirementLink.last_status` and `Requirement.priority`
each named their legal values in help text alone. Prose publishes nothing, so
`generate_contract` emitted no `enum/` surface and a renamed value broke a
consumer reading the database in silence. Three instances make a pattern; this
scan fails on the fourth.

The signal is a parenthesised list of bare lowercase tokens — the shape
`(draft, active, deprecated)` — in the help text of a `CharField` that declares
no choices. A parenthesised example (`e.g., 'coder-1'`) and an open list
(`runs analyzed, test results, etc.`) name no vocabulary, so the scan skips both.
"""

import inspect
import re
from pathlib import Path

from django.apps import apps
from django.db import models

from requirements import models as requirements_models

REPO_ROOT = Path(requirements_models.__file__).resolve().parents[2]

PARENTHESISED_LIST = re.compile(r"\(([^()]*,[^()]*)\)")
BARE_TOKEN = re.compile(r"^[a-z][a-z0-9_-]*$")
OPEN_LIST_MARKERS = ("e.g.", "etc.", "i.e.")

EXEMPT = {
    "requirements.SLO.budgeting_method": (
        "OpenSLO vocabulary (occurrences, timeslices) that the field declares nowhere. "
        "Publishing it is separate work; this scan holds the line meanwhile."
    ),
    "requirements.CorpusEntryVersion.content_hash": (
        "The list names the fields the hash covers, not values the column stores."
    ),
}


def undeclared_vocabulary(field) -> list[str] | None:
    """Return the values a field's help text enumerates without declaring them as choices."""
    if not isinstance(field, models.CharField) or field.choices:
        return None

    help_text = str(field.help_text)
    for match in PARENTHESISED_LIST.finditer(help_text):
        listed = match.group(1)
        if any(marker in listed for marker in OPEN_LIST_MARKERS):
            continue
        items = [item.strip() for item in listed.split(",")]
        if len(items) > 1 and all(BARE_TOKEN.match(item) for item in items):
            return items
    return None


def scan_fields() -> dict[str, list[str]]:
    """Map each field this repository defines to the vocabulary its help text hides."""
    found = {}
    for model in apps.get_models(include_auto_created=True):
        if not Path(inspect.getfile(model)).resolve().is_relative_to(REPO_ROOT):
            continue
        for field in model._meta.concrete_fields:
            values = undeclared_vocabulary(field)
            if values:
                found[f"{model._meta.label}.{field.name}"] = values
    return found


def test_scan_fields__finds_no_vocabulary_outside_the_exempt_set():
    found = scan_fields()

    undeclared = {name: values for name, values in found.items() if name not in EXEMPT}
    assert not undeclared, (
        "Help text names a vocabulary the field declares nowhere, so the contract "
        f"snapshot publishes no enum surface for it: {undeclared}. "
        "Attach a TextChoices class, add a migration, and regenerate contract.snapshot.json."
    )


def test_scan_fields__still_finds_every_exempt_field():
    found = scan_fields()

    assert set(EXEMPT) <= set(found), (
        f"These fields no longer hide a vocabulary: {set(EXEMPT) - set(found)}. "
        "Drop them from EXEMPT."
    )


def test_undeclared_vocabulary__flags_a_charfield_naming_values_in_prose():
    field = models.CharField(max_length=20, help_text="Priority level (high, medium, low)")

    assert undeclared_vocabulary(field) == ["high", "medium", "low"]


def test_undeclared_vocabulary__passes_a_field_that_declares_its_choices():
    field = models.CharField(
        max_length=20,
        choices=[("high", "High"), ("medium", "Medium"), ("low", "Low")],
        help_text="Priority level (high, medium, low)",
    )

    assert undeclared_vocabulary(field) is None


def test_undeclared_vocabulary__passes_a_parenthesised_example():
    field = models.CharField(
        max_length=50, help_text="Unique agent identifier (e.g., 'coder-1', 'reviewer-opus')"
    )

    assert undeclared_vocabulary(field) is None


def test_undeclared_vocabulary__passes_an_open_list():
    field = models.CharField(
        max_length=50, help_text="Additional context (commit SHA, review feedback, etc.)"
    )

    assert undeclared_vocabulary(field) is None
