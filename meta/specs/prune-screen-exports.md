---
id: REQ-WORKER-SCREENS-001
title: Prune the surviving Worker screen modules
tags: [spectrace, worker, screens]
priority: medium
status: active
risk_level: low
verification_method: test
complies_with:
  - STD-WORKER-001@1
---

# Prune the surviving Worker screen modules

PR #2 deleted the 38 Worker screens the dashboard replaced and kept five files
under `worker/src/screens/`: the demo route, the demo page, its catalog, the
layout helper, and the `/admin/*` redirects. All five are mounted. Two of them
still carry code that nothing reaches: the retired admin chrome in
`layout.tsx` and the demo-card helpers in `data/demos.ts`.

## User-visible behavior

Nothing changes for a visitor. `GET /demo/` renders the same page byte for
byte. `/` and every retired `/admin/*` path redirect to the same destination
as before. The change is to the source: each screen module keeps only what the
demo page and the redirects use.

## Acceptance criteria

1. Every symbol exported from a module under `worker/src/screens/` is imported
   by name from at least one other module under `worker/src/`.
2. `worker/src/screens/layout.tsx` exports exactly one symbol, `renderScreen`.
3. `worker/src/screens/data/demos.ts` exports exactly one symbol,
   `demoCatalog`.
4. No module under `worker/src/screens/` other than `redirects.ts` contains an
   `/admin/` path.
5. `GET /demo/` returns the same body as before the change, pinned by SHA-256.
6. `GET /` still redirects to `/demo`, and every `/admin/*` redirect keeps its
   status and destination.
7. `npm run typecheck` and the full Worker suite pass.

## Out of scope

- The React dashboard under `app/` and its Worker.
- The Python package and its tests.
- The content of the demo page or the redirect map.
- Deploying. CI deploys on every push to `main`, so this work stays on its
  branch until someone merges it.

## Failure modes

- Deleting `paths` strands the import in `data/demos.ts`. `tsc` catches it;
  the fix deletes the import together with `webDemoUrls`.
- An export audit that matches words instead of import specifiers passes or
  fails for the wrong reason. The test resolves each
  `import { … } from "<relative path>"` to a file and matches names against
  that file's exports. The red run must name `Layout`, `Page`, `route`,
  `paths`, `LayoutProps`, `PageProps`, `Demo`, `DemoCard`, and `demoCards`.
- Type-only exports are invisible to a module namespace. The audit reads source
  text, so `export type` and `export interface` count.
- The body pin drifts on an unrelated content edit. That is the pin working; a
  deliberate content change updates the hash in the same commit.
- Vite's `import.meta.glob` may not resolve inside the workers pool. The
  fallback injects the sources as a test binding at config time, the way
  `CONTRACT` reaches `contract.test.ts` today.
