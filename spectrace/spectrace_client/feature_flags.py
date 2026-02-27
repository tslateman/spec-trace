"""Feature flag extraction and tracking utilities.

This module provides helpers for extracting feature flags from various sources
(Django settings, environment variables, database models) and tracking them in
SpecTrace validations for correlation analysis.

Usage:
    from spectrace_client.feature_flags import (
        extract_feature_flags,
        get_django_feature_flags,
        get_env_feature_flags,
    )

    # Auto-extract from multiple sources
    flags = extract_feature_flags(
        django_prefix='FEATURE_',
        env_prefix='FF_',
        model_instance=hotel,
        model_field='feature_flags'
    )

    # Use in validation
    with ValidationRun(..., context={'feature_flags': flags}) as run:
        ...
"""

import os
from typing import Any

from django.conf import settings


def extract_feature_flags(
    django_prefix: str = "FEATURE_",
    env_prefix: str = "FF_",
    model_instance: Any | None = None,
    model_field: str = "feature_flags",
    include_django: bool = True,
    include_env: bool = True,
    include_model: bool = True,
) -> dict[str, bool]:
    """Extract feature flags from multiple sources and merge them.

    Args:
        django_prefix: Prefix for Django settings (e.g., 'FEATURE_')
        env_prefix: Prefix for environment variables (e.g., 'FF_')
        model_instance: Django model instance with feature flags
        model_field: Field name on model containing flags dict
        include_django: Whether to extract from Django settings
        include_env: Whether to extract from environment variables
        include_model: Whether to extract from model instance

    Returns:
        Merged dict of feature flags with precedence: model > env > django

    Example:
        # Django settings.py:
        FEATURE_NEW_AUTH = True
        FEATURE_LEGACY_MODE = False

        # Environment:
        FF_NEW_AUTH=false
        FF_DEBUG_MODE=true

        # Hotel model:
        hotel.feature_flags = {'new_auth': True, 'beta_features': True}

        # Extract:
        flags = extract_feature_flags(
            django_prefix='FEATURE_',
            env_prefix='FF_',
            model_instance=hotel
        )
        # Result: {
        #     'new_auth': True,           # From model (highest precedence)
        #     'legacy_mode': False,       # From Django settings
        #     'debug_mode': True,         # From env
        #     'beta_features': True       # From model
        # }
    """
    merged_flags = {}

    # 1. Django settings (lowest precedence)
    if include_django:
        merged_flags.update(get_django_feature_flags(prefix=django_prefix))

    # 2. Environment variables (medium precedence)
    if include_env:
        merged_flags.update(get_env_feature_flags(prefix=env_prefix))

    # 3. Model instance (highest precedence)
    if include_model and model_instance:
        merged_flags.update(get_model_feature_flags(model_instance, field=model_field))

    return merged_flags


def get_django_feature_flags(prefix: str = "FEATURE_") -> dict[str, bool]:
    """Extract feature flags from Django settings.

    Args:
        prefix: Setting name prefix (e.g., 'FEATURE_')

    Returns:
        Dict mapping flag names to boolean values

    Example:
        # In settings.py:
        FEATURE_NEW_AUTH = True
        FEATURE_LEGACY_MODE = False
        FEATURE_BETA_ACCESS = True

        # Extract:
        flags = get_django_feature_flags(prefix='FEATURE_')
        # Result: {
        #     'new_auth': True,
        #     'legacy_mode': False,
        #     'beta_access': True
        # }
    """
    flags = {}

    for setting_name in dir(settings):
        if setting_name.startswith(prefix):
            value = getattr(settings, setting_name)

            # Only include boolean values
            if isinstance(value, bool):
                # Convert FEATURE_NEW_AUTH -> new_auth
                flag_name = setting_name[len(prefix) :].lower()
                flags[flag_name] = value

    return flags


def get_env_feature_flags(prefix: str = "FF_") -> dict[str, bool]:
    """Extract feature flags from environment variables.

    Args:
        prefix: Environment variable prefix (e.g., 'FF_')

    Returns:
        Dict mapping flag names to boolean values

    Example:
        # In environment:
        FF_NEW_AUTH=true
        FF_LEGACY_MODE=false
        FF_DEBUG_MODE=1
        FF_BETA=0

        # Extract:
        flags = get_env_feature_flags(prefix='FF_')
        # Result: {
        #     'new_auth': True,
        #     'legacy_mode': False,
        #     'debug_mode': True,
        #     'beta': False
        # }
    """
    flags = {}

    for env_var, value in os.environ.items():
        if env_var.startswith(prefix):
            # Convert FF_NEW_AUTH -> new_auth
            flag_name = env_var[len(prefix) :].lower()

            # Parse boolean value (true/false, 1/0, yes/no)
            flags[flag_name] = _parse_bool(value)

    return flags


def get_model_feature_flags(instance: Any, field: str = "feature_flags") -> dict[str, bool]:
    """Extract feature flags from a Django model instance.

    Args:
        instance: Django model instance
        field: Field name containing feature flags (usually JSONField)

    Returns:
        Dict mapping flag names to boolean values

    Example:
        # Model:
        class Hotel(models.Model):
            feature_flags = models.JSONField(default=dict, blank=True)

        # Instance:
        hotel = Hotel.objects.get(id=123)
        hotel.feature_flags = {'new_auth': True, 'beta_features': False}

        # Extract:
        flags = get_model_feature_flags(hotel, field='feature_flags')
        # Result: {'new_auth': True, 'beta_features': False}
    """
    flags_value = getattr(instance, field, {})

    if not isinstance(flags_value, dict):
        return {}

    # Filter to only boolean values
    return {k: v for k, v in flags_value.items() if isinstance(v, bool)}


def _parse_bool(value: str) -> bool:
    """Parse string value to boolean.

    Args:
        value: String value like 'true', '1', 'yes', 'false', '0', 'no'

    Returns:
        Boolean value
    """
    value_lower = value.lower().strip()

    if value_lower in ("true", "1", "yes", "on", "enabled"):
        return True
    elif value_lower in ("false", "0", "no", "off", "disabled"):
        return False
    else:
        # Default to False for unknown values
        return False


# Convenience decorator for automatic feature flag tracking
def with_feature_flags(
    django_prefix: str = "FEATURE_",
    env_prefix: str = "FF_",
    model_param: str | None = None,
    model_field: str = "feature_flags",
):
    """Decorator to automatically extract and inject feature flags into context.

    Args:
        django_prefix: Prefix for Django settings
        env_prefix: Prefix for environment variables
        model_param: Parameter name containing model instance (e.g., 'hotel')
        model_field: Field name on model containing flags

    Example:
        from spectrace_client.feature_flags import with_feature_flags
        from spectrace_client import ValidationRun

        @with_feature_flags(model_param='hotel')
        def validate_pms_connection(hotel_id: int, hotel=None, feature_flags=None):
            with ValidationRun(
                requirement_id='REQ-PMS-001',
                name=f'PMS Connection - Hotel {hotel_id}',
                context={'feature_flags': feature_flags}  # Auto-injected!
            ) as run:
                # ... validation logic
                return run.finalize()
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract feature flags
            model_instance = kwargs.get(model_param) if model_param else None

            extracted_flags = extract_feature_flags(
                django_prefix=django_prefix,
                env_prefix=env_prefix,
                model_instance=model_instance,
                model_field=model_field,
            )

            # Inject into kwargs if not already provided
            if "feature_flags" not in kwargs or kwargs["feature_flags"] is None:
                kwargs["feature_flags"] = extracted_flags
            else:
                # Merge with provided flags (provided flags take precedence)
                kwargs["feature_flags"] = {**extracted_flags, **kwargs["feature_flags"]}

            return func(*args, **kwargs)

        return wrapper

    return decorator
