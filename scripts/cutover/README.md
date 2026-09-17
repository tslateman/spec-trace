# Cutover scripts

Two scripts for retiring the Django server. Neither belongs in CI, and neither
runs on a schedule.

| Script                     | Lifetime                                                        |
| -------------------------- | --------------------------------------------------------------- |
| `compare_django_d1.py`     | Keep. It is the evidence the cutover finished.                  |
| `backfill_django_to_d1.py` | One shot. Delete it once a human has run it against production. |

## compare_django_d1.py

Counts every table `db.sqlite3` and D1 share, and names the side that leads.

```bash
python scripts/cutover/compare_django_d1.py --d1 remote
```

Both reads. It writes to neither store.

## backfill_django_to_d1.py

Moves the Django-only rows that no `spectrace push` refills.

```bash
python scripts/cutover/backfill_django_to_d1.py --dry-run --d1 remote
python scripts/cutover/backfill_django_to_d1.py --apply   --d1 remote
```

Read the dry run first. It prints the row count it would insert per table and
writes nothing.

Primary keys differ between the two stores — `REQ-BILL-002` is id 7 in Django
and id 11 in D1 — so the script resolves every foreign key through a natural
key. A reference that resolves to nothing stops the run and names the row.
Copying ids verbatim would attach history to the wrong requirement.

Re-running is safe: a row whose natural key is already in D1 counts as present
and is left alone. `--apply` verifies the counts afterward and raises when a
table lands off its expected total.

### Agent tasks stay out

The TaskLedger Durable Object is the only writer of `requirements_agenttask`
and the tables around it. `--archive-agent-tasks PATH` writes those rows to
JSON, which keeps the pre-Worker record without giving the ledger's tables a
second writer.

### As measured on 2026-09-16

Against production D1, the dry run plans zero inserts. `db.sqlite3` was rebuilt
from migrations that morning and holds no row D1 lacks. Run the dry run again
before deleting this script; it is written for a `db.sqlite3` that still
carries pre-Worker history.
