"""Post or update a single pull request comment identified by a hidden marker."""

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

DEFAULT_API_URL = "https://api.github.com"
PAGE_SIZE = 100
MAX_PAGES = 10


@dataclass
class CommentResult:
    """Outcome of an upsert: whether a comment was created or updated."""

    action: str
    comment_id: int
    url: str


def _api_call(url: str, token: str, method: str = "GET", payload: dict | None = None) -> object:
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def find_marked_comment(
    repo: str,
    pr_number: int,
    token: str,
    marker_prefix: str,
    api_url: str = DEFAULT_API_URL,
) -> dict | None:
    """Return the first comment on the pull request carrying the marker."""
    for page in range(1, MAX_PAGES + 1):
        url = f"{api_url}/repos/{repo}/issues/{pr_number}/comments?per_page={PAGE_SIZE}&page={page}"
        comments = _api_call(url, token)
        if not comments:
            return None
        for comment in comments:
            if marker_prefix in comment.get("body", ""):
                return comment
        if len(comments) < PAGE_SIZE:
            return None
    return None


def upsert_pr_comment(
    repo: str,
    pr_number: int,
    token: str,
    body: str,
    marker_prefix: str,
    api_url: str = DEFAULT_API_URL,
) -> CommentResult:
    """Create the gate's comment, or edit the one it left on an earlier push."""
    existing = find_marked_comment(repo, pr_number, token, marker_prefix, api_url)

    if existing:
        url = f"{api_url}/repos/{repo}/issues/comments/{existing['id']}"
        updated = _api_call(url, token, method="PATCH", payload={"body": body})
        return CommentResult("updated", updated["id"], updated["html_url"])

    url = f"{api_url}/repos/{repo}/issues/{pr_number}/comments"
    created = _api_call(url, token, method="POST", payload={"body": body})
    return CommentResult("created", created["id"], created["html_url"])
