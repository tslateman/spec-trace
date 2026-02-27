"""Linear API client for fetching issues as requirements."""

import requests

from requirements.models import VerificationMethod
from requirements.services.requirement_parser import extract_structured_fields


class LinearClient:
    """Client for Linear GraphQL API.

    Fetches issues with a specific label and converts them to requirement dicts
    compatible with import_requirements_to_database().
    """

    API_URL = "https://api.linear.app/graphql"

    # Map Linear priority (1=urgent, 2=high, 3=medium, 4=low, 0=none) to requirement priority
    PRIORITY_MAP = {
        1: "urgent",
        2: "high",
        3: "medium",
        4: "low",
        0: "",  # No priority
    }

    # Map Linear state types to requirement status
    STATE_MAP = {
        "backlog": "draft",
        "unstarted": "draft",
        "started": "active",
        "completed": "active",
        "canceled": "deprecated",
    }

    # Map Linear labels to verification method
    # Labels like "verify:test", "verify:inapp", "verify:both"
    VERIFICATION_METHOD_MAP = {
        "verify:test": VerificationMethod.TEST,
        "verify:inapp": VerificationMethod.INAPP,
        "verify:both": VerificationMethod.BOTH,
    }

    def __init__(self, api_key: str):
        """Initialize client with API key.

        Args:
            api_key: Linear API key (starts with 'lin_api_')
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": api_key,
                "Content-Type": "application/json",
            }
        )

    def _execute_query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query against Linear API.

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            Response data dict

        Raises:
            requests.HTTPError: If API request fails
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self.session.post(self.API_URL, json=payload)
        response.raise_for_status()

        result = response.json()
        if "errors" in result:
            raise ValueError(f"GraphQL errors: {result['errors']}")

        return result.get("data", {})

    def fetch_issues_by_label(self, label: str) -> list[dict]:
        """Fetch all issues with the given label, return as requirement dicts.

        Args:
            label: Label name to filter issues (e.g., 'requirement')

        Returns:
            List of requirement dicts compatible with import_requirements_to_database()
        """
        query = """
        query IssuesByLabel($labelFilter: String!, $cursor: String) {
            issues(
                filter: { labels: { name: { eq: $labelFilter } } }
                first: 100
                after: $cursor
            ) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    identifier
                    title
                    description
                    priority
                    state {
                        name
                        type
                    }
                    labels {
                        nodes {
                            name
                        }
                    }
                    parent {
                        identifier
                    }
                    team {
                        key
                    }
                }
            }
        }
        """

        all_issues = []
        cursor = None

        # Handle pagination
        while True:
            variables = {"labelFilter": label, "cursor": cursor}
            data = self._execute_query(query, variables)

            issues_data = data.get("issues", {})
            nodes = issues_data.get("nodes", [])
            all_issues.extend(nodes)

            page_info = issues_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        # Convert to requirement dicts
        return [self._issue_to_requirement(issue, label) for issue in all_issues]

    def _issue_to_requirement(self, issue: dict, filter_label: str) -> dict:
        """Convert a Linear issue to a requirement dict.

        Args:
            issue: Linear issue data from GraphQL
            filter_label: Label used for filtering (excluded from tags)

        Returns:
            Requirement dict compatible with import_requirements_to_database()
        """
        # Extract labels, excluding the filter label and verify:* labels
        labels = issue.get("labels", {}).get("nodes", [])
        label_names = [lbl["name"] for lbl in labels]

        # Determine verification method from labels
        verification_method = VerificationMethod.UNSPECIFIED
        for label in label_names:
            if label in self.VERIFICATION_METHOD_MAP:
                verification_method = self.VERIFICATION_METHOD_MAP[label]
                break

        # Build tags excluding filter label and verify:* labels
        tags = [lbl for lbl in label_names if lbl != filter_label and not lbl.startswith("verify:")]

        # Map priority
        priority_num = issue.get("priority") or 0
        priority = self.PRIORITY_MAP.get(priority_num, "")

        # Map state to status
        state = issue.get("state", {})
        state_type = state.get("type", "backlog")
        status = self.STATE_MAP.get(state_type, "draft")

        # Build source URL
        team_key = issue.get("team", {}).get("key", "unknown")
        identifier = issue.get("identifier", "")
        source_file = f"linear://{team_key}/{identifier}"

        # Get parent reference
        parent = issue.get("parent")
        parent_id = parent.get("identifier") if parent else None

        # Extract structured fields from description (best-effort)
        description = issue.get("description") or ""
        structured = extract_structured_fields(description)

        return {
            "external_id": identifier,
            "title": issue.get("title", ""),
            "description": description,
            "tags": tags,
            "priority": priority,
            "status": status,
            "parent_id": parent_id,
            "source_file": source_file,
            "verification_method": verification_method,
            # Structured fields (FRET-inspired) extracted from description
            "scope": structured.get("scope", ""),
            "condition": structured.get("condition", ""),
            "component": structured.get("component", ""),
            "timing": structured.get("timing", ""),
            "response": structured.get("response", ""),
        }
