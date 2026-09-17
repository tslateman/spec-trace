#!/usr/bin/env python3
"""Move the Django-only rows that no `spectrace push` refills into D1.

Run it once, read the dry run, then apply:

    python scripts/cutover/backfill_django_to_d1.py --dry-run --d1 remote
    python scripts/cutover/backfill_django_to_d1.py --apply --d1 remote

Primary keys differ between the two stores, so every foreign key travels
through a natural key instead of its integer id. A reference that resolves to
nothing stops the run and names the row.

Re-running inserts nothing it already inserted: a row whose natural key is
already in D1 is reported as present and left alone.

Agent tasks stay out of D1 by design — the TaskLedger Durable Object is their
only writer. `--archive-agent-tasks PATH` writes them to JSON instead.
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_DIR = REPO_ROOT / "worker"
DEFAULT_DJANGO_DB = REPO_ROOT / "spectrace" / "db.sqlite3"

NATURAL_KEYS = {
    "requirements_requirement": ("external_id",),
    "requirements_agenttask": ("external_id",),
    "requirements_agent": ("agent_id",),
    "requirements_agentsprint": ("name",),
    "requirements_conflictlog": ("requirement_a_id", "requirement_b_id", "pattern"),
    "requirements_inappvalidation": ("name",),
    "requirements_inappvalidationrun": ("imported_at", "source"),
    "requirements_inappvalidationresult": ("validation_id", "validation_run_id", "checked_at"),
    "requirements_intentvalidationresult": ("task_id", "commit_sha"),
}

AGENT_TASK_TABLES = (
    "requirements_agenttask",
    "requirements_agenttask_requirements",
    "requirements_agenttask_depends_on",
    "requirements_agenttaskhistory",
    "requirements_agenttaskreview",
)


@dataclass(frozen=True)
class ForeignKey:
    column: str
    references: str


@dataclass(frozen=True)
class TableSpec:
    name: str
    foreign_keys: tuple[ForeignKey, ...] = ()
    copied_columns: tuple[tuple[str, str], ...] = ()
    skipped_columns: tuple[str, ...] = ()

    @property
    def natural_key(self):
        return NATURAL_KEYS[self.name]


BACKFILL = (
    TableSpec("requirements_agent"),
    TableSpec("requirements_agentsprint"),
    TableSpec(
        "requirements_conflictlog",
        foreign_keys=(
            ForeignKey("requirement_a_id", "requirements_requirement"),
            ForeignKey("requirement_b_id", "requirements_requirement"),
        ),
        copied_columns=(("last_seen_at", "created_at"),),
    ),
    TableSpec(
        "requirements_inappvalidation",
        foreign_keys=(ForeignKey("requirement_id", "requirements_requirement"),),
    ),
    TableSpec("requirements_inappvalidationrun"),
    TableSpec(
        "requirements_inappvalidationresult",
        foreign_keys=(
            ForeignKey("validation_id", "requirements_inappvalidation"),
            ForeignKey("validation_run_id", "requirements_inappvalidationrun"),
        ),
    ),
    TableSpec(
        "requirements_intentvalidationresult",
        foreign_keys=(ForeignKey("task_id", "requirements_agenttask"),),
    ),
)

PENDING = object()


class UnmappedForeignKey(Exception):
    pass


class BackfillVerificationFailed(Exception):
    pass


@dataclass
class TablePlan:
    spec: TableSpec
    to_insert: list = field(default_factory=list)
    already_present: int = 0

    @property
    def source_rows(self):
        return len(self.to_insert) + self.already_present


def django_rows(conn, table):
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(f"SELECT * FROM `{table}`")]


def d1_query(sql, target):
    command = ["npx", "wrangler", "d1", "execute", "spectrace", f"--{target}", "--json", "--command", sql]
    completed = subprocess.run(command, cwd=WORKER_DIR, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout[completed.stdout.index("[") :])[0]["results"]


def d1_execute_file(statements, target):
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as handle:
        handle.write(";\n".join(statements) + ";\n")
        path = handle.name
    command = ["npx", "wrangler", "d1", "execute", "spectrace", f"--{target}", "--yes", "--file", path]
    subprocess.run(command, cwd=WORKER_DIR, capture_output=True, text=True, check=True)


def d1_count(table, target):
    return d1_query(f"SELECT COUNT(*) AS n FROM `{table}`", target)[0]["n"]


def sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def key_of(row, columns):
    return tuple(row[column] for column in columns)


def d1_key_to_id(table, target):
    columns = NATURAL_KEYS[table]
    selected = ", ".join(f"`{column}`" for column in ("id", *columns))
    return {key_of(row, columns): row["id"] for row in d1_query(f"SELECT {selected} FROM `{table}`", target)}


def resolve_references(conn, spec, target, pending_keys):
    """Return {django_id: d1_id} for every table this spec points at."""
    resolved = {}
    for foreign_key in spec.foreign_keys:
        referenced = foreign_key.references
        if referenced in resolved:
            continue
        d1_ids = d1_key_to_id(referenced, target)
        mapping = {}
        for row in django_rows(conn, referenced):
            key = key_of(row, NATURAL_KEYS[referenced])
            if key in d1_ids:
                mapping[row["id"]] = d1_ids[key]
            elif key in pending_keys.get(referenced, set()):
                mapping[row["id"]] = PENDING
        resolved[referenced] = mapping
    return resolved


def plan_table(conn, spec, target, pending_keys):
    references = resolve_references(conn, spec, target, pending_keys)
    existing = set(d1_key_to_id(spec.name, target))
    plan = TablePlan(spec)
    for row in django_rows(conn, spec.name):
        mapped = {column: value for column, value in row.items() if column != "id"}
        for foreign_key in spec.foreign_keys:
            source_id = row[foreign_key.column]
            if source_id is None:
                continue
            if source_id not in references[foreign_key.references]:
                raise UnmappedForeignKey(
                    f"{spec.name} id={row['id']} column {foreign_key.column}={source_id} "
                    f"has no row in {foreign_key.references} on either side"
                )
            mapped[foreign_key.column] = references[foreign_key.references][source_id]
        for target_column, source_column in spec.copied_columns:
            mapped[target_column] = row[source_column]
        if key_of(mapped, spec.natural_key) in existing:
            plan.already_present += 1
        else:
            plan.to_insert.append(mapped)
    return plan


def insert_statements(plan):
    statements = []
    for row in plan.to_insert:
        unresolved = [column for column, value in row.items() if value is PENDING]
        if unresolved:
            raise UnmappedForeignKey(f"{plan.spec.name} row has unresolved references: {', '.join(unresolved)}")
        columns = ", ".join(f"`{column}`" for column in row)
        values = ", ".join(sql_literal(value) for value in row.values())
        statements.append(f"INSERT INTO `{plan.spec.name}` ({columns}) VALUES ({values})")
    return statements


def pending_natural_keys(conn):
    keys = {}
    for spec in BACKFILL:
        keys[spec.name] = {key_of(row, spec.natural_key) for row in django_rows(conn, spec.name)}
    return keys


def render_plan(plans, counts_before, target):
    width = max(len(plan.spec.name) for plan in plans)
    lines = [
        f"| {'table'.ljust(width)} | django | d1 before | insert | present |",
        f"| {'-' * width} | -----: | --------: | -----: | ------: |",
    ]
    for plan in plans:
        lines.append(
            f"| {plan.spec.name.ljust(width)} | {plan.source_rows:>6} | "
            f"{counts_before[plan.spec.name]:>9} | {len(plan.to_insert):>6} | {plan.already_present:>7} |"
        )
    total = sum(len(plan.to_insert) for plan in plans)
    lines.append("")
    lines.append(f"{total} rows to insert into D1 {target} across {len(plans)} tables.")
    return "\n".join(lines)


def archive_agent_tasks(conn, path):
    archive = {table: django_rows(conn, table) for table in AGENT_TASK_TABLES}
    path.write_text(json.dumps(archive, indent=2, sort_keys=True))
    return sum(len(rows) for rows in archive.values())


def verify(plans, counts_before, target):
    failures = []
    for plan in plans:
        expected = counts_before[plan.spec.name] + len(plan.to_insert)
        actual = d1_count(plan.spec.name, target)
        if actual != expected:
            failures.append(f"{plan.spec.name}: expected {expected}, found {actual}")
    if failures:
        raise BackfillVerificationFailed("; ".join(failures))
    return sum(d1_count(plan.spec.name, target) for plan in plans)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--d1", choices=["remote", "local"], default="remote")
    parser.add_argument("--django", type=Path, default=DEFAULT_DJANGO_DB)
    parser.add_argument("--archive-agent-tasks", type=Path, default=None)
    args = parser.parse_args(argv)

    conn = sqlite3.connect(f"file:{args.django}?mode=ro", uri=True)
    pending_keys = pending_natural_keys(conn)
    counts_before = {spec.name: d1_count(spec.name, args.d1) for spec in BACKFILL}

    if args.dry_run:
        plans = [plan_table(conn, spec, args.d1, pending_keys) for spec in BACKFILL]
        print(render_plan(plans, counts_before, args.d1))
        print("Dry run. Nothing written.")
    else:
        plans = []
        for spec in BACKFILL:
            plan = plan_table(conn, spec, args.d1, pending_keys)
            statements = insert_statements(plan)
            if statements:
                d1_execute_file(statements, args.d1)
            plans.append(plan)
        print(render_plan(plans, counts_before, args.d1))
        print(f"Applied. D1 now holds {verify(plans, counts_before, args.d1)} rows across these tables.")

    if args.archive_agent_tasks:
        rows = archive_agent_tasks(conn, args.archive_agent_tasks)
        print(f"Archived {rows} agent-task rows to {args.archive_agent_tasks}. D1 holds none of them by design.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
