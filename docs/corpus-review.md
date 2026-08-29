# Corpus-backed spec review

Given a spec file, SpecTrace names every org standard, decision, and commitment
it touches — at a pinned corpus version — and records the check as an auditable
artifact. Coverage stops depending on what the reviewer remembered.

Nothing here judges whether a spec honors an obligation. A rule engine cannot do
that. It can assert coverage: which obligations bound, which the spec
acknowledged, and which structural fields it left empty. Reviewers still read.
The record proves what was put in front of them.

## The two halves of a review

**Coverage** is the load-bearing half. Every applicable entry version gets a row,
finding or not. A row is the claim that this obligation was put in front of a
reviewer, at that version, on that date. A review that recorded only problems
would prove nothing about what was covered.

**Findings** are the five deterministic rule outcomes:

| Finding                   | Fires when                                                        |
| ------------------------- | ----------------------------------------------------------------- |
| `unaddressed_obligation`  | An entry applies and the spec cites no version of it              |
| `stale_citation`          | The spec cites version N while version M > N applies              |
| `orphan_citation`         | The spec cites an entry that does not apply                       |
| `unmet_check`             | An applicable, cited entry has a check the requirement fails      |
| `conflicting_obligations` | Two applicable entries assert contradictory predicates on a field |

## Commands

| Command                                         | Does                                               | Exit                    |
| ----------------------------------------------- | -------------------------------------------------- | ----------------------- |
| `spectrace corpus review <spec-or-requirement>` | Reviews and records coverage plus findings         | 1 on a blocking finding |
| `spectrace corpus coverage`                     | The audit ledger: each requirement's latest review | always 0                |
| `spectrace corpus drift`                        | Reviews the corpus has moved out from under        | 0, or 1 with `--strict` |
| `spectrace corpus suggest`                      | Proposes `applies_to` widenings for a human        | always 0                |
| `python spectrace/manage.py parse_corpus <dir>` | Imports `corpus/**/*.md` into immutable versions   | 1 on a parse error      |

Common options:

- `--format text|json|md` on all four `corpus` subcommands. `text` for a
  terminal, `json` for a machine, `md` for a PR comment.
- `--reviewer <name>` on `review`, recorded on the review row.
- `--strict` on `review`, which treats advisory findings as blocking for that
  one run. On `drift`, it exits 1 when stale reviews exist.
- `--requirement <id>` on `coverage` and `suggest`.
- `--min-score <float>` on `suggest`, the cosine floor for text similarity.

Writing a corpus entry is covered in
[Writing a corpus entry](corpus-authoring.md).

## One spec, end to end

`specs/platform/tenant_isolation.md` declares `REQ-PLAT-001` and cites two
entries in its frontmatter:

```yaml
---
id: REQ-PLAT-001
title: Tenant Data Isolation
status: active
priority: high
tags: [platform, security, compliance]
complies_with:
  - STD-SEC-001@3
  - STD-SEC-002@1
---
```

`complies_with` is the citation mechanism. Every citation names a version:
`ENTRY-ID@VERSION`. A bare `STD-SEC-002` is rejected before anything runs.

### Review it

```bash
spectrace corpus review specs/platform/tenant_isolation.md --reviewer alice
```

```
Review of REQ-PLAT-001 (specs/platform/tenant_isolation.md)
Snapshot: 74ac5e6694ba

Coverage (3 entry versions surfaced):
  COM-PLAT-001@2 [not cited] [advisory] Workspace durability and recovery window
    matched by paths=specs/platform/tenant_isolation.md
  STD-SEC-001@4 [cited] [blocking] Tenant data isolation
    matched by tags=platform, tags=security, paths=specs/platform/tenant_isolation.md, requirement_ids=REQ-PLAT-001
  STD-SEC-002@1 [cited] [blocking] Audit log retention and immutability
    matched by tags=compliance, tags=security, paths=specs/platform/tenant_isolation.md

Findings (7):
  ✗ [advisory] Unaddressed obligation: COM-PLAT-001 (version 2)
    COM-PLAT-001@2 applies to REQ-PLAT-001 but the spec does not cite it in complies_with
  ✗ [blocking] Stale citation: STD-SEC-001 (version 4)
    spec cites STD-SEC-001@3; version 4 is the applicable one
  ✗ [blocking] Unmet structural check: STD-SEC-001#has-isolation-test (version 4)
    STD-SEC-001@4 check 'has-isolation-test' requires 'verification_method in [test, both]'; REQ-PLAT-001 has verification_method='unspecified'
  ✗ [blocking] Unmet structural check: STD-SEC-001#risk-classified (version 4)
    STD-SEC-001@4 check 'risk-classified' requires 'risk_level in [critical, high]'; REQ-PLAT-001 has risk_level='unclassified'
  ✗ [blocking] Unmet structural check: STD-SEC-002#audit-verified (version 1)
    STD-SEC-002@1 check 'audit-verified' requires 'verification_method in [test, both]'; REQ-PLAT-001 has verification_method='unspecified'
  ✗ [blocking] Unmet structural check: STD-SEC-002#retention-stated (version 1)
    STD-SEC-002@1 check 'retention-stated' requires 'timing is set'; REQ-PLAT-001 has timing=''
  ✗ [blocking] Unmet structural check: STD-SEC-002#risk-classified (version 1)
    STD-SEC-002@1 check 'risk-classified' requires 'risk_level in [critical, high, medium]'; REQ-PLAT-001 has risk_level='unclassified'
```

Read the coverage block first. Three obligations bound to this spec, and the
`matched by` column says which scope rule pulled each one in. `STD-SEC-001`
matched four ways; `COM-PLAT-001` matched on its path glob alone.

Then the findings:

- **`COM-PLAT-001@2` is unaddressed.** The spec never mentions workspace
  durability. Because it is uncited, its checks go unevaluated — there is no
  point faulting the detail of an obligation the spec has not acknowledged.
- **`STD-SEC-001` is stale.** The spec cites `@3`; the corpus has moved to `@4`.
  The finding reports version 4, the applicable one, and the detail names the
  version the spec actually wrote.
- **Five checks are unmet**, all against the two cited entries. Each names the
  predicate and the value the requirement holds.

The exit code is 1, without `--strict`, because `STD-SEC-001` and `STD-SEC-002`
carry `enforcement: blocking`. See [Enforcement](#enforcement-belongs-to-the-owner).

### A spec whose findings are all advisory

`specs/billing/invoicing.md` cites the other end of a supersession chain, and
classifies itself:

```yaml
risk_level: high
verification_method: test
complies_with:
  - DEC-BILL-001@1
  - DEC-BILL-002@1
```

```bash
spectrace corpus review specs/billing/invoicing.md
```

```
Review of REQ-BILL-002 (specs/billing/invoicing.md)
Snapshot: 74ac5e6694ba

Coverage (2 entry versions surfaced):
  COM-BILL-001@1 [not cited] [advisory] Invoice accuracy guarantee
    matched by tags=billing, tags=finance, paths=specs/billing/invoicing.md, requirement_ids=REQ-BILL-002, tags=billing (via REQ-BILL-001), paths=specs/billing/subscriptions.md (via REQ-BILL-001)
  DEC-BILL-002@1 [cited] [advisory] Event stream is the metering source of truth
    matched by tags=billing, tags=finance, paths=specs/billing/invoicing.md, requirement_ids=REQ-BILL-002, tags=billing (via REQ-BILL-001), tags=subscriptions (via REQ-BILL-001), paths=specs/billing/subscriptions.md (via REQ-BILL-001), requirement_ids=REQ-BILL-001 (via REQ-BILL-001)

Findings (2):
  ✗ [advisory] Unaddressed obligation: COM-BILL-001 (version 1)
    COM-BILL-001@1 applies to REQ-BILL-002 but the spec does not cite it in complies_with
  ✗ [advisory] Orphan citation: DEC-BILL-001 (version 1)
    spec cites DEC-BILL-001@1, which does not apply to REQ-BILL-002
```

`DEC-BILL-002@1` is cited, applies, and faults nothing. Its three checks —
`risk-classified`, `metering-tested`, `no-batch-dependency` — all hold, because
the spec declares `risk_level: high` and `verification_method: test` and reads
no batch table. That coverage row is the shape a reviewer wants: the obligation
was surfaced, acknowledged, and satisfied, recorded at a pinned version.

`DEC-BILL-002@1` supersedes `DEC-BILL-001@1`, so the old decision no longer
binds and the citation to it is an **orphan**, not a stale citation. The
`(via REQ-BILL-001)` entries show applicability inherited from the parent
requirement: `REQ-BILL-002` sits under `REQ-BILL-001` in the hierarchy, and a
rule matching the parent reaches the child.

Every entry here is advisory, so the command exits 0 and the findings are a
reviewer's reading list rather than a gate. `--strict` overrides that for one
run:

```bash
spectrace corpus review specs/billing/invoicing.md --strict   # exit 1
```

### Why one spec passes `risk-classified` and the other does not

`risk_level` is a spec frontmatter field, declared by the author beside
`priority` and `verification_method`, and validated against the `RiskLevel`
choices at import. A value outside them names the file and refuses to import:

```
InvalidRiskLevelError: specs/billing/invoicing.md: risk_level 'severe' is not a
RiskLevel. Use one of: critical, high, medium, low, unclassified
```

`specs/billing/invoicing.md` declares `high`, so `DEC-BILL-002#risk-classified`
holds. `specs/platform/tenant_isolation.md` declares nothing, defaults to
`unclassified`, and fails the same check on two entries. Both outcomes are the
tool working. A spec that has not stated its blast radius genuinely has not
stated it, and declaring one line of frontmatter clears the finding.

Every check field is one of these three things — author-set, system-computed, or
populated by nothing at all. The full table is in
[Writing a corpus entry](corpus-authoring.md#what-populates-a-check-field).

## Enforcement belongs to the owner

Each entry version declares `enforcement: advisory` or `enforcement: blocking`.
The value is copied onto every coverage row and every finding at review time, so
a review record still says what blocked on the day it ran.

- A **blocking** finding exits 1. No flag needed.
- An **advisory** finding exits 0.
- `--strict` is the caller's override: treat every finding as blocking for this
  run. It is recorded nowhere.

Nothing computes a severity from the finding type or the count. The standard's
owner decides, in the corpus file, and escalating from advisory to blocking is a
version bump — `enforcement` joins the content hash.

Past reviews keep the posture that was in force when they ran. Escalating
`STD-SEC-001` to blocking in `@4` left the existing review rows recording `@3`
as advisory, and they stay as written. Rewriting them would destroy the evidence
`corpus drift` reads to notice the change.

## Reading the coverage ledger in an audit

```bash
spectrace corpus coverage --requirement REQ-BILL-002 --format text
spectrace corpus coverage --format json
```

```
REQ-BILL-002: 2 entries surfaced at 74ac5e6694ba on 2026-08-29T20:23:01.851676+00:00
  COM-BILL-001@1 [not cited] Invoice accuracy guarantee
  DEC-BILL-002@1 [cited] Event stream is the metering source of truth
  unaddressed: COM-BILL-001@1

Summary: 1 of 1 requirements reviewed, 2 entry versions surfaced
```

The ledger reports each requirement's **latest** review. An earlier review is
superseded by the later one and makes no live claim.

Three questions an auditor asks, and where the answer is:

- _Was this requirement ever reviewed?_ The `reviewed` field. A requirement with
  no review reports `reviewed: false` rather than being omitted — omission would
  hide exactly the gap the command exists to expose.
- _Against which corpus?_ `snapshot_hash`, which pins the exact set of entry
  versions in force.
- _Which obligations were surfaced, and were they acknowledged?_ The `coverage`
  rows and their `cited` flag. `unaddressed` is the subset the spec never cited.

## Drift: when the corpus moves

```bash
spectrace corpus drift --format text
spectrace corpus drift --format json --strict
```

Against a corpus that has not moved since the reviews ran, drift says so and
exits 0:

```
Corpus snapshot: 74ac5e6694ba

✓ No stale reviews

No newly applicable entries

Summary: 0 of 2 reviews stale, 0 entry versions newly applicable across 0 specs
```

Seeing the other answer takes a corpus that moved between a review and the
drift run. `DEC-BILL-002` supersedes `DEC-BILL-001`, and both entries are files
on disk, so importing them in two steps stages the move without editing
anything tracked:

```bash
mkdir -p /tmp/corpus-legacy/billing
cp corpus/billing/metering-source-legacy.md /tmp/corpus-legacy/billing/
python spectrace/manage.py parse_corpus /tmp/corpus-legacy/
spectrace corpus review specs/billing/subscriptions.md
python spectrace/manage.py parse_corpus corpus/
spectrace corpus drift --format text
```

The review runs while `DEC-BILL-001@1` is the only entry in the corpus, so it
covers that version. The second import brings in the successor:

```
Corpus snapshot: 74ac5e6694ba

Stale reviews (1):
  ✗ REQ-BILL-001 (specs/billing/subscriptions.md) reviewed at 2026-08-29T20:46:19.051191+00:00 on 9ea12bf141d6
    DEC-BILL-002@1 entered the corpus after this review and supersedes DEC-BILL-001@1

Newly applicable (1 specs):
  REQ-BILL-001:
    COM-BILL-001@1 (commitment) Invoice accuracy guarantee
    DEC-BILL-002@1 (decision) Event stream is the metering source of truth

Summary: 1 of 1 reviews stale, 2 entry versions newly applicable across 1 specs
```

The review is stale for a reason it can name: the decision it surfaced has been
replaced. Two other entries now reach the same spec and no review has ever put
them in front of anyone.

Staleness is derived, never stored. A review pins a snapshot and records which
entry versions it surfaced; the corpus as it stands now is another snapshot.
Those facts answer whether the review still holds, so no flag or cache can drift
away from the truth.

A change only reaches a review when the changed entry appears in that review's
own coverage rows, or supersedes a version those rows cover. A review that never
covered the changed entry is not stale, and naming it would train reviewers to
re-run everything on every corpus edit.

**Stale reviews** are reviews the corpus outran. **Newly applicable** is the
inverse question: obligations that now reach a spec no review ever put in front
of anyone.

Re-running `corpus review` on the named spec clears it. The old record stays;
the ledger keeps the past and drift reports the delta.

## `UnknownCitationError` versus `orphan_citation`

Both come from a `complies_with` line, and they are not the same failure.

**`orphan_citation` is a finding.** The cited entry version exists in the corpus
but does not apply to this spec — it was superseded, retired, or its scope rules
were narrowed. The review runs, records the whole ledger, and reports the
citation as one finding among others. That is the ordinary case, and
`DEC-BILL-001@1` above is an example of it.

**`UnknownCitationError` aborts the review.** The citation names an entry version
the corpus has never held, and the command writes nothing:

```bash
spectrace corpus review specs/platform/tenant_isolation.md
Error: spec cites DEC-IAM-001@1, which the corpus does not contain
```

It aborts rather than becoming a finding because `ReviewFinding.entry_version`
is a non-nullable foreign key: there is no row to point the finding at.

That is safe to fail loudly on. Versions are immutable and `parse_corpus`
refuses `--clear`, so a version that was ever imported never disappears. The
only way to reach this error is to type an id or a version that was never
parsed — an authoring mistake, not a corpus change. Check the spelling of the
entry id and the version number against the corpus file, then re-run.

Two neighbouring failures, for completeness:

```bash
Error: complies_with entry 'STD-SEC-002' must look like ENTRY-ID@VERSION, e.g. STD-SEC-001@3
```

A citation without a version is rejected before any review runs.

A citation naming a version **above** every version the entry holds aborts the
same way, and the message names the versions that exist:

```bash
Error: spec cites STD-SEC-001@9, which the corpus does not contain; STD-SEC-001 holds version 4
```

An unknown entry and a version digit typed too high are one authoring mistake,
so they get one treatment. A cited version at or **below** the newest is a
different case and stays a `stale_citation` finding even when no row holds it.
That is what `specs/platform/tenant_isolation.md` does: it cites
`STD-SEC-001@3`, the corpus file declares version 4, and a clone that never
held a row for version 3 still reports the citation as stale. The finding is
decided by the two version numbers, so it needs no database history — see
[the version model](corpus-authoring.md#the-version-model).

A spec file is reviewed atomically. If any one of its requirements raises on a
citation, the file records no review at all rather than half a ledger.

## Proving the canary still dies

The finding types are covered by a planted-failure canary,
`spectrace/requirements/tests/test_corpus_canary.py`, which plants one defect of
every type in fixture corpora that live outside `corpus/` and `specs/`.

A green canary proves nothing on its own — a test that cannot fail is worse than
no test. `scripts/canary_mutation_table.py` is how a maintainer proves it still
dies:

```bash
.venv/bin/python scripts/canary_mutation_table.py
```

It disables one detection at a time in `corpus_checks.py`, `corpus_matcher.py`,
or `corpus_parser.py`, runs the canary suite, restores the file, and prints a
markdown table of which assertions broke. Every mutation must turn the canary
red. A row reading `GREEN - canary blind` means the canary no longer detects
that class of defect, and the script exits nonzero.

Run it after changing anything in the review path, and after adding a finding
type.

> The script edits source files in place while it runs. Do not run it
> concurrently with a test run or with uncommitted work in those three files.

## Known gaps

- Nothing scales review depth to blast radius. A check reads `risk_level` as a
  predicate, and nothing asks for more scrutiny of a `critical` requirement than
  of a `low` one. The impact analyzer computes its own risk level for a change
  set and no review path reads it.

## Related

- [Writing a corpus entry](corpus-authoring.md) — frontmatter, scope rules, the
  predicate grammar, versioning
- `.claude/skills/spec-review/SKILL.md` — the agent skill that runs the tool and
  formats the result
