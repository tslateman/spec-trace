"""Tests for upserting the impact gate's pull request comment."""

import json
from unittest.mock import patch

import pytest

from requirements.services.github_comment import (
    find_marked_comment,
    upsert_pr_comment,
)

MARKER = "<!-- spectrace-impact-gate"


class FakeResponse:
    """Stand-in for the file-like object urlopen returns."""

    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


class FakeApi:
    """Record every call and answer it from a scripted list of payloads."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def __call__(self, request, timeout=None):
        body = json.loads(request.data.decode()) if request.data else None
        self.calls.append((request.method, request.full_url, body, dict(request.header_items())))
        return FakeResponse(self.payloads.pop(0))


@pytest.fixture
def gate_comment():
    return {"id": 7, "body": f"{MARKER} risk=high -->\nold", "html_url": "https://gh/c/7"}


def test_find_marked_comment__returns_the_comment_carrying_the_marker(gate_comment):
    api = FakeApi([[{"id": 1, "body": "unrelated"}, gate_comment]])

    with patch("requirements.services.github_comment.urlopen", new=api):
        found = find_marked_comment("o/r", 42, "tok", MARKER, api_url="https://api")

    assert found == gate_comment


def test_find_marked_comment__returns_none_when_no_comment_carries_the_marker():
    api = FakeApi([[{"id": 1, "body": "unrelated"}]])

    with patch("requirements.services.github_comment.urlopen", new=api):
        assert find_marked_comment("o/r", 42, "tok", MARKER, api_url="https://api") is None


def test_find_marked_comment__returns_none_when_the_pull_request_has_no_comments():
    api = FakeApi([[]])

    with patch("requirements.services.github_comment.urlopen", new=api):
        assert find_marked_comment("o/r", 42, "tok", MARKER, api_url="https://api") is None


def test_find_marked_comment__reads_a_second_page_when_the_first_one_fills(gate_comment):
    api = FakeApi([[{"id": n, "body": "unrelated"} for n in range(100)], [gate_comment]])

    with patch("requirements.services.github_comment.urlopen", new=api):
        found = find_marked_comment("o/r", 42, "tok", MARKER, api_url="https://api")

    assert found == gate_comment
    assert "page=2" in api.calls[1][1]


def test_upsert_pr_comment__creates_a_comment_when_none_is_marked():
    created = {"id": 11, "html_url": "https://gh/c/11"}
    api = FakeApi([[], created])

    with patch("requirements.services.github_comment.urlopen", new=api):
        result = upsert_pr_comment("o/r", 42, "tok", "body", MARKER, api_url="https://api")

    assert result.action == "created"
    assert result.comment_id == 11
    assert result.url == "https://gh/c/11"
    assert api.calls[1][0] == "POST"
    assert api.calls[1][1] == "https://api/repos/o/r/issues/42/comments"
    assert api.calls[1][2] == {"body": "body"}


def test_upsert_pr_comment__edits_the_marked_comment_instead_of_stacking(gate_comment):
    patched = {"id": 7, "html_url": "https://gh/c/7"}
    api = FakeApi([[gate_comment], patched])

    with patch("requirements.services.github_comment.urlopen", new=api):
        result = upsert_pr_comment("o/r", 42, "tok", "fresh", MARKER, api_url="https://api")

    assert result.action == "updated"
    assert result.comment_id == 7
    assert api.calls[1][0] == "PATCH"
    assert api.calls[1][1] == "https://api/repos/o/r/issues/comments/7"
    assert api.calls[1][2] == {"body": "fresh"}


def test_upsert_pr_comment__authenticates_with_the_workflow_token():
    api = FakeApi([[], {"id": 11, "html_url": "https://gh/c/11"}])

    with patch("requirements.services.github_comment.urlopen", new=api):
        upsert_pr_comment("o/r", 42, "sekret", "body", MARKER, api_url="https://api")

    headers = api.calls[0][3]
    assert headers["Authorization"] == "Bearer sekret"
    assert headers["Accept"] == "application/vnd.github+json"
