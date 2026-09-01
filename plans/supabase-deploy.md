Status: In progress

# Supabase Deploy

## Problem

Every checkout of every project runs its own SQLite file at `BASE_DIR /
db.sqlite3`. An agent in one repo cannot claim a task another repo created,
and the cross-project dependencies landing on `feat/cross-project-dependencies`
have no shared database to live in.

## Goal

One Postgres database on Supabase that every checkout, every CI run, and one
hosted Django admin all read and write.

## Success Criteria

- A Claude Code session in praxis runs `spectrace tasks claim <task-id>` with
  `DATABASE_URL` set and the claim shows in the hosted admin at `/admin/`
  within the same minute.
- spec-trace's own CI `Verification` job runs `migrate`, `parse_specs`, and
  `import_test_links` against Supabase instead of a throwaway SQLite file.
- `pytest` with no `DATABASE_URL` still runs on SQLite and stays green.
- `pytest` with `DATABASE_URL` pointed at Postgres is green.
- The hosted admin serves django-unfold's CSS and JS (no unstyled admin).
- `DEBUG=false` in production and `python manage.py check --deploy` reports no
  errors.

## Context

**What the repo has.** Django 5.2 WSGI monolith. `settings.py:216` hardcodes
SQLite. `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `SPECTRACE_API_KEY` already
read from the environment. `uv.lock` holds no `psycopg`, `gunicorn`,
`whitenoise`, or `dj-database-url`. No Dockerfile, no `STATIC_ROOT`.

**How clients reach the database.** `spectrace/cli.py` wraps
`call_command`, so the CLI and every `agent_*` and ingest command go through
the ORM. The HTTP API (`api_v1.py`) covers task list/claim/complete, coverage,
drift, impact, conflicts, and enforcement runs; `agent_submit`,
`agent_review`, `agent_merge`, and all ingestion have no HTTP path. Pointing
`DATABASE_URL` at Supabase makes every existing command a remote client with
no new endpoints.

**What stays on disk.** `parse_specs`, `parse_corpus`, `import_results`,
`import_test_links`, `agent_context` read files. `services/impact_analyzer.py`
and `services/git_cochange.py` shell out to `git` against `repo_path`
(default `Path.cwd()`). These run where the repo is checked out: a developer
machine or CI. The web tier never runs them.

**Supabase connection facts** (supabase.com/docs, Supavisor FAQ and Prisma
guide):

- The direct connection (`db.<ref>.supabase.co:5432`) is IPv6-only. GitHub
  Actions runners are IPv4-only.
- The session pooler (`aws-0-<region>.pooler.supabase.com:5432`) is IPv4
  reachable and supports server-side prepared statements. This is the
  connection for Django, CI, and developer machines.
- The transaction pooler (port 6543) drops prepared statements. Do not use it.
- Set `sslmode=require`; percent-encode reserved characters in the password.

**One backend-specific lookup.** `matrix.py:96` filters tags with
`tags__icontains` because SQLite lacks JSONField `__contains`. Django registers
`icontains` on JSONField for every backend by casting to text, so it runs on
Postgres, but it matches substrings (`api` matches `api-v2`) on both. The
Postgres test run decides whether anything else diverges.

**Cross-project model.** `docs/integration.md` describes installing spec-trace
as a library inside another Django app. This plan replaces that model with a
shared instance; the doc gets rewritten, not deleted.

**First consumers** (scan of `~/dev`, 2026-08-31):

| Repo                   | Why                                                                                                                                            |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `praxis`               | `specs/praxis.md` with `REQ-PRX-001..005`, a `spectrace-map.yaml` declaring `depends_on: spectrace:db/...`, CI. Already reads spec-trace data. |
| `cli/agent-of-empires` | 16 spec files under `specs/`, CI. No spec-trace wiring yet, so it proves the from-scratch path.                                                |

Praxis reads spec-trace today by opening
`~/dev/forge/spec-trace/spectrace/db.sqlite3` with `sqlite3`
(`praxis/src/praxis/spectrace.py:12`). `db_available()` returns `False` when
the file is missing, so praxis degrades to empty results rather than crashing
once the data moves. Repointing it at Postgres is a praxis change, listed under
follow-ups.

## What to Do

### 1. Database from the environment

File: `spectrace/spectrace/settings.py`

Add `dj-database-url>=2.3,<3.0` and `psycopg[binary]>=3.2,<4.0` to
`dependencies` in `pyproject.toml`. Replace the `DATABASES` block:

```python
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```

No `DATABASE_URL` means SQLite at the same path as today. Tests and `make run`
stay unchanged.

### 2. Postgres test run

Run the suite once against Postgres before touching anything else:

```bash
DATABASE_URL=postgres://postgres:postgres@localhost:5432/spectrace \
  python -m pytest -m "not demo" --tb=short -q
```

Fix every failure in this step. Expected candidates: `matrix.py:96`,
migration ordering under treebeard, any raw SQL. Record each fix in the
changelog.

### 3. Production serving

Files: `pyproject.toml`, `spectrace/spectrace/settings.py`, `Dockerfile`

Add `gunicorn>=23,<24` and `whitenoise>=6.8,<7.0` to `dependencies`. In
settings:

```python
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

Insert `whitenoise.middleware.WhiteNoiseMiddleware` directly after
`SecurityMiddleware`.

Dockerfile: `python:3.13-slim`, `uv pip install --system -e ./spectrace-flows
-e .`, `collectstatic --no-input` at build, entrypoint
`gunicorn spectrace.wsgi:application --bind 0.0.0.0:8000 --workers 2
--chdir spectrace`. Migrations run as a release command, not at container
start, so two replicas never race.

### 4. Hosting

Provider: Fly.io (`fly.toml` checked in). Region matching the Supabase
project. Secrets: `DATABASE_URL`, `SECRET_KEY`, `SPECTRACE_API_KEY`,
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DEBUG=false`.

Release command: `python spectrace/manage.py migrate --no-input`.

Supabase free tier. It pauses the project after seven idle days; a paused
database refuses connections until someone restores it from the dashboard.
Accepted: an agent that hits a paused database gets a connection error, and
whoever sees it presses Restore. Upgrade to Pro when that happens more than
once.

### 5. CI as writer

File: `.github/workflows/ci.yml`

The `Verification` job on `main` pushes gets `DATABASE_URL` from the
`SUPABASE_DATABASE_URL` repository secret. It keeps `migrate`: a migration can
merge before anyone runs `fly deploy`, and `parse_specs` against a stale
schema fails. `migrate` is idempotent, so the Fly release command and CI both
running it is harmless. Pull requests keep the throwaway SQLite build so a
broken PR never writes to the shared database.

The `Impact` job stays as is: it runs `impact_analysis` against the PR's git
history and posts a comment; it does not need the shared database.

### 6. Other repos

The Click CLI had no ingestion commands and `manage.py` is unreachable from an
installed package, so this step adds three thin wrappers: `spectrace specs
parse SPECS_DIR [--project]`, `spectrace results extract --path --output`, and
`spectrace results link LINKS_FILE`. Verified from the praxis checkout: `specs
parse specs --project praxis` wrote 8 requirements to Postgres.

Each consuming repo adds a `.env` or CI secret with the session-pooler
`DATABASE_URL` and installs spec-trace from git as `docs/integration.md`
already shows. Rewrite `docs/integration.md` around the shared instance:
install the CLI, set `DATABASE_URL`, run `parse_specs` from your own
`specs/`, and claim tasks. Remove the "add to `INSTALLED_APPS`" section.

### 7. Accounts

Create staff accounts in the hosted admin for each person who reads status
pages. The status pages already sit under `admin/`, so the admin login gates
them.

## What NOT to Do

- Do not use Supabase Auth, RLS, PostgREST, Storage, or Edge Functions. Django
  owns the schema and the login. Supabase is a Postgres host.
- Do not add HTTP endpoints for submit, review, merge, or ingest. Direct
  Postgres is the transport for every client in this pass.
- Do not add per-project or per-agent API keys. One `SPECTRACE_API_KEY`,
  rotated by hand.
- Do not run `git`, `impact_analysis`, or `parse_specs` on the web tier. It
  has no repo checkout.
- Do not connect through the transaction pooler (6543).
- Do not build multi-tenant isolation. The `project` column separates
  projects; every credential holder sees every project.
- Do not remove SQLite as the default. Local dev and tests without
  `DATABASE_URL` stay exactly as they are.

## Decisions

- First consumer: praxis. Second: `cli/agent-of-empires`.
- The `Impact` job stays on PR-local SQLite and git history. PR runs never
  hold the shared credential. Cross-project impact from the shared database
  is a later pass.
- Supabase free tier, pause accepted.

## Follow-ups (outside this plan)

- praxis: replace the `sqlite3` reader in `src/praxis/spectrace.py` with a
  Postgres connection from `DATABASE_URL`, or with calls to the hosted API.

## Acceptance Criteria

- [x] `DATABASE_URL` unset: `pytest` green on SQLite.
- [x] `DATABASE_URL` set to Postgres: `pytest` green.
- [x] `docker build` succeeds and the image serves `/admin/login/` with
      django-unfold styling.
- [x] `fly deploy` runs migrations as the release command and serves the
      admin at the public URL with `DEBUG=false`.
- [x] `manage.py check --deploy` reports zero errors against production env.
- [x] CI `Verification` on `main` writes to Supabase; on PRs it uses SQLite.
      Run 33516765697 (2026-09-01 14:00 UTC): "No migrations to apply",
      "updated 117 existing links", Supabase `updated_at` matches.
- [ ] praxis runs `spectrace specs parse specs/` and `spectrace tasks claim`
      with `DATABASE_URL` set; `REQ-PRX-*` and the claim appear in the hosted
      admin.
- [x] `docs/integration.md` describes the shared-instance model.
- [x] CHANGELOG.md covers every commit.
