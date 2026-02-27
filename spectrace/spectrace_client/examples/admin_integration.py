"""Django admin integration example.

This module demonstrates how to add "Test Connection" buttons to Django admin
for on-demand validation testing. Engineers can click a button in the admin UI
to immediately test an integration and see the results in SpecTrace.

Usage:
    # In your admin.py file:
    from spectrace_client.examples.admin_integration import create_pms_test_action
    from spectrace_client.examples.pms import validate_opera_pms

    @admin.register(Hotel)
    class HotelAdmin(admin.ModelAdmin):
        list_display = ['name', 'pms_vendor', 'last_validated']
        actions = [create_pms_test_action(validate_opera_pms)]
"""

from typing import Any, Callable

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from spectrace_client import ValidationStatus


def create_pms_test_action(
    validate_func: Callable[[int, dict | None], Any],
) -> Callable:
    """Create a Django admin action for testing PMS connections.

    Args:
        validate_func: Validation function that takes (hotel_id, feature_flags)

    Returns:
        Admin action function that can be added to ModelAdmin.actions

    Example:
        @admin.register(Hotel)
        class HotelAdmin(admin.ModelAdmin):
            actions = [
                create_pms_test_action(validate_opera_pms),
                create_pms_test_action(validate_mews_pms),
            ]
    """

    def test_connection_action(
        modeladmin: admin.ModelAdmin, request: HttpRequest, queryset: QuerySet
    ) -> None:
        """Test PMS connection for selected hotels."""
        success_count = 0
        failure_count = 0

        for hotel in queryset:
            # Get feature flags from hotel settings if available
            feature_flags = getattr(hotel, "feature_flags", {})

            try:
                result = validate_func(hotel.id, feature_flags)

                if result.status == ValidationStatus.SUCCESS:
                    success_count += 1
                    modeladmin.message_user(
                        request,
                        f"✅ {hotel.name}: Connection test PASSED",
                        messages.SUCCESS,
                    )
                elif result.status == ValidationStatus.DEGRADED:
                    modeladmin.message_user(
                        request,
                        f"⚠️ {hotel.name}: Connection test DEGRADED - {result.message}",
                        messages.WARNING,
                    )
                else:
                    failure_count += 1
                    modeladmin.message_user(
                        request,
                        f"❌ {hotel.name}: Connection test FAILED - {result.message}",
                        messages.ERROR,
                    )
            except Exception as e:
                failure_count += 1
                modeladmin.message_user(
                    request,
                    f"❌ {hotel.name}: Validation error - {str(e)}",
                    messages.ERROR,
                )

        # Summary message
        if success_count > 0:
            modeladmin.message_user(
                request,
                f"Tested {queryset.count()} hotel(s): {success_count} passed, {failure_count} failed",
                messages.INFO,
            )

    test_connection_action.short_description = f"Test {validate_func.__name__.replace('validate_', '').replace('_', ' ').title()} Connection"
    return test_connection_action


def create_mobile_key_test_action(
    validate_func: Callable[[int, dict | None], Any],
) -> Callable:
    """Create a Django admin action for testing mobile key connections.

    Args:
        validate_func: Validation function that takes (hotel_id, feature_flags)

    Returns:
        Admin action function that can be added to ModelAdmin.actions

    Example:
        @admin.register(Hotel)
        class HotelAdmin(admin.ModelAdmin):
            actions = [
                create_mobile_key_test_action(validate_ambiance_mobile_key),
                create_mobile_key_test_action(validate_openkey_mobile_key),
            ]
    """

    def test_mobile_key_action(
        modeladmin: admin.ModelAdmin, request: HttpRequest, queryset: QuerySet
    ) -> None:
        """Test mobile key connection for selected hotels."""
        success_count = 0
        failure_count = 0

        for hotel in queryset:
            feature_flags = getattr(hotel, "feature_flags", {})

            try:
                result = validate_func(hotel.id, feature_flags)

                if result.status == ValidationStatus.SUCCESS:
                    success_count += 1
                    modeladmin.message_user(
                        request,
                        f"✅ {hotel.name}: Mobile key test PASSED",
                        messages.SUCCESS,
                    )
                elif result.status == ValidationStatus.DEGRADED:
                    modeladmin.message_user(
                        request,
                        f"⚠️ {hotel.name}: Mobile key test DEGRADED - {result.message}",
                        messages.WARNING,
                    )
                else:
                    failure_count += 1
                    modeladmin.message_user(
                        request,
                        f"❌ {hotel.name}: Mobile key test FAILED - {result.message}",
                        messages.ERROR,
                    )
            except Exception as e:
                failure_count += 1
                modeladmin.message_user(
                    request,
                    f"❌ {hotel.name}: Validation error - {str(e)}",
                    messages.ERROR,
                )

        # Summary message
        if success_count + failure_count > 0:
            modeladmin.message_user(
                request,
                f"Tested {queryset.count()} hotel(s): {success_count} passed, {failure_count} failed",
                messages.INFO,
            )

    test_mobile_key_action.short_description = (
        f"Test {validate_func.__name__.replace('validate_', '').replace('_', ' ').title()}"
    )
    return test_mobile_key_action


# Example: Complete HotelAdmin integration
"""
# In your app's admin.py:

from django.contrib import admin
from spectrace_client.examples.admin_integration import (
    create_pms_test_action,
    create_mobile_key_test_action,
)
from spectrace_client.examples.pms import validate_opera_pms, validate_mews_pms
from spectrace_client.examples.mobile_key import (
    validate_ambiance_mobile_key,
    validate_openkey_mobile_key,
)
from .models import Hotel


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ['name', 'pms_vendor', 'mobile_key_vendor', 'last_validated']
    list_filter = ['pms_vendor', 'mobile_key_vendor']
    search_fields = ['name', 'code']

    # Add "Test Connection" actions
    actions = [
        create_pms_test_action(validate_opera_pms),
        create_pms_test_action(validate_mews_pms),
        create_mobile_key_test_action(validate_ambiance_mobile_key),
        create_mobile_key_test_action(validate_openkey_mobile_key),
    ]

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'code', 'address')
        }),
        ('PMS Integration', {
            'fields': ('pms_vendor', 'pms_config', 'last_pms_validation')
        }),
        ('Mobile Key Integration', {
            'fields': ('mobile_key_vendor', 'mobile_key_config', 'last_mobile_key_validation')
        }),
        ('Feature Flags', {
            'fields': ('feature_flags',),
            'classes': ('collapse',),
            'description': 'Feature flags tracked in SpecTrace validations'
        }),
    )


# Now admins can:
# 1. Go to /admin/hotels/hotel/
# 2. Select one or more hotels
# 3. Choose "Test Opera PMS Connection" from actions dropdown
# 4. Click "Go"
# 5. See immediate validation results in admin messages
# 6. Check detailed step-by-step results in SpecTrace dashboard
"""
