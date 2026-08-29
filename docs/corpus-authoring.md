# Writing a corpus entry

A corpus entry is one org standard, decision, or commitment, written as a
markdown file under `corpus/`. `parse_corpus` reads it into an immutable
version. `spectrace corpus review` decides which specs it binds to and which of
its checks they fail.

> This guide lives in `docs/`, not in `corpus/`. `parse_corpus` globs
> `corpus/**/*.md` and rejects any file that lacks entry frontmatter, so a
> `corpus/README.md` fails the whole import:
>
> ```
> CommandError: corpus/README.md: missing required frontmatter keys ['id', 'kind', 'title', 'version']
> ```

## File layout

```markdown
---
id: STD-SEC-001
kind: standard
title: Tenant data isolation
version: 4
status: active
supersedes: null
effective: 2026-08-29
owner: platform
enforcement: blocking
applies_to:
  tags: [platform, security]
  components: [api, storage]
  paths: ["specs/platform/**", "specs/workspaces/**"]
  requirement_ids: ["REQ-PLAT-*"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
  - id: has-isolation-test
    assert: verification_method in [test, both]
---

Every query that reads tenant-scoped data MUST filter by tenant at the
persistence layer. Application-level filtering does not satisfy this standard.
```

Import it:

```bash
python spectrace/manage.py parse_corpus corpus/ --dry-run
python spectrace/manage.py parse_corpus corpus/
```

`parse_corpus` is idempotent and refuses `--clear`. Entry versions are
immutable, and review records point at them.

## Frontmatter keys

| Key              | Required | Value                                                                      |
| ---------------- | -------- | -------------------------------------------------------------------------- |
| `id`             | yes      | External id, unique across the corpus. `STD-SEC-001`, `DEC-BILL-002`       |
| `kind`           | yes      | `standard`, `decision`, or `commitment`                                    |
| `title`          | yes      | One line, shown in every report                                            |
| `version`        | yes      | Positive integer. Bump it whenever the pinned content changes              |
| `status`         | no       | `active`, `superseded`, or `retired`. Defaults to `active`                 |
| `supersedes`     | no       | `ENTRY-ID@VERSION` naming the version this one replaces                    |
| `effective`      | no       | `YYYY-MM-DD`. Part of the content hash                                     |
| `owner`          | no       | Team or person accountable for the entry                                   |
| `enforcement`    | no       | `advisory` or `blocking`. Defaults to `advisory`. Part of the content hash |
| `applies_to`     | no       | Scope rules. Absent or empty means the entry binds to **nothing**          |
| `checks`         | no       | Structural predicates over requirement fields                              |
| `retired_checks` | no       | Check ids the previous version defined and this version drops on purpose   |

`kind`, `status`, and `enforcement` are closed sets. An unknown value rejects
the file.

### What a version pins

The content hash covers `kind`, `title`, the body, `applies_to`, `checks`,
`enforcement`, and `effective`. Change any of them and you must bump `version`,
or the import fails:

```
CommandError: STD-SEC-001 version 4 changed without a version bump. Stored hash …,
incoming hash … from corpus/security/tenant-isolation.md. Bump `version` to record
the new content.
```

`owner`, `status`, and `source_file` sit on the entry rather than the version,
so editing them takes no bump.

Escalating `enforcement` from `advisory` to `blocking` is a version bump like
any other. That is deliberate: escalation changes what the standard demands of
a spec, and a review record has to be able to say which posture was in force
when it ran.

### The version model

**One file per entry, at its current version.** `corpus/security/tenant-isolation.md`
carries `version: 4` and nothing else on disk carries version 3. Bumping an
entry means editing that one file and raising the number in it.

**The database accumulates the history.** Each import writes a new immutable
`CorpusEntryVersion` row, and the earlier rows stay. A checkout that parsed the
file at version 3 and again at version 4 holds both; snapshots pinned by reviews
point at the version that was current when each ran.

**A fresh deployment starts at the current version.** `make migrate &&
parse_corpus corpus/` on a clone yields one version per entry — the version its
file declares. There is no earlier history to import, because the earlier bodies
live in git, not in `corpus/`.

Three consequences worth stating plainly:

- Nothing documented or demonstrated may depend on a version absent from the
  corpus files. `spectrace/requirements/tests/test_docs_walkthrough.py` seeds a
  fresh database from `corpus/` and `specs/`, runs the commands
  [Corpus-backed spec review](corpus-review.md) prints, and compares the output
  against the documented blocks.
- A spec citing a version below the one on disk gets a `stale_citation` finding
  whether or not a row for that version exists. The finding compares two numbers.
- A supersession demo needs no history at all, because supersession crosses
  entries: `metering-source-legacy.md` holds `DEC-BILL-001` and
  `metering-source.md` holds `DEC-BILL-002`, both on disk.

## Scope rules: `applies_to`

Four keys, all optional, all lists. An entry version binds to a requirement when
**any** pattern under **any** key matches.

| Key               | Matched against           | Matching                  |
| ----------------- | ------------------------- | ------------------------- |
| `tags`            | `Requirement.tags`        | **Exact string equality** |
| `components`      | `Requirement.component`   | **Exact string equality** |
| `paths`           | `Requirement.source_file` | Glob (`fnmatchcase`)      |
| `requirement_ids` | `Requirement.external_id` | Glob (`fnmatchcase`)      |

Three rules that surprise authors, each chosen on purpose:

**An empty `applies_to` matches nothing.** Never everything. A half-written
entry that fired on every spec would train reviewers to skim past the output.
Omit the block and the entry binds to no spec at all.

**`tags` and `components` do not glob.** An entry scoped
`components: [api]` never binds to a requirement whose component is
`api-gateway`, and the author gets silence rather than a warning. That silence
is why `spectrace corpus suggest` exists — see
[Near misses](#near-misses-and-corpus-suggest) below.

**Only the newest version of an entry applies.** A snapshot may hold
`STD-SEC-001@3` and `@4`; a review binds `@4` alone. Older versions stay in the
snapshot because it records what the corpus held, so a review pinned before the
bump still resolves the version current then. A version superseded by another
member of the same snapshot never applies, and a `retired` entry never applies.

Scope rules are read off the version that wins. A bump that narrows `applies_to`
narrows what binds; it does not leave the older rules standing.

### Inheritance

Applicability inherits down the requirement hierarchy. A rule matching an
ancestor applies to its descendants, and the report names the ancestor it came
from:

```
matched by tags=billing, requirement_ids=REQ-BILL-002, tags=billing (via REQ-BILL-001)
```

## Checks: the predicate grammar

Each check has an `id` and an `assert`. The grammar is closed and validated at
parse time. Nothing is ever evaluated as an expression.

```
<field> in [a, b]          <field> not in [a, b]
<field> == value           <field> != value
<field> contains value     <field> not contains value
<field> is set             <field> is not set
```

Fields, all read off the `Requirement` row:

```
risk_level            verification_method   verification_status   slo_status
priority              status                tags                  component
timing                scope                 condition             response
depends_on
```

`tags` and `depends_on` are list-valued: `in` and `not in` use set
intersection, `contains` uses membership, `==` holds only when the list is
exactly the one value. The rest are scalars, where `contains` is a substring
test.

### What populates a check field

A check is only worth writing if something can satisfy it. Each of the thirteen
fields is filled by the spec author, computed by a command, or filled by nothing
at all — and a check on a field nothing fills is permanently red, which teaches
reviewers to skip the findings table.

| Field                 | Filled by                                                   | Where               |
| --------------------- | ----------------------------------------------------------- | ------------------- |
| `risk_level`          | Author, in frontmatter. Validated against `RiskLevel`       | `parse_specs`       |
| `verification_method` | Author, in frontmatter. Unknown values become `unspecified` | `parse_specs`       |
| `priority`            | Author, in frontmatter. Free text                           | `parse_specs`       |
| `status`              | Author, in frontmatter. Defaults to `draft`                 | `parse_specs`       |
| `tags`                | Author, in frontmatter. List                                | `parse_specs`       |
| `component`           | Author, in frontmatter (FRET)                               | `parse_specs`       |
| `timing`              | Author, in frontmatter (FRET)                               | `parse_specs`       |
| `scope`               | Author, in frontmatter (FRET)                               | `parse_specs`       |
| `condition`           | Author, in frontmatter (FRET)                               | `parse_specs`       |
| `response`            | Author, in frontmatter (FRET)                               | `parse_specs`       |
| `depends_on`          | Author, in frontmatter. Ids resolved after import           | `parse_specs`       |
| `verification_status` | System, from linked test results                            | `import_results`    |
| `slo_status`          | System, from linked SLOs                                    | `update_slo_status` |

Nothing is unpopulated today. `risk_level` was, until a spec author could
declare it: every seed entry asserts `risk_level in [critical, high]`, the spec
parser read eleven frontmatter keys and not that one, and every real review
reported the same unmeetable finding.

Two things to know before writing a check:

**Computed fields are the good case, not a trap.** `verification_status` and
`slo_status` come from `import_results` and `update_slo_status`, so a check on
them asks whether the tests pass or the SLO holds — a question the author
answers by doing the work, not by editing frontmatter. They read `untested` and
`not_linked` in a database that has imported neither.

**Only `risk_level` rejects a bad value.** `verification_method` normalizes an
unknown value to `unspecified` and says nothing, so `verification_method: tests`
silently fails every `verification_method in [test, both]` check. `priority` and
`status` are free text and validate nothing at all. A check reading them is a
string comparison against whatever the author typed.

Values are bare words (`[A-Za-z0-9._-]+`) or quoted strings. Quoting is the
only way to carry a space, which keeps composed expressions such as `a and b`
out of the grammar. An unknown field, an unknown operator, an unbracketed list,
or a list where a scalar belongs all reject the file.

A check fires an `unmet_check` finding only when the spec **cites** the entry.
An uncited applicable entry produces an `unaddressed_obligation` instead, and
its checks go unevaluated — there is no point faulting the detail of an
obligation the spec never acknowledged.

### Check ids are a public identifier

A finding is cited as `STD-SEC-001#risk-classified`, with the version reported
beside that id and never inside it. That is what lets a reviewer track one
finding across a standard's edits — so a new version may not silently drop or
rename a check id.

Every id the previous version defined must be accounted for in the next one:

- keep it, or
- put `renamed_from: <old-id>` on the check that replaces it, or
- list it under the entry-level `retired_checks`.

`COM-BILL-001@1` defines `risk-classified`, `accuracy-tested`, and
`slo-linked`. Version 2 renames the first and drops the last:

```yaml
id: COM-BILL-001
version: 2
retired_checks: [slo-linked]
checks:
  - id: risk-level-set
    renamed_from: risk-classified
    assert: risk_level in [critical, high]
  - id: accuracy-tested
    assert: verification_method in [test, both]
```

Silence raises `CorpusCheckLineageError` and names the fix:

```
STD-SEC-001 version 5 drops check 'risk-classified' while adding 'risk-level-set'.
Findings cite STD-SEC-001#risk-classified without a version, so declare
`renamed_from: risk-classified` on check 'risk-level-set', or list
'risk-classified' under `retired_checks`.
```

`renamed_from` must name a check the previous version actually defines, and the
current version must not still define it. `retired_checks` must name ids the
previous version defines and the current one does not.

`resolve_check_id(entry_id, check_id)` follows declared renames forward, so a
consumer holding an id from an old finding lands on the current check.

## Superseding an entry

Write a new file with a new `id`, point `supersedes` at the exact version it
replaces, and set the old entry's `status` to `superseded`:

```yaml
# corpus/billing/metering-source.md
id: DEC-BILL-002
supersedes: DEC-BILL-001@1
```

```yaml
# corpus/billing/metering-source-legacy.md
id: DEC-BILL-001
status: superseded
```

Once `DEC-BILL-002@1` is in the snapshot, `DEC-BILL-001@1` stops applying. A
spec still citing it gets an `orphan_citation` finding, not a `stale_citation`
one: the citation names a real version that no longer binds, rather than an
older version of something that still does.

Keep the superseded file. Removing it would not remove the stored version —
`parse_corpus` refuses `--clear` and reviews reference the row — and the file is
where a reader finds out why the decision changed.

## Near misses and `corpus suggest`

```bash
spectrace corpus suggest --format text
spectrace corpus suggest --requirement REQ-PLAT-002 --min-score 0.2 --format json
```

`corpus suggest` reports the scope-rule edits that would close a gap the exact
matcher cannot see. It writes no row, no file, and no nonzero exit. A suggestion
is a proposal for a human to accept into a corpus file.

Two kinds, reported strongest first:

**Near-miss scope rules.** A value already in the rule, spelled one segment or
one plural off — `components: [api]` against a requirement whose component is
`api-gateway`, or `workspaces` against `workspace`. `requirement_ids` gets one
rule of its own: a pattern differing only in the trailing id widens to the
family, `REQ-PLAT-001` to `REQ-PLAT-*`. Near misses ignore `--min-score`.

**Text similarity.** TF-IDF cosine over the entry body and the spec prose,
computed in plain Python — no model, no network call. It proposes the narrowest
edit that closes the gap: a `requirement_ids` pattern naming the one spec.
`--min-score` is its floor, default `0.12`.

`paths` produces no near miss. Its patterns already glob across separators, so
widening a differing segment generated twelve suggestions against the seed
corpus and every one was noise.

## Errors you will hit

| Error                                              | Cause                                                                       |
| -------------------------------------------------- | --------------------------------------------------------------------------- |
| `missing required frontmatter keys`                | A `.md` under `corpus/` that is not an entry, or a genuinely incomplete one |
| `changed without a version bump`                   | Body, scope, checks, enforcement, kind, title, or effective edited in place |
| `CorpusCheckLineageError`                          | A check id dropped or renamed without `retired_checks` or `renamed_from`    |
| `does not match the check grammar`                 | An operator or shape outside the closed grammar                             |
| `references unknown field`                         | A check field that is not a `Requirement` field                             |
| `declared in both … and …`                         | Two files claiming one `id`                                                 |
| `supersedes … names a version that does not exist` | A `supersedes` target absent from both the corpus and the database          |
| `--clear is not supported for the corpus`          | Entry versions are immutable and reviews reference them                     |

## Related

- [Corpus-backed spec review](corpus-review.md) — running a review end to end
- `.claude/skills/spec-review/SKILL.md` — the agent skill that runs the tool
