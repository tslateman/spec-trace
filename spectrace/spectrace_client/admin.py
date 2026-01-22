"""Django admin helpers for adding validation actions."""
from typing import Any, Callable

from django.contrib import admin, messages
from django.http import HttpRequest

from .models import ValidationResult


def create_validation_action(
    validation_func: Callable[[Any], ValidationResult],
    short_description: str,
) -> Callable:
    """Create a Django admin action that runs a validation function.
    
    Usage in admin.py:
        from spectrace_client import create_validation_action
        
        def verify_hotel_pms(hotel):
            # ... validation logic ...
            return validation_result
        
        class HotelAdmin(admin.ModelAdmin):
            actions = [
                create_validation_action(
                    verify_hotel_pms,
                    "Validate PMS Connection"
                )
            ]
    
    Args:
        validation_func: Function that takes a model instance and returns ValidationResult
        short_description: Text to display in admin action dropdown
    
    Returns:
        Admin action function that can be added to ModelAdmin.actions
    """
    def action(modeladmin: admin.ModelAdmin, request: HttpRequest, queryset):
        """Admin action that runs validation on selected objects."""
        success_count = 0
        failure_count = 0
        error_count = 0
        
        for obj in queryset:
            try:
                result = validation_func(obj)
                
                # Count by status
                if result.overall_status.value == 'success':
                    success_count += 1
                elif result.overall_status.value in ('failure', 'degraded'):
                    failure_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                modeladmin.message_user(
                    request,
                    f"Error validating {obj}: {e}",
                    level=messages.ERROR
                )
        
        # Show summary message
        total = queryset.count()
        msg_parts = []
        if success_count:
            msg_parts.append(f"{success_count} passed")
        if failure_count:
            msg_parts.append(f"{failure_count} failed")
        if error_count:
            msg_parts.append(f"{error_count} errors")
        
        summary = f"Validated {total} items: {', '.join(msg_parts)}"
        
        # Choose message level based on results
        if error_count > 0 or failure_count > 0:
            level = messages.WARNING
        else:
            level = messages.SUCCESS
        
        modeladmin.message_user(request, summary, level=level)
    
    action.short_description = short_description  # type: ignore[attr-defined]
    return action
