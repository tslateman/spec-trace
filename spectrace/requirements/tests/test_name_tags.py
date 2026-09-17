"""Tests for requirement tags carried in test names."""

import pytest

from requirements.services.name_tags import junit_links, requirement_ids_in_name

VITEST_JUNIT = (
    '<testsuites name="vitest tests"><testsuite name="worker/test/ledger.test.ts">'
    '<testcase classname="worker/test/ledger.test.ts" '
    'name="TaskLedger claims &gt; [REQ-TASK-002] claim grants exactly one claim" time="0.02"/>'
    '<testcase classname="worker/test/ledger.test.ts" '
    'name="TaskLedger lease alarm &gt; alarm releases lapsed leases" time="0.01"/>'
    "</testsuite></testsuites>"
)

GOTESTSUM_JUNIT = (
    '<testsuites tests="3"><testsuite name="example.com/upload-gateway" tests="3">'
    '<testcase classname="example.com/upload-gateway" '
    'name="TestAccepts/[GW-UPL-001]_admits_the_media_types_the_pipeline_processes" '
    'time="0.000000"/>'
    '<testcase classname="example.com/upload-gateway" '
    'name="TestRateLimiter/[GW-RTL-001]_keeps_one_tenant&#39;s_budget_off_another&#39;s" '
    'time="0.000000"/>'
    '<testcase classname="example.com/upload-gateway" name="TestAccepts" time="0.000000"/>'
    "</testsuite></testsuites>"
)

NEXTEST_JUNIT = (
    '<testsuites name="nextest-run" tests="2">'
    '<testsuite name="storage-vault::vault" tests="2">'
    '<testcase name="[VLT-ENC-001] seals a document before it lands" '
    'classname="storage-vault::vault" time="0.008"/>'
    '<testcase name="sweeps only the expired documents" '
    'classname="storage-vault::vault" time="0.008"/>'
    "</testsuite></testsuites>"
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("[REQ-AUTH-001] logs in", ["REQ-AUTH-001"]),
        ("POST /tasks/{id}/claim [REQ-TASK-002] > claim moves a task", ["REQ-TASK-002"]),
        ("[REQ-RSLT-003][REQ-RSLT-004] detail and resolve", ["REQ-RSLT-003", "REQ-RSLT-004"]),
        ("TestLogin/[req_auth_001]_logs_in", ["REQ-AUTH-001"]),
        ("[DOC-ING-002] ingests [DOC-ING-002] twice", ["DOC-ING-002"]),
        ("[MYPROJ-001] single segment prefix", ["MYPROJ-001"]),
    ],
)
def test_requirement_ids_in_name__reads_tags(name, expected):
    assert requirement_ids_in_name(name) == expected


@pytest.mark.parametrize(
    "name",
    ["[slow] no id shape", "[REQ-AUTH] no number", "REQ-AUTH-001 without brackets", "plain"],
)
def test_requirement_ids_in_name__ignores_text_that_is_not_a_requirement_id(name):
    assert requirement_ids_in_name(name) == []


def test_junit_links__pairs_each_tagged_case_with_its_requirement(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(VITEST_JUNIT)

    assert junit_links(junit) == [
        {
            "test_nodeid": (
                "worker/test/ledger.test.ts::TaskLedger claims > "
                "[REQ-TASK-002] claim grants exactly one claim"
            ),
            "requirement_id": "REQ-TASK-002",
        }
    ]


def test_junit_links__reads_a_gotestsum_report(tmp_path):
    """gotestsum keeps the tag through Go's underscores and its dotted module path."""
    junit = tmp_path / "junit.xml"
    junit.write_text(GOTESTSUM_JUNIT)

    assert junit_links(junit) == [
        {
            "test_nodeid": (
                "example.com/upload-gateway::TestAccepts/"
                "[GW-UPL-001]_admits_the_media_types_the_pipeline_processes"
            ),
            "requirement_id": "GW-UPL-001",
        },
        {
            "test_nodeid": (
                "example.com/upload-gateway::TestRateLimiter/"
                "[GW-RTL-001]_keeps_one_tenant's_budget_off_another's"
            ),
            "requirement_id": "GW-RTL-001",
        },
    ]


def test_junit_links__reads_a_cargo_nextest_report(tmp_path):
    """nextest's `crate::binary` classname survives the pytest nodeid normalizer."""
    junit = tmp_path / "junit.xml"
    junit.write_text(NEXTEST_JUNIT)

    assert junit_links(junit) == [
        {
            "test_nodeid": "storage-vault::vault::[VLT-ENC-001] seals a document before it lands",
            "requirement_id": "VLT-ENC-001",
        }
    ]
