---
name: spec-review
description: 'Review a spec in this repo against the SpecTrace corpus of org standards, decisions, and commitments. Runs `spectrace corpus review` and formats what it emits. Use when the user asks to review a spec against the corpus, check which standards a spec touches, find unaddressed obligations or stale citations, or says "corpus review this", "which standards apply to this spec", "is this spec covered".'
---

# Corpus spec review

You run one tool and format its output. The tool decides everything.

`spectrace corpus review` is a deterministic rule engine over a versioned corpus
of standards, decisions, and commitments. It emits five finding types and a
coverage row per applicable entry. Your job is to run it, present the result so a
human reviewer can act on it, and stop.

## Rules

These are rules, not guidance. Breaking one makes the review record worthless,
because the whole point is that every printed line traces to an entry id and a
rule outcome.

1. **Add no finding the tool did not emit.** Not a suspicion, not a
   "you may also want to consider", not a sixth category you invented. If the
   JSON has seven findings, your output has seven findings.
2. **Reword no obligation.** Quote the entry body verbatim. Do not summarize,
   soften, paraphrase, or "clarify" what a standard demands. If you need fewer
   words, quote fewer words and mark the elision.
3. **Judge nothing.** You cannot decide whether a spec honors an obligation. The
   tool cannot either. Present the obligation and let the reviewer decide.
4. **Invent no severity.** Enforcement is `advisory` or `blocking`, read off the
   entry version. Do not rank, score, or escalate.
5. **Report the exit code and the error verbatim** when the command fails. Do
   not work around an error by guessing what the review would have said.

## Commands

Run from the repo root.

```bash
# The review. Emit md for a human, json for yourself.
spectrace corpus review <spec-path> --format md --reviewer "<who>"
spectrace corpus review <spec-path> --format json

# Context, when the user asks for it
spectrace corpus coverage --requirement <REQ-ID> --format json
spectrace corpus drift --format json
spectrace corpus suggest --requirement <REQ-ID> --format json
```

The target is a spec file path (`specs/platform/tenant_isolation.md`) or a
requirement external id (`REQ-PLAT-001`).

Exit codes: `review` exits 1 when a finding carries `enforcement: blocking`, or
when `--strict` is passed and any finding exists. `coverage` and `suggest`
always exit 0. Nonzero from `review` is a result, not a failure — report it.

## Workflow

1. Run `--format json` and read it. That is your source of truth.
2. Run `--format md` for the tables, or build them from the JSON.
3. Write the output described below.
4. Every finding in the JSON appears in your output. Nothing else does.

If the command errors, print the error verbatim and stop. Two you will see:

- `complies_with entry 'X' must look like ENTRY-ID@VERSION` — the spec cites an
  entry without a version.
- `spec cites X@N, which the corpus does not contain` — `UnknownCitationError`.
  The whole review aborted and wrote nothing. This is different from an
  `orphan_citation` finding, which is a finding inside a review that ran. See
  `docs/corpus-review.md`.

## Output

### 1. Header

The requirement id, the spec file, the corpus snapshot hash, and the exit code.

### 2. Coverage table

Straight from the JSON `coverage` array. One row per applicable entry version,
including the ones with no finding — a row is the record that the obligation was
put in front of the reviewer.

| Entry | Version | Kind | Enforcement | Cited | Matched by |
| ----- | ------- | ---- | ----------- | ----- | ---------- |

### 3. Findings, grouped by enforcement

Blocking first, then advisory. Within each group, the tool's order. Report each
finding's `finding_id` (`STD-SEC-001#risk-classified`), its `entry_version` as a
separate column, and its `detail` verbatim.

### 4. Reviewer checklist

For every `unaddressed_obligation` finding, one checklist item. This is the
half a human acts on, so it carries the most weight:

```markdown
## Reviewer checklist

- [ ] **COM-PLAT-001@2** — Workspace durability and recovery window
      (`corpus/platform/workspace-durability-commitment.md`, advisory)

  > We commit to customers that a deleted workspace is recoverable for 30 days
  > and that no workspace content is destroyed before that window closes.
  >
  > A spec that deletes, archives, or migrates workspace content MUST state the
  > recovery window it honors and MUST name the test that proves content
  > survives the documented period.

  Decide: does this spec touch that, and if so, cite `COM-PLAT-001@2` in
  `complies_with` or record why it does not apply.
```

Read the entry body out of its corpus file to quote it. Find the file by entry
id under `corpus/`, or:

```bash
grep -rl "^id: COM-PLAT-001" corpus/
```

Quote the body. Link the file. Add nothing between the blockquote and the file
path.

### 5. Nothing else

No summary of what the spec is about. No opinion on the design. No suggested
edits to the spec prose. No "overall this looks good."

## Fixing what the review found

When the user asks how to clear a finding, the answer is always an edit to
frontmatter or to a corpus file, never a rewrite of spec prose.

| Finding                   | Fix                                                                                      |
| ------------------------- | ---------------------------------------------------------------------------------------- |
| `unaddressed_obligation`  | Add `ENTRY-ID@VERSION` to the spec's `complies_with`, after the human decides it applies |
| `stale_citation`          | Bump the version in `complies_with` after re-reading the newer entry                     |
| `orphan_citation`         | Remove the citation, or widen the entry's `applies_to` in the corpus file                |
| `unmet_check`             | Set the requirement field the check names                                                |
| `conflicting_obligations` | A human resolves it in the corpus. Neither you nor the tool picks a winner               |

Never edit `complies_with` on the user's behalf without being asked. A citation
is a claim that a human read the obligation.

## Reference

- `docs/corpus-review.md` — running a review, the ledger, drift, the
  `UnknownCitationError` versus `orphan_citation` distinction
- `docs/corpus-authoring.md` — frontmatter, scope rules, the predicate grammar,
  the versioning contract
