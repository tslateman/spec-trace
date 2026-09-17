# Session API (TypeScript)

A vitest example that links tests to requirements through the bracketed tag
SpecTrace reads from any JUnit report.

The API issues a session token (`SES-AUTH-001`), refuses a locked account
(`SES-AUTH-002`), and expires a token after an hour (`SES-TTL-001`).

## Layout

```
session-api-typescript/
├── spectrace-map.yaml           # project: session-api
├── specs/session/
│   ├── SES-001.md               # Root requirement
│   ├── SES-AUTH-001.md          # Issue a session
│   ├── SES-AUTH-002.md          # Refuse a locked account
│   └── SES-TTL-001.md           # Session expiry
├── src/session.ts
├── test/session.test.ts
├── vitest.config.ts
└── ci/github-actions.yml
```

## Linking a test

A tag on a `describe` block links every test inside it. A tag on one `it` links
that test as well:

```typescript
describe("POST /sessions [SES-AUTH-001]", () => {
  it("issues a token naming its subject", () => { ... });

  it("[SES-AUTH-002] issues no token for a locked account", () => { ... });
});
```

Vitest joins the names with `>`, so the second case links both requirements.

## Running it

The JUnit reporter comes with vitest:

```typescript
// vitest.config.ts
test: {
  reporters: ["default", ["junit", { classnameTemplate: "examples/session-api-typescript/{filename}" }]],
  outputFile: { junit: "junit.xml" },
},
```

```bash
npm ci
npm test
```

```
 ✓ test/session.test.ts (6 tests) 2ms

 Test Files  1 passed (1)
      Tests  6 passed (6)

JUNIT report written to .../examples/session-api-typescript/junit.xml
```

`classnameTemplate` decides the test nodeid SpecTrace stores, so point it at the
path the requirement's readers expect.

## Pushing

One file carries both the links and the results:

```bash
spectrace push --specs specs --links junit.xml --replace
spectrace results push junit.xml
```

`ci/github-actions.yml` runs the same three commands on every change.
