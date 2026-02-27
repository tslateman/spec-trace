"""Tests for Linear API client."""

from unittest.mock import MagicMock, patch

import pytest

from requirements.linear import LinearClient
from requirements.models import VerificationMethod


@pytest.fixture
def linear_client():
    """Create a LinearClient with a mock API key."""
    return LinearClient("lin_api_test_key")


@pytest.fixture
def mock_graphql_response():
    """Create a mock GraphQL response with issues."""
    return {
        "data": {
            "issues": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "identifier": "PROJ-123",
                        "title": "Implement login feature",
                        "description": "Users should be able to log in",
                        "priority": 2,
                        "state": {"name": "In Progress", "type": "started"},
                        "labels": {
                            "nodes": [
                                {"name": "requirement"},
                                {"name": "auth"},
                                {"name": "verify:test"},
                            ]
                        },
                        "parent": None,
                        "team": {"key": "PROJ"},
                    }
                ],
            }
        }
    }


class TestLinearClient:
    """Tests for LinearClient class."""

    def test_init_sets_headers(self, linear_client):
        """Client initializes with correct headers."""
        assert linear_client.session.headers["Authorization"] == "lin_api_test_key"
        assert linear_client.session.headers["Content-Type"] == "application/json"

    @patch("requests.Session.post")
    def test_execute_query_success(self, mock_post, linear_client):
        """Execute query returns data on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"issues": []}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = linear_client._execute_query("query { issues { nodes { id } } }")

        assert result == {"issues": []}
        mock_post.assert_called_once()

    @patch("requests.Session.post")
    def test_execute_query_raises_on_graphql_errors(self, mock_post, linear_client):
        """Execute query raises ValueError on GraphQL errors."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"errors": [{"message": "Invalid query"}]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(ValueError) as exc_info:
            linear_client._execute_query("invalid query")

        assert "GraphQL errors" in str(exc_info.value)

    @patch("requests.Session.post")
    def test_fetch_issues_by_label(self, mock_post, linear_client, mock_graphql_response):
        """Fetch issues returns requirement dicts."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_graphql_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        requirements = linear_client.fetch_issues_by_label("requirement")

        assert len(requirements) == 1
        req = requirements[0]
        assert req["external_id"] == "PROJ-123"
        assert req["title"] == "Implement login feature"
        assert req["priority"] == "high"
        assert req["status"] == "active"
        assert req["source_file"] == "linear://PROJ/PROJ-123"

    @patch("requests.Session.post")
    def test_fetch_issues_extracts_verification_method(
        self, mock_post, linear_client, mock_graphql_response
    ):
        """Fetch issues extracts verification method from labels."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_graphql_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        requirements = linear_client.fetch_issues_by_label("requirement")

        req = requirements[0]
        assert req["verification_method"] == VerificationMethod.TEST

    @patch("requests.Session.post")
    def test_fetch_issues_excludes_filter_label_from_tags(
        self, mock_post, linear_client, mock_graphql_response
    ):
        """Fetch issues excludes filter label and verify:* labels from tags."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_graphql_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        requirements = linear_client.fetch_issues_by_label("requirement")

        req = requirements[0]
        assert "requirement" not in req["tags"]
        assert "verify:test" not in req["tags"]
        assert "auth" in req["tags"]

    @patch("requests.Session.post")
    def test_fetch_issues_handles_pagination(self, mock_post, linear_client):
        """Fetch issues handles pagination correctly."""
        # First page has more
        page1_response = {
            "data": {
                "issues": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor123"},
                    "nodes": [
                        {
                            "identifier": "PROJ-1",
                            "title": "Issue 1",
                            "description": "",
                            "priority": 0,
                            "state": {"name": "Backlog", "type": "backlog"},
                            "labels": {"nodes": [{"name": "requirement"}]},
                            "parent": None,
                            "team": {"key": "PROJ"},
                        }
                    ],
                }
            }
        }
        # Second page is last
        page2_response = {
            "data": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "identifier": "PROJ-2",
                            "title": "Issue 2",
                            "description": "",
                            "priority": 0,
                            "state": {"name": "Done", "type": "completed"},
                            "labels": {"nodes": [{"name": "requirement"}]},
                            "parent": None,
                            "team": {"key": "PROJ"},
                        }
                    ],
                }
            }
        }

        mock_response1 = MagicMock()
        mock_response1.json.return_value = page1_response
        mock_response1.raise_for_status = MagicMock()

        mock_response2 = MagicMock()
        mock_response2.json.return_value = page2_response
        mock_response2.raise_for_status = MagicMock()

        mock_post.side_effect = [mock_response1, mock_response2]

        requirements = linear_client.fetch_issues_by_label("requirement")

        assert len(requirements) == 2
        assert requirements[0]["external_id"] == "PROJ-1"
        assert requirements[1]["external_id"] == "PROJ-2"
        assert mock_post.call_count == 2

    def test_issue_to_requirement_with_parent(self, linear_client):
        """Issue with parent sets parent_id correctly."""
        issue = {
            "identifier": "PROJ-456",
            "title": "Child issue",
            "description": "A child",
            "priority": 3,
            "state": {"name": "Todo", "type": "unstarted"},
            "labels": {"nodes": [{"name": "requirement"}]},
            "parent": {"identifier": "PROJ-123"},
            "team": {"key": "PROJ"},
        }

        req = linear_client._issue_to_requirement(issue, "requirement")

        assert req["parent_id"] == "PROJ-123"

    def test_priority_mapping(self, linear_client):
        """Priority values map correctly."""
        assert linear_client.PRIORITY_MAP[1] == "urgent"
        assert linear_client.PRIORITY_MAP[2] == "high"
        assert linear_client.PRIORITY_MAP[3] == "medium"
        assert linear_client.PRIORITY_MAP[4] == "low"
        assert linear_client.PRIORITY_MAP[0] == ""

    def test_state_mapping(self, linear_client):
        """State types map to status correctly."""
        assert linear_client.STATE_MAP["backlog"] == "draft"
        assert linear_client.STATE_MAP["unstarted"] == "draft"
        assert linear_client.STATE_MAP["started"] == "active"
        assert linear_client.STATE_MAP["completed"] == "active"
        assert linear_client.STATE_MAP["canceled"] == "deprecated"

    def test_verification_method_mapping(self, linear_client):
        """Verification method labels map correctly."""
        assert linear_client.VERIFICATION_METHOD_MAP["verify:test"] == VerificationMethod.TEST
        assert linear_client.VERIFICATION_METHOD_MAP["verify:inapp"] == VerificationMethod.INAPP
        assert linear_client.VERIFICATION_METHOD_MAP["verify:both"] == VerificationMethod.BOTH
