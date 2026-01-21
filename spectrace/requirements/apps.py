"""Requirements app configuration."""
from django.apps import AppConfig


class RequirementsConfig(AppConfig):
    """Configuration for the requirements app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'requirements'
    verbose_name = 'Requirements'
