"""Tests for the Lore overlay query the task-context bundle carries."""

from unittest.mock import patch

from requirements.services.task_context import lore_overlay, overlay_query, render_markdown


def test_overlay_query__ors_every_tag_and_title_word():
    query = overlay_query({"pricing", "checkout"}, ["Apply a discount code at checkout"])

    assert query == "checkout OR pricing OR apply OR discount OR code"


def test_overlay_query__drops_punctuation_and_short_words():
    assert overlay_query(set(), ["Refund a `charge`, at once"]) == "refund OR charge OR once"


def test_overlay_query__is_empty_when_the_bundle_links_nothing():
    assert overlay_query(set(), []) == ""


@patch("requirements.services.task_context.find_lore_cli", autospec=True)
@patch("requirements.services.task_context.subprocess.run", autospec=True)
def test_lore_overlay__passes_the_or_query_to_lore(mock_run, mock_cli):
    mock_cli.return_value = "/bin/lore"
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = '{"items": []}'
    context = {"requirements": [{"title": "Apply a discount code", "tags": ["checkout"]}]}

    assert lore_overlay(context) == {"items": []}
    command = mock_run.call_args[0][0]
    assert command[command.index("--query") + 1] == "checkout OR apply OR discount OR code"


def test_render_markdown__lists_the_overlay_items_by_title():
    context = {
        "task_id": "task-refund",
        "title": "Refund a discounted order",
        "status": "draft",
        "description": "",
        "done_when": [],
        "scope_in": [],
        "scope_out": [],
        "requirements": [],
        "lore": {
            "query": "refund",
            "items": [{"type": "decision", "title": "task-discount merged"}],
        },
    }

    rendered = render_markdown(context)

    assert "## Lore Context\n- task-discount merged" in rendered
