.PHONY: help install install-dev test migrate makemigrations shell run clean setup

help:
	@echo "Available targets:"
	@echo "  install         Install package in editable mode"
	@echo "  install-dev     Install with dev dependencies"
	@echo "  test            Run tests with pytest"
	@echo "  migrate         Run Django migrations"
	@echo "  makemigrations  Create new migrations"
	@echo "  shell           Open Django shell"
	@echo "  run             Start development server"
	@echo "  clean           Remove caches and build artifacts"
	@echo "  setup           Create admin user (admin/admin)"

install:
	uv pip install -e .

install-dev:
	uv pip install -e ".[dev]"

test:
	pytest

migrate:
	python spectrace/manage.py migrate

makemigrations:
	python spectrace/manage.py makemigrations

shell:
	python spectrace/manage.py shell

run:
	python spectrace/manage.py runserver

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

setup:
	python scripts/setup.py
