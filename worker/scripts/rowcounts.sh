#!/usr/bin/env bash
# Usage: scripts/rowcounts.sh <source.sqlite3>
# Compares per-table row counts between the source database and the local D1
# database under .wrangler/state. Exits 1 on any mismatch.
set -euo pipefail

source_db="$1"
worker_dir="$(cd "$(dirname "$0")/.." && pwd)"
d1_files=("$worker_dir"/.wrangler/state/v3/d1/miniflare-D1DatabaseObject/[0-9a-f]*.sqlite)
[[ ${#d1_files[@]} -eq 1 ]] || { echo "expected one local D1 file, found ${#d1_files[@]}" >&2; exit 1; }
d1_db="${d1_files[0]}"

schema_tables=$(cat "$worker_dir"/migrations/*.sql | grep -o 'CREATE TABLE `[^`]*`' | sed 's/CREATE TABLE `\(.*\)`/\1/' | sort)
source_tables=$(sqlite3 "$source_db" "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
tables=$(comm -12 <(echo "$schema_tables") <(echo "$source_tables"))

status=0
printf '%-48s %8s %8s  %s\n' table source d1 match
for table in $tables; do
  source_count=$(sqlite3 "$source_db" "SELECT count(*) FROM \"$table\"")
  d1_count=$(sqlite3 "$d1_db" "SELECT count(*) FROM \"$table\"")
  if [[ "$source_count" == "$d1_count" ]]; then
    match=ok
  else
    match=MISMATCH
    status=1
  fi
  printf '%-48s %8s %8s  %s\n' "$table" "$source_count" "$d1_count" "$match"
done
exit $status
