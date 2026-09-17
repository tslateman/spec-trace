# spec-trace Worker

The spec-trace server on Cloudflare Workers: Hono routes, Drizzle on D1, and a
`TaskLedger` Durable Object per project. The Python CLI reads specs, tests, and
git where the repo lives and pushes here; this Worker stores and serves. Data
screens live in the dashboard (`app/`) and the old URLs redirect there; one
public demo page stays at `/demo/`. The contract is [`plans/openapi-worker.yaml`](../plans/openapi-worker.yaml);
the design is [`plans/cloudflare-port.md`](../plans/cloudflare-port.md).

## Develop

```sh
npm install
npm run typecheck        # wrangler types + tsc
npm test                 # vitest against a migrated local D1
npm run dev              # http://localhost:8787, key from .dev.vars
```

Load the real data into local D1 and check every table's row count:

```sh
rm -rf .wrangler/state
python3 scripts/dump-data.py ../spectrace/db.sqlite3 /tmp/data.sql
npx wrangler d1 migrations apply spectrace --local
npx wrangler d1 execute spectrace --local --file=/tmp/data.sql
scripts/rowcounts.sh ../spectrace/db.sqlite3
```

Prove the Worker answers like Django (both servers running on the same data):

```sh
python3 scripts/parity-diff.py --django http://localhost:8000 \
  --worker http://localhost:8787 --api-key dev-key
```

Schema changes go in `src/db/schema.ts`; `npm run db:generate` writes the
migration and `migrations/meta/` must be committed with it.

## Deploy once

```sh
npx wrangler login
npx wrangler d1 create spectrace          # paste database_id into wrangler.toml
npx wrangler secret put SPECTRACE_API_KEY
npx wrangler d1 migrations apply spectrace --remote
npx wrangler d1 execute spectrace --remote --file=/tmp/data.sql
npx wrangler deploy
```

Then in the Cloudflare dashboard:

- **Rate limiting:** a WAF rate-limit rule on `/api/*` in place of
  `django-ratelimit`.

## Deploy on every merge

`.github/workflows/worker.yml` typechecks and tests on every PR that touches
`worker/`, then on `main` applies migrations, runs `wrangler deploy`, and
pushes the repo's specs, links, and flows. It needs these repository secrets:
`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `SPECTRACE_URL`,
`SPECTRACE_API_KEY`.

## Feed it

From any checkout or CI job:

```sh
export SPECTRACE_URL=https://spectrace.example.workers.dev SPECTRACE_API_KEY=…
spectrace push --specs specs --flows flows --links links.json
spectrace results push junit.xml --links links.json
spectrace specs impact main HEAD --push
spectrace specs drift --push
spectrace lore sync
```

`spectrace lore sync` drains merged and abandoned task outcomes from
`GET /api/v1/tasks/outcomes` into Lore's journal and acknowledges them. The
Worker never calls Lore.
