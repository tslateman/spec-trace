.PHONY: help venv install install-dev test lint format check migrate makemigrations shell run clean setup demo demos

# Use venv Python if it exists, otherwise fall back to system python
PYTHON := $(shell [ -f .venv/bin/python ] && echo .venv/bin/python || echo python)

help:
	@echo "Available targets:"
	@echo "  install         Install package in editable mode"
	@echo "  install-dev     Install with dev dependencies + git hooks"
	@echo "  test            Run tests with pytest"
	@echo "  migrate         Run Django migrations"
	@echo "  makemigrations  Create new migrations"
	@echo "  shell           Open Django shell"
	@echo "  run             Start development server"
	@echo "  clean           Remove caches and build artifacts"
	@echo "  setup           Create admin user (admin/admin)"
	@echo "  demo            Run the SpecTrace demo"
	@echo "  lint            Run ruff linter"
	@echo "  format          Check ruff formatting"
	@echo "  check           Run lint + format + test (matches CI)"
	@echo "  demos           List all available demos"

venv:
	@test -d .venv || uv venv

install: venv
	uv pip install -e ./spectrace-flows -e .

install-dev: venv
	uv pip install -e ./spectrace-flows -e ".[dev]"
	git config core.hooksPath .githooks

test:
	$(PYTHON) -m pytest -m "not demo"

lint:
	ruff check spectrace/ tests/ spectrace-flows/

format:
	ruff format --check spectrace/ tests/ spectrace-flows/

check: lint format test

migrate:
	$(PYTHON) spectrace/manage.py migrate

makemigrations:
	$(PYTHON) spectrace/manage.py makemigrations

shell:
	$(PYTHON) spectrace/manage.py shell

run:
	$(PYTHON) spectrace/manage.py runserver

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

setup:
	$(PYTHON) scripts/setup.py

demo:
	$(PYTHON) scripts/demo.py

demos:
	$(PYTHON) scripts/list_demos.py
