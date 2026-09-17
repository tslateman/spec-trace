"""Cover the one-shot Django-to-D1 backfill in scripts/cutover/."""

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "cutover"
_MODULE_PATH = _SCRIPTS / "backfill_django_to_d1.py"
_SPEC = importlib.util.spec_from_file_location("backfill_django_to_d1", _MODULE_PATH)
backfill = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(backfill)

DJANGO_SCHEMA = """
CREATE TABLE requirements_requirement (id INTEGER PRIMARY KEY, external_id TEXT);
CREATE TABLE requirements_agenttask (id INTEGER PRIMARY KEY, external_id TEXT);
CREATE TABLE requirements_conflictlog (
    id INTEGER PRIMARY KEY, pattern TEXT, details TEXT, created_at TEXT,
    requirement_a_id INTEGER, requirement_b_id INTEGER
);
CREATE TABLE requirements_intentvalidationresult (
    id INTEGER PRIMARY KEY, commit_sha TEXT, created_at TEXT, task_id INTEGER
);
CREATE TABLE requirements_agenttask_requirements (
    id INTEGER PRIMARY KEY, agenttask_id INTEGER, requirement_id INTEGER
);
CREATE TABLE requirements_agenttask_depends_on (
    id INTEGER PRIMARY KEY, from_agenttask_id INTEGER, to_agenttask_id INTEGER
);
CREATE TABLE requirements_agenttaskhistory (
    id INTEGER PRIMARY KEY, action TEXT, task_id INTEGER
);
CREATE TABLE requirements_agenttaskreview (
    id INTEGER PRIMARY KEY, decision TEXT, task_id INTEGER
);
CREATE TABLE requirements_agent (id INTEGER PRIMARY KEY, agent_id TEXT);
CREATE TABLE requirements_agentsprint (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE requirements_inappvalidation (
    id INTEGER PRIMARY KEY, name TEXT, requirement_id INTEGER
);
CREATE TABLE requirements_inappvalidationrun (
    id INTEGER PRIMARY KEY, imported_at TEXT, source TEXT
);
CREATE TABLE requirements_inappvalidationresult (
    id INTEGER PRIMARY KEY, checked_at TEXT, validation_id INTEGER, validation_run_id INTEGER
);
"""

D1_SCHEMA = (
    DJANGO_SCHEMA
    + """
ALTER TABLE requirements_conflictlog ADD COLUMN last_seen_at TEXT;
"""
)

REQUIREMENT_IDS_DIFFER = {"REQ-BILL-002": (7, 107), "REQ-PLAT-002": (8, 108)}


@pytest.fixture
def django_db_path(tmp_path):
    path = tmp_path / "db.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(DJANGO_SCHEMA)
    for external_id, (django_id, _) in REQUIREMENT_IDS_DIFFER.items():
        conn.execute(
            "INSERT INTO requirements_requirement (id, external_id) VALUES (?, ?)",
            (django_id, external_id),
        )
    conn.execute("INSERT INTO requirements_agenttask (id, external_id) VALUES (1, 'TASK-LEGACY-1')")
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def d1(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.executescript(D1_SCHEMA)
    for external_id, (_, d1_id) in REQUIREMENT_IDS_DIFFER.items():
        connection.execute(
            "INSERT INTO requirements_requirement (id, external_id) VALUES (?, ?)",
            (d1_id, external_id),
        )
    connection.execute(
        "INSERT INTO requirements_agenttask (id, external_id) VALUES (900, 'TASK-LEGACY-1')"
    )
    connection.commit()

    def fake_d1_query(sql, target):
        cursor = connection.execute(sql)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    monkeypatch.setattr(backfill, "d1_query", fake_d1_query)
    return connection


def plan_for(table, django_db_path):
    spec = next(candidate for candidate in backfill.BACKFILL if candidate.name == table)
    conn = sqlite3.connect(f"file:{django_db_path}?mode=ro", uri=True)
    return backfill.plan_table(conn, spec, "local", backfill.pending_natural_keys(conn))


def test_plan_table__remaps_requirement_ids_through_external_id(django_db_path, d1):
    conn = sqlite3.connect(django_db_path)
    conn.execute(
        "INSERT INTO requirements_conflictlog"
        " (pattern, details, created_at, requirement_a_id, requirement_b_id)"
        " VALUES ('threshold', '{}', '2026-08-02', 7, 8)"
    )
    conn.commit()
    conn.close()

    plan = plan_for("requirements_conflictlog", django_db_path)

    assert len(plan.to_insert) == 1
    assert plan.to_insert[0]["requirement_a_id"] == 107
    assert plan.to_insert[0]["requirement_b_id"] == 108


def test_plan_table__remaps_task_ids_through_external_id(django_db_path, d1):
    conn = sqlite3.connect(django_db_path)
    conn.execute(
        "INSERT INTO requirements_intentvalidationresult (commit_sha, created_at, task_id)"
        " VALUES ('abc123', '2026-08-04', 1)"
    )
    conn.commit()
    conn.close()

    plan = plan_for("requirements_intentvalidationresult", django_db_path)

    assert plan.to_insert[0]["task_id"] == 900


def test_plan_table__copies_last_seen_at_from_created_at(django_db_path, d1):
    conn = sqlite3.connect(django_db_path)
    conn.execute(
        "INSERT INTO requirements_conflictlog"
        " (pattern, details, created_at, requirement_a_id, requirement_b_id)"
        " VALUES ('threshold', '{}', '2026-08-02', 7, 8)"
    )
    conn.commit()
    conn.close()

    plan = plan_for("requirements_conflictlog", django_db_path)

    assert plan.to_insert[0]["last_seen_at"] == "2026-08-02"


def test_plan_table__reports_rows_already_in_d1_as_present(django_db_path, d1):
    conn = sqlite3.connect(django_db_path)
    conn.execute("INSERT INTO requirements_agent (agent_id) VALUES ('legacy-coder-1')")
    conn.commit()
    conn.close()
    d1.execute("INSERT INTO requirements_agent (agent_id) VALUES ('legacy-coder-1')")
    d1.commit()

    plan = plan_for("requirements_agent", django_db_path)

    assert plan.to_insert == []
    assert plan.already_present == 1


def test_plan_table__raises_when_the_referenced_row_is_missing_from_both_stores(django_db_path, d1):
    conn = sqlite3.connect(django_db_path)
    conn.execute(
        "INSERT INTO requirements_intentvalidationresult (commit_sha, created_at, task_id)"
        " VALUES ('abc123', '2026-08-04', 404)"
    )
    conn.commit()
    conn.close()

    with pytest.raises(backfill.UnmappedForeignKey, match="requirements_agenttask"):
        plan_for("requirements_intentvalidationresult", django_db_path)


def test_insert_statements__raises_when_a_reference_is_still_pending(django_db_path, d1):
    spec = next(
        candidate for candidate in backfill.BACKFILL if candidate.name == "requirements_conflictlog"
    )
    plan = backfill.TablePlan(
        spec, to_insert=[{"pattern": "threshold", "requirement_a_id": backfill.PENDING}]
    )

    with pytest.raises(backfill.UnmappedForeignKey, match="unresolved references"):
        backfill.insert_statements(plan)


def test_archive_agent_tasks__writes_every_ledger_owned_table(django_db_path, tmp_path):
    conn = sqlite3.connect(django_db_path)
    conn.execute("INSERT INTO requirements_agenttaskhistory (action, task_id) VALUES ('claim', 1)")
    conn.commit()
    archive_path = tmp_path / "agent-tasks.json"

    rows = backfill.archive_agent_tasks(conn, archive_path)

    archive = json.loads(archive_path.read_text())
    assert rows == 2
    assert archive["requirements_agenttask"][0]["external_id"] == "TASK-LEGACY-1"
    assert archive["requirements_agenttaskhistory"][0]["action"] == "claim"
    assert set(archive) == set(backfill.AGENT_TASK_TABLES)


def test_backfill_tables__exclude_every_ledger_owned_table():
    backfilled = {spec.name for spec in backfill.BACKFILL}

    assert backfilled.isdisjoint(backfill.AGENT_TASK_TABLES)
