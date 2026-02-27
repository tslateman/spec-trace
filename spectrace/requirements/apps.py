"""Requirements app configuration."""

import sys

from django.apps import AppConfig


class RequirementsConfig(AppConfig):
    """Configuration for the requirements app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "requirements"
    verbose_name = "Requirements"

    def ready(self):
        """Called when Django app is ready.

        Syncs verification flow definitions from code to database.
        This runs on every startup to ensure flows are up to date.

        We skip sync during certain management commands where the
        database might not be ready (makemigrations, migrate).
        """
        # Skip sync during database-affecting management commands
        skip_commands = {"makemigrations", "migrate", "flush", "sqlmigrate"}
        if any(cmd in sys.argv for cmd in skip_commands):
            return

        # Import here to avoid circular imports
        from requirements.flows.sync import sync_flows_safe

        # Sync flows to database (safe version handles DB errors gracefully)
        sync_flows_safe()
