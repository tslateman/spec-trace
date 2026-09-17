"""API payloads that seed the same demo data the admin load-demo views wrote through the ORM."""

from dataclasses import asdict
from datetime import datetime, timedelta
from itertools import cycle

from requirements.flows.definitions import REGISTERED_FLOWS
from requirements.matrix import MATRIX_DEMO_TESTS
from requirements.services.results_payload import VALIDATION_STATUS
from requirements.services.vendor_demo import DEMO_SOURCE_PREFIX, VENDOR_CONFIGS

MATRIX_DEMO_SOURCE = "demo://matrix-demo"
IMPACT_DEMO_BRANCH = "demo/impact-analysis"


def vendor_demo_runs(requirement_ids: list[str], now: datetime) -> list[dict]:
    """Two enforcement payloads: a run from two days ago and one from now.

    Every vendor validation appears in both; Plaid's first validation passes in the
    older run and fails in the newer one, the regression the dashboard highlights.
    """
    older_at = now - timedelta(days=2)
    older: list[dict] = []
    newer: list[dict] = []
    requirements = cycle(requirement_ids[:12])
    for vendor in VENDOR_CONFIGS:
        name = vendor["name"]
        for index in range(vendor["validation_count"]):
            should_pass = index < vendor["pass_count"]
            regression = vendor.get("has_regression", False) and index == 0
            validation = {
                "requirement_id": next(requirements),
                "name": f"{name} - Validation {index + 1}",
                "endpoint": f"{DEMO_SOURCE_PREFIX}/{name.lower()}/v{index + 1}",
                "context": {"vendor": name, "feature_flags": vendor["feature_flags"]},
            }
            older.append(
                {
                    **validation,
                    **_outcome(True if regression else should_pass),
                    "checked_at": (older_at + timedelta(minutes=index)).isoformat(),
                }
            )
            newer.append(
                {
                    **validation,
                    **(_regressed() if regression else _outcome(should_pass)),
                    "checked_at": (now + timedelta(minutes=index)).isoformat(),
                }
            )
    return [
        {"source": f"{DEMO_SOURCE_PREFIX}/run-1", "validations": older},
        {"source": f"{DEMO_SOURCE_PREFIX}/run-2", "validations": newer},
    ]


def _outcome(passed: bool) -> dict:
    return {
        "status": "success" if passed else "failure",
        "message": "Validation passed" if passed else "Assertion failed",
        "steps": [{"name": "Connect", "passed": True}, {"name": "Verify", "passed": passed}],
    }


def _regressed() -> dict:
    return {
        "status": "failure",
        "message": "Connection timeout - regression detected",
        "steps": [
            {"name": "Connect", "passed": False, "error_message": "Timeout after 30s"},
            {"name": "Verify", "passed": False, "details": "skipped"},
        ],
    }


def matrix_demo_run(requirement_ids: list[str]) -> dict:
    """One enforcement payload spreading the matrix demo's twelve tests over the requirements.

    Every third test also covers the next requirement, so some cells show two tests.
    """
    requirements = requirement_ids[:12]
    count = len(requirements)
    validations = []
    for index, (nodeid, _name, status) in enumerate(MATRIX_DEMO_TESTS):
        position = index % count
        targets = [requirements[position]]
        if index % 3 == 0 and position + 1 < count:
            targets.append(requirements[position + 1])
        validations.extend(
            {"requirement_id": requirement_id, "name": nodeid, "status": VALIDATION_STATUS[status]}
            for requirement_id in targets
        )
    return {"source": MATRIX_DEMO_SOURCE, "validations": validations}


def impact_demo_links(requirement_ids: list[str]) -> list[dict]:
    """Test links for the first eight requirements, named the way setup_impact_demo names them."""
    return [
        {
            "test_nodeid": f"tests/test_{requirement_id.lower().replace('-', '_')}.py"
            f"::test_verify_{index}",
            "requirement_id": requirement_id,
        }
        for index, requirement_id in enumerate(requirement_ids[:8])
    ]


def flow_demo_flows() -> list[dict]:
    """The code-defined flows the flow status dashboard demo syncs."""
    return [asdict(flow) for flow in REGISTERED_FLOWS]
