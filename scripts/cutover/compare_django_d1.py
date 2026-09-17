#!/usr/bin/env python3
"""Compare row counts between the Django SQLite database and D1.

Prints one row per table shared by both stores, with each side's count and
which side leads. Run it before and after `backfill_django_to_d1.py` so the
diff between the two runs is readable.

    python scripts/cutover/compare_django_d1.py --d1 remote
    python scripts/cutover/compare_django_d1.py --d1 local

`--django PATH` points at a database other than `spectrace/db.sqlite3`.
Every query is a read; this script never writes to either store.
"""

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_DIR = REPO_ROOT / "worker"
DEFAULT_DJANGO_DB = REPO_ROOT / "spectrace" / "db.sqlite3"
TABLE_PREFIX = "requirements_"


def django_tables(db_path):
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?",
            (f"{TABLE_PREFIX}%",),
        ).fetchall()
    return sorted(name for (name,) in rows)


def django_counts(db_path, tables):
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        return {table: conn.execute(f"SELECT COUNT(*) FROM `{table}`").fetchone()[0] for table in tables}


def d1_query(sql, target):
    command = ["npx", "wrangler", "d1", "execute", "spectrace", f"--{target}", "--json", "--command", sql]
    completed = subprocess.run(command, cwd=WORKER_DIR, capture_output=True, text=True, check=True)
    payload = completed.stdout[completed.stdout.index("[") :]
    return json.loads(payload)[0]["results"]


def d1_tables(target):
    rows = d1_query(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '{TABLE_PREFIX}%' ORDER BY name",
        target,
    )
    return sorted(row["name"] for row in rows)


D1_COMPOUND_SELECT_LIMIT = 5


def d1_counts(target, tables):
    counts = {}
    for start in range(0, len(tables), D1_COMPOUND_SELECT_LIMIT):
        batch = tables[start : start + D1_COMPOUND_SELECT_LIMIT]
        union = " UNION ALL ".join(f"SELECT '{table}' AS t, COUNT(*) AS n FROM `{table}`" for table in batch)
        counts.update({row["t"]: row["n"] for row in d1_query(union, target)})
    return counts


def leader(django_count, d1_count):
    if django_count == d1_count:
        return "match"
    return "django" if django_count > d1_count else "d1"


def render(rows, django_only, d1_only, target):
    width = max(len(row[0]) for row in rows)
    lines = [
        f"| {'table'.ljust(width)} | django | d1 | leader |",
        f"| {'-' * width} | -----: | -: | ------ |",
    ]
    for table, django_count, d1_count in rows:
        lines.append(f"| {table.ljust(width)} | {django_count:>6} | {d1_count:>2} | {leader(django_count, d1_count)} |")
    matched = sum(1 for _, dj, d1 in rows if dj == d1)
    lines.append("")
    lines.append(f"{len(rows)} shared tables against D1 {target}: {matched} match, {len(rows) - matched} differ.")
    lines.append(f"django rows {sum(row[1] for row in rows)}, d1 rows {sum(row[2] for row in rows)}.")
    if django_only:
        lines.append(f"django-only tables: {', '.join(django_only)}")
    if d1_only:
        lines.append(f"d1-only tables: {', '.join(d1_only)}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d1", choices=["remote", "local"], default="remote")
    parser.add_argument("--django", type=Path, default=DEFAULT_DJANGO_DB)
    args = parser.parse_args()

    dj_tables = django_tables(args.django)
    worker_tables = d1_tables(args.d1)
    shared = sorted(set(dj_tables) & set(worker_tables))

    dj = django_counts(args.django, shared)
    d1 = d1_counts(args.d1, shared)
    rows = [(table, dj[table], d1[table]) for table in shared]

    print(render(rows, sorted(set(dj_tables) - set(worker_tables)), sorted(set(worker_tables) - set(dj_tables)), args.d1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
