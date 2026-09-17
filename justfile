python := if path_exists(".venv/bin/python") == "true" { ".venv/bin/python" } else { "python3" }

# List available recipes
default:
    @just --list --unsorted

# --- Setup ---

# Create the virtualenv if it is missing
[group('setup')]
venv:
    @test -d .venv || uv venv

# Install the package and spectrace-flows in editable mode
[group('setup')]
install: venv
    uv pip install -e ./spectrace-flows -e .

# Install with dev dependencies and point git at .githooks
[group('setup')]
install-dev: venv
    uv pip install -e ./spectrace-flows -e ".[dev]"
    git config core.hooksPath .githooks

# Install the Worker and dashboard npm dependencies
[group('setup')]
install-js: worker-deps app-deps

[private]
worker-deps:
    @test -d worker/node_modules || (cd worker && npm ci)

[private]
app-deps:
    @test -d app/node_modules || (cd app && npm ci)

# Create the admin user (admin/admin)
[group('setup')]
setup:
    {{python}} scripts/setup.py

# --- Secrets ---

# Store a secret in the login keychain, prompting for the value
[group('secrets')]
secret-set name="spectrace-api-key":
    @security add-generic-password -U -s "{{name}}" -a "$USER" -w

# Report which keychain secrets are present
[group('secrets')]
secret-list:
    #!/usr/bin/env bash
    for name in spectrace-api-key; do
      if security find-generic-password -s "$name" -a "$USER" >/dev/null 2>&1; then
        echo "$name: present"
      else
        echo "$name: missing -- run 'just secret-set $name'"
      fi
    done

# Write the dummy values local development needs, never a deployed secret
[group('secrets')]
dev-secrets:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -f worker/.dev.vars ]; then
      echo "worker/.dev.vars already exists"
      exit 0
    fi
    umask 077
    echo "SPECTRACE_API_KEY=dev-key" > worker/.dev.vars
    echo "wrote worker/.dev.vars"

# --- Python ---

# Run the test suite, skipping demos
[group('python')]
test:
    {{python}} -m pytest -m "not demo"

# Lint with ruff
[group('python')]
lint:
    ruff check spectrace/ spectrace-flows/

# Check ruff formatting
[group('python')]
format:
    ruff format --check spectrace/ spectrace-flows/

# Rewrite files to ruff's format
[group('python')]
format-fix:
    ruff format spectrace/ spectrace-flows/

# Lint, format, changelog gate, and tests; CI adds the verification and impact jobs
[group('python')]
check: lint format changelog-check test

# --- Django (retiring with the Cloudflare port) ---

# Apply Django migrations
[group('django')]
migrate:
    {{python}} spectrace/manage.py migrate

# Create Django migrations
[group('django')]
makemigrations:
    {{python}} spectrace/manage.py makemigrations

# Open the Django shell
[group('django')]
shell:
    {{python}} spectrace/manage.py shell

# Start the Django development server
[group('django')]
run:
    {{python}} spectrace/manage.py runserver

# --- Worker ---

# Typecheck the Worker
[group('worker')]
worker-typecheck: worker-deps
    cd worker && npm run typecheck

# Lint and format-check the Worker with Biome
[group('worker')]
worker-lint: worker-deps
    cd worker && npm run lint

# Run the Worker test suite
[group('worker')]
worker-test: worker-deps
    cd worker && npm test

# Serve the Worker against local D1
[group('worker')]
worker-dev: worker-deps dev-secrets
    cd worker && npm run dev

# Apply Worker D1 migrations locally
[group('worker')]
worker-migrate-local: worker-deps
    cd worker && npm run db:migrate:local

# Deploy the Worker (CI does this on merge to main)
[group('worker')]
worker-deploy: worker-deps
    cd worker && npm run db:migrate:remote && npm run deploy

# --- Dashboard ---

# Typecheck the dashboard
[group('app')]
app-typecheck: app-deps
    cd app && npm run typecheck

# Run the dashboard tests
[group('app')]
app-test: app-deps
    cd app && npm test

# Lint and format-check the dashboard with Biome
[group('app')]
app-lint: app-deps
    cd app && npm run lint

# Build the dashboard
[group('app')]
app-build: app-deps
    cd app && npm run build

# Serve the dashboard against the deployed Worker, keyed from the keychain
[group('app')]
app-dev login="tslateman": app-build
    #!/usr/bin/env bash
    set -euo pipefail
    cd app
    if [ -e .dev.vars ]; then
      echo "app/.dev.vars exists. Remove it, or run 'just app-dev-local'." >&2
      exit 1
    fi
    if ! key=$(security find-generic-password -s spectrace-api-key -a "$USER" -w 2>/dev/null); then
      echo "No spectrace-api-key in the keychain. Run 'just secret-set'." >&2
      exit 1
    fi
    trap 'rm -f .dev.vars' EXIT
    umask 077
    printf 'SPECTRACE_API_KEY=%s\nSESSION_SECRET=%s\nDEV_LOGIN=%s\n' \
      "$key" "$(openssl rand -base64 32)" "{{login}}" > .dev.vars
    npm run dev

# Serve the dashboard and the Worker together against local D1
[group('app')]
app-dev-local port="8799" login="tslateman": app-build worker-deps dev-secrets
    #!/usr/bin/env bash
    set -euo pipefail
    cd app
    trap 'rm -f wrangler.local.jsonc' EXIT
    sed 's/, "remote": true//' wrangler.jsonc > wrangler.local.jsonc
    state=$PWD/.wrangler/state
    npx wrangler d1 migrations apply spectrace --local \
      -c ../worker/wrangler.toml --persist-to "$state"
    key=$(awk -F= '/^SPECTRACE_API_KEY=/{sub(/^SPECTRACE_API_KEY=/,"");print}' ../worker/.dev.vars)
    npx wrangler dev -c wrangler.local.jsonc -c ../worker/wrangler.toml \
      --port {{port}} --local --persist-to "$state" \
      --var "SPECTRACE_API_KEY:$key" --var "DEV_LOGIN:{{login}}" \
      --var "SESSION_SECRET:$(openssl rand -base64 32)"

# Deploy the dashboard
[group('app')]
deploy-app: app-deps
    cd app && npm run deploy

# --- Meta ---

# Regenerate the Unreleased section of CHANGELOG.md
[group('meta')]
changelog:
    {{python}} scripts/changelog.py update

# Push. CI owns CHANGELOG.md on main, so a branch carries no changelog commit
[group('meta')]
push *args:
    git push {{args}}

# Fail when a commit is missing from the Unreleased section
[group('meta')]
changelog-check:
    {{python}} scripts/changelog.py check

# Run the SpecTrace demo
[group('meta')]
demo:
    {{python}} scripts/demo.py

# List available demos
[group('meta')]
demos:
    {{python}} scripts/list_demos.py

# Remove caches and build artifacts
[group('meta')]
clean:
    rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
    find . -type d -name __pycache__ -not -path "./node_modules/*" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
