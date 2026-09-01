"""Tests for the Markdown renderer behind the pull request impact gate."""

import pytest

from requirements.services.impact_analyzer import CodeImpactResult
from requirements.services.impact_markdown import MARKER_PREFIX, marker, render_markdown


@pytest.fixture
def result():
    return CodeImpactResult(
        changed_files={"local": ["a.py", "b.py"]},
        blast={
            "affected_requirements": ["REQ-A-001", "REQ-A-002"],
            "affected_modules": ["src/one.py"],
            "affected_projects": ["local"],
        },
        affected_tests=["tests/test_one.py::test_a", "tests/test_two.py::test_b"],
        risk_score=0.86,
        risk_level="critical",
        edge_summary={"annotated": 64, "inferred": 4, "contract": 9, "dependency": 3},
        traversed_edges={"annotated": 12, "inferred": 1, "contract": 2, "dependency": 1},
    )


def test_marker__names_the_risk_level():
    assert marker("high") == "<!-- spectrace-impact-gate risk=high -->"


def test_render_markdown__opens_with_the_hidden_marker(result):
    body = render_markdown(result, "base", "head")

    assert body.splitlines()[0] == "<!-- spectrace-impact-gate risk=critical -->"
    assert MARKER_PREFIX in body


def test_render_markdown__states_the_risk_level_and_score(result):
    body = render_markdown(result, "base", "head")

    assert "**Risk:** CRITICAL (0.86)" in body


def test_render_markdown__names_the_compared_refs(result):
    body = render_markdown(result, "abc123", "def456")

    assert "**Comparing:** `abc123` .. `def456`" in body


def test_render_markdown__lists_affected_requirements(result):
    body = render_markdown(result, "base", "head")

    assert "### Affected Requirements (2)" in body
    assert "- REQ-A-001" in body
    assert "- REQ-A-002" in body


def test_render_markdown__reports_the_edges_that_carried_the_change(result):
    body = render_markdown(result, "base", "head")

    assert "annotated: 12 | contract: 2 | inferred: 1" in body


def test_render_markdown__omits_the_whole_graph_edge_inventory(result):
    body = render_markdown(result, "base", "head")

    assert "64" not in body


def test_render_markdown__truncates_a_long_test_list_with_a_count(result):
    result.affected_tests = [f"tests/test_{n}.py::test_it" for n in range(270)]

    body = render_markdown(result, "base", "head")

    assert "### Affected Tests (270)" in body
    assert "…and 255 more." in body
    assert body.count("pytest tests/") == 15


def test_render_markdown__truncates_a_long_requirement_list_with_a_count(result):
    result.blast["affected_requirements"] = [f"REQ-A-{n:03d}" for n in range(100)]

    body = render_markdown(result, "base", "head")

    assert "### Affected Requirements (100)" in body
    assert "- …and 75 more" in body


def test_render_markdown__keeps_a_short_list_whole(result):
    body = render_markdown(result, "base", "head")

    assert "more" not in body.split("### Affected Requirements")[1].split("###")[0]


def test_render_markdown__collapses_the_changed_file_list(result):
    body = render_markdown(result, "base", "head")

    assert "<summary>Changed Files (2)</summary>" in body
    assert "</details>" in body


def test_render_markdown__says_the_gate_only_warns(result):
    body = render_markdown(result, "base", "head")

    assert "warns, it does not block" in body


def test_render_markdown__marks_an_empty_diff_without_dropping_the_marker():
    empty = CodeImpactResult(changed_files={}, blast={}, affected_tests=[])

    body = render_markdown(empty, "base", "head")

    assert body.startswith("<!-- spectrace-impact-gate risk=low -->")
    assert "**Risk:** LOW (0.00)" in body
    assert "No code files changed." in body


def test_render_markdown__honors_explicit_limits(result):
    result.affected_tests = ["a::x", "b::x", "c::x"]

    body = render_markdown(result, "base", "head", list_limit=1, test_limit=2)

    assert "…and 1 more." in body
    assert "- …and 1 more" in body


def test_render_markdown__names_a_dependency_whose_provider_was_absent(result):
    result.unresolved_dependencies = [
        {
            "consumer": "praxis",
            "module": "src/praxis/spectrace.py",
            "provider": "spectrace",
            "surface": "db/requirements_requirement",
        }
    ]

    body = render_markdown(result, "HEAD~1", "HEAD")

    assert "### Dependencies Not Analysed" in body
    assert "`spectrace:db/requirements_requirement`" in body


def test_render_markdown__omits_the_unanalysed_section_when_every_provider_was_loaded(result):
    assert "Dependencies Not Analysed" not in render_markdown(result, "HEAD~1", "HEAD")
