---
id: REQ-CANARY-002
title: Canary requirement citing a version the fixture corpus never held
status: active
priority: high
tags: [canary-fixture]
component: storage
verification_method: test
timing: within 4 hours
complies_with: [CANARY-STD-STALE@9]
---

# Canary requirement citing an unstored version

`CANARY-STD-STALE` exists at versions 1 and 2, and this spec cites version 9.
The entry applies to this requirement, so every citation rule finds a version to
compare against and none of them faults a citation for being newer than the one
that applies. Reviewing this file must raise `UnknownCitationError` naming the
entry, the cited version, and the versions that exist.

It lives in its own file because the error aborts the whole review. Adding the
citation to `canary_spec.md` would take every other planted defect down with it.

Editing this file without editing `test_corpus_canary.py` breaks the canary.
