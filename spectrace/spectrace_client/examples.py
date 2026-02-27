"""Example usage of SpecTrace In-App Validation SDK.

This file demonstrates how to use the SDK to create validation functions
for PMS integrations, mobile key systems, and other configurations.
"""

from spectrace_client import ValidationRun, verify_requirement


# Example 1: Simple validation with decorator (5 lines!)
@verify_requirement("REQ-PMS-OPERA-001", name="Opera PMS Connection")
def verify_opera_connection(hotel, validation_run: ValidationRun):
    """Validate Opera PMS integration for a hotel."""
    config = hotel.pms_config

    # Step 1: Configuration check
    if not config or not config.get("opera_url"):
        validation_run.step("config", passed=False, error_message="Opera URL not configured")
        return validation_run.result

    validation_run.step("config", passed=True, details=f"URL: {config['opera_url']}")

    # Step 2: Authentication
    try:
        # opera_client.login(config)
        validation_run.step("auth", passed=True, details="Login successful")
    except Exception as e:
        validation_run.step("auth", passed=False, error_message=f"Login failed: {e}")
        return validation_run.result

    # Step 3: Connectivity
    try:
        # opera_client.ping()
        validation_run.step("connectivity", passed=True, details="PMS reachable")
    except Exception as e:
        validation_run.step("connectivity", passed=False, error_message=f"Ping failed: {e}")

    # Add context for debugging
    validation_run.context.update(
        {
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "vendor": "Opera",
            "pms_version": config.get("version", "unknown"),
        }
    )

    return validation_run.result


# Example 2: Mobile key validation
@verify_requirement("REQ-MOBILE-AMBIANCE-001", name="Ambiance Mobile Key")
def verify_ambiance_mobile_key(hotel, validation_run: ValidationRun):
    """Validate Ambiance mobile key integration."""
    config = hotel.mobile_key_config

    # Config check
    if not config or config.get("vendor") != "ambiance":
        validation_run.step("config", passed=False, error_message="Ambiance not configured")
        return validation_run.result

    validation_run.step("config", passed=True)

    # Auth check
    try:
        # ambiance_client.authenticate(config)
        validation_run.step("auth", passed=True, details="API key valid")
    except Exception as e:
        validation_run.step("auth", passed=False, error_message=str(e))
        return validation_run.result

    # Permissions check
    try:
        # ambiance_client.check_permissions()
        validation_run.step("permissions", passed=True, details="All permissions granted")
    except Exception as e:
        validation_run.step("permissions", passed=False, error_message=str(e))

    validation_run.context.update(
        {
            "hotel_id": hotel.id,
            "vendor": "Ambiance",
        }
    )

    return validation_run.result


# Example 3: Context extraction for better debugging
@verify_requirement(
    "REQ-PMS-MEWS-001",
    name="Mews PMS Connection",
    context_fn=lambda hotel: {
        "hotel_id": hotel.id,
        "hotel_name": hotel.name,
        "property_code": hotel.property_code,
        "vendor": "Mews",
    },
)
def verify_mews_connection(hotel, validation_run: ValidationRun):
    """Validate Mews PMS integration with automatic context extraction."""
    config = hotel.pms_config

    validation_run.step("config", passed=bool(config and config.get("mews_client_id")))

    if config and config.get("mews_client_id"):
        validation_run.step("auth", passed=True, details="OAuth configured")

    return validation_run.result


# Example 4: Django admin action (adds "Validate PMS" button to admin)
# Add to your HotelAdmin class:
#
# from django.contrib import admin
# from .models import Hotel
# from .validations import verify_opera_connection
#
# class HotelAdmin(admin.ModelAdmin):
#     list_display = ['name', 'property_code', 'pms_vendor']
#     actions = [
#         create_validation_action(verify_opera_connection, "Validate Opera PMS"),
#     ]
#
# admin.site.register(Hotel, HotelAdmin)


# Example 5: API endpoint usage
# from rest_framework.decorators import api_view
# from rest_framework.response import Response
#
# @api_view(['POST'])
# def validate_hotel_pms(request, hotel_id):
#     hotel = Hotel.objects.get(id=hotel_id)
#     result = verify_opera_connection(hotel)
#
#     return Response({
#         'requirement_id': result.requirement_id,
#         'status': result.status.value,
#         'message': result.message,
#         'steps': [step.to_dict() for step in result.steps],
#     })
