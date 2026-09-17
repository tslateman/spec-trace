#!/usr/bin/env python3
"""Dump a Django SQLite database as D1-loadable INSERT statements.

Usage: python3 dump-data.py <source.sqlite3> <out.sql>

Emits one INSERT per row for every table the Worker migration creates,
ordered so each table's foreign-key targets load first. Tables absent from
the migration (django_*, auth_*, webhookevent) are skipped.
"""

import re
import sqlite3
import sys
from graphlib import TopologicalSorter
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def schema_tables() -> set[str]:
    sql = "\n".join(p.read_text() for p in sorted(MIGRATIONS_DIR.glob("*.sql")))
    return set(re.findall(r"CREATE TABLE `([^`]+)`", sql))


def load_order(source: sqlite3.Connection, tables: set[str]) -> list[str]:
    graph = {}
    for table in tables:
        parents = {row[2] for row in source.execute(f'PRAGMA foreign_key_list("{table}")')}
        graph[table] = (parents & tables) - {table}
    return list(TopologicalSorter(graph).static_order())


def literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    return "'" + value.replace("'", "''") + "'"


def dump_table(source: sqlite3.Connection, table: str, out) -> int:
    columns = [row[1] for row in source.execute(f'PRAGMA table_info("{table}")')]
    column_list = ", ".join(f'"{c}"' for c in columns)
    count = 0
    for row in source.execute(f'SELECT {column_list} FROM "{table}" ORDER BY id'):
        values = ", ".join(literal(v) for v in row)
        out.write(f'INSERT INTO "{table}" ({column_list}) VALUES ({values});\n')
        count += 1
    return count


def main(source_path: str, out_path: str) -> None:
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    source_tables = {
        row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    tables = schema_tables() & source_tables
    with open(out_path, "w") as out:
        out.write("PRAGMA defer_foreign_keys = true;\n")
        for table in load_order(source, tables):
            count = dump_table(source, table, out)
            print(f"{table} {count}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
