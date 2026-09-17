#!/usr/bin/env python3
"""Diff the v1 read API between Django and the Worker for every stored requirement.

Usage:
    parity-diff.py [--django URL] [--worker URL] [--api-key KEY] [--db PATH]

Fetches each requirement's context and status from both servers, plus the
project-wide reads, canonicalises the JSON, and prints a unified diff for every
mismatch. Exits 1 on any difference.
"""

import argparse
import difflib
import json
import sqlite3
import sys
import urllib.error
import urllib.request

DEFAULT_DB = "/Users/tslater/dev/spec-trace/spectrace/db.sqlite3"

PROJECT_WIDE_PATHS = [
    "/api/v1/specs/coverage/",
    "/api/v1/results/conflicts/",
    "/api/v1/results/test-runs/latest/",
    "/api/v1/results/enforcement-runs/latest/",
]


def requirement_ids(db_path: str) -> list[str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT external_id FROM requirements_requirement ORDER BY external_id"
        ).fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]


def per_requirement_paths(external_id: str) -> list[str]:
    return [
        f"/api/v1/specs/{external_id}/context",
        f"/api/v1/specs/{external_id}/status/",
    ]


def fetch(base_url: str, path: str, api_key: str) -> tuple[int, str]:
    request = urllib.request.Request(base_url + path, headers={"X-API-Key": api_key})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def normalise_numbers(value):
    if isinstance(value, dict):
        return {key: normalise_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalise_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def canonical(status: int, body: str) -> str:
    try:
        rendered = json.dumps(normalise_numbers(json.loads(body)), sort_keys=True, indent=2)
    except json.JSONDecodeError:
        rendered = body
    return f"HTTP {status}\n{rendered}\n"


def compare(path: str, django: tuple[int, str], worker: tuple[int, str]) -> list[str]:
    expected = canonical(*django)
    actual = canonical(*worker)
    if expected == actual:
        return []
    return list(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"django {path}",
            tofile=f"worker {path}",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--django", default="http://localhost:8000")
    parser.add_argument("--worker", default="http://localhost:8787")
    parser.add_argument("--api-key", default="dev-key")
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    paths = [
        path
        for external_id in requirement_ids(args.db)
        for path in per_requirement_paths(external_id)
    ] + PROJECT_WIDE_PATHS

    differences = 0
    for path in paths:
        diff = compare(
            path, fetch(args.django, path, args.api_key), fetch(args.worker, path, args.api_key)
        )
        if diff:
            differences += 1
            sys.stdout.writelines(diff)
            print()

    print(f"{len(paths)} endpoints compared, {differences} differences")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
