# SpecTrace In-App Validation SDK

Add "Test Connection" validation buttons with 5 lines of code. Validate real integration configurations (PMS, mobile key, feature flags) and report results to SpecTrace.

## Quick Start

```python
from spectrace_client import ValidationRun, ValidationStep
from datetime import datetime

# Test a PMS connection with 5-step validation
def validate_opera_pms(hotel_id: int):
    with ValidationRun(
        requirement_id="REQ-PMS-OPERA-001",
        name=f"Opera PMS Connection - Hotel {hotel_id}",
        context={'vendor': 'Opera', 'hotel_id': hotel_id}
    ) as run:
        # Step 1: Load config
        run.add_step(ValidationStep(
            name='load_config',
            passed=True,
            details='Config loaded',
            timestamp=datetime.now()
        ))
        
        # Step 2-5: Auth, connect, read, write...
        # (see examples/ for complete implementations)
        
        return run.finalize()
```

That's it! Results automatically appear in your SpecTrace dashboard with:
- ✅ **Per-step breakdown** (which step failed?)
- 📊 **Vendor grouping** (Opera vs Mews pass rates)
- 🚨 **Regression detection** (was it working yesterday?)
- 🎛️ **Feature flag correlation** (which flags affected this?)

## Installation

The SDK is bundled with SpecTrace - no separate installation needed.

```python
# Just import and use
from spectrace_client import ValidationRun, ValidationStatus
```

## Core Concepts

### ValidationRun Context Manager

The heart of the SDK. Handles submission, error handling, and best-effort delivery.

```python
with ValidationRun(
    requirement_id="REQ-XXX",      # Links to your spec
    name="Human readable name",
    context={                       # Optional metadata
        'vendor': 'Opera',
        'hotel_id': 123,
        'feature_flags': {'new_auth': True}
    }
) as run:
    # Add steps as you validate
    run.add_step(ValidationStep(...))
    
    # Automatically submits on exit
    return run.finalize()
```

### ValidationStep

Represents one check in a multi-step validation.

```python
ValidationStep(
    name='authenticate',           # Short identifier
    passed=True,                   # Did it pass?
    details='Auth successful',     # Success details
    error_message='Timeout',       # Failure details
    duration_ms=150,               # Optional timing
    timestamp=datetime.now()
)
```

### ValidationStatus

Overall status computed from steps:
- `SUCCESS`: All steps passed
- `DEGRADED`: Some steps passed, some failed
- `FAILURE`: All steps failed
- `ERROR`: Unexpected exception

## Integration Patterns

### 1. Django Admin "Test Connection" Button

```python
# In admin.py
from spectrace_client.examples.admin_integration import create_pms_test_action
from spectrace_client.examples.pms import validate_opera_pms

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    actions = [create_pms_test_action(validate_opera_pms)]
```

Now admins can:
1. Select hotels in admin
2. Choose "Test Opera PMS Connection"
3. See immediate results + detailed breakdown in SpecTrace

### 2. REST API Endpoint

```python
# In views.py
from spectrace_client.examples.pms import validate_opera_pms
from django.http import JsonResponse

def test_connection_api(request, hotel_id):
    result = validate_opera_pms(hotel_id)
    return JsonResponse({
        'status': result.status.value,
        'steps': [{'name': s.name, 'passed': s.passed} for s in result.steps]
    })
```

### 3. Automated Health Checks

```python
# In management command or celery task
from spectrace_client.examples.pms import validate_opera_pms

# Nightly validation of all active hotels
for hotel in Hotel.objects.filter(pms_active=True):
    validate_opera_pms(hotel.id)
```

## Feature Flag Tracking

Automatically track which feature flags were active during validations:

```python
from spectrace_client import extract_feature_flags

# Auto-extract from Django settings, env vars, and model
flags = extract_feature_flags(
    django_prefix='FEATURE_',
    env_prefix='FF_',
    model_instance=hotel,
    model_field='feature_flags'
)

# Use in validation
with ValidationRun(..., context={'feature_flags': flags}) as run:
    ...
```

Or use the decorator for automatic injection:

```python
from spectrace_client import with_feature_flags

@with_feature_flags(model_param='hotel')
def validate_pms(hotel_id, hotel=None, feature_flags=None):
    # feature_flags automatically populated!
    with ValidationRun(..., context={'feature_flags': feature_flags}) as run:
        ...
```

## Configuration

The SDK reads configuration from Django settings or environment variables:

```python
# In settings.py
SPECTRACE_URL = "http://localhost:8000"
SPECTRACE_API_KEY = "your-api-key"  # Optional

# Or via environment
SPECTRACE_URL=http://localhost:8000
SPECTRACE_API_KEY=your-api-key
```

## Examples

See `spectrace_client/examples/` for complete working examples:

- **pms.py**: Opera, Mews PMS validations (5-step pattern)
- **mobile_key.py**: Ambiance, OpenKey, Vostio validations (3-step pattern)
- **admin_integration.py**: Django admin "Test Connection" buttons
- **api_integration.py**: REST API endpoints for on-demand validation

## Error Handling

The SDK uses **best-effort submission** - your validation never breaks if SpecTrace is down:

```python
# Your code runs regardless of SpecTrace availability
with ValidationRun(...) as run:
    run.add_step(...)  # This always works
    return run.finalize()  # Submits if possible, silently fails if not
```

Errors are logged but never raised. Check logs for submission issues:

```
WARNING: Failed to submit validation: Connection refused
```

## Dashboard Features

Once you're submitting validations, the SpecTrace dashboard shows:

### Vendor Coverage View (`/admin/vendor-coverage/`)

- **Pass rates per vendor**: See which vendors are most reliable
- **Recent regressions**: Detect when integrations break
- **Feature flag analysis**: Correlate flags with failure rates

### In-App Validation Admin

- **Step-by-step breakdown**: See exactly which step failed
- **Historical results**: Track improvement/degradation over time
- **Context inspection**: Debug with full context (hotel ID, feature flags, etc.)

## API Reference

### ValidationRun

```python
ValidationRun(
    requirement_id: str,           # Required: Links to spec (e.g., "REQ-PMS-001")
    name: str,                     # Required: Human-readable name
    context: dict[str, Any] = {},  # Optional: Metadata (vendor, hotel_id, flags)
)

# Methods:
.add_step(step: ValidationStep)   # Add a validation step
.finalize() -> ValidationResult    # Complete and submit
```

### ValidationStep

```python
ValidationStep(
    name: str,                     # Required: Step identifier
    passed: bool,                  # Required: Pass/fail status
    details: str = "",             # Optional: Success details
    error_message: str = "",       # Optional: Failure details
    duration_ms: int | None = None, # Optional: Timing
    timestamp: datetime = now()    # Optional: When this step ran
)
```

### ValidationResult

```python
# Returned by run.finalize()
result = ValidationResult(
    requirement_id: str,
    name: str,
    status: ValidationStatus,      # SUCCESS, DEGRADED, FAILURE, ERROR
    steps: list[ValidationStep],
    message: str,
    context: dict[str, Any],
    timestamp: datetime,
)

# Properties:
result.overall_status              # Computed from steps
```

### Feature Flag Helpers

```python
# Extract from multiple sources
extract_feature_flags(
    django_prefix='FEATURE_',
    env_prefix='FF_',
    model_instance=hotel,
    model_field='feature_flags'
) -> dict[str, bool]

# Extract from specific sources
get_django_feature_flags(prefix='FEATURE_')
get_env_feature_flags(prefix='FF_')
get_model_feature_flags(instance, field='feature_flags')

# Decorator for automatic injection
@with_feature_flags(model_param='hotel')
def validate_pms(hotel_id, hotel=None, feature_flags=None):
    ...
```

## Best Practices

1. **Use descriptive step names**: `authenticate`, `test_connection`, `test_read_access`
2. **Include context**: Always add `vendor`, `hotel_id`, and `feature_flags` to context
3. **Test early and often**: Run validations on every config change
4. **Monitor regressions**: Use the vendor coverage dashboard to catch issues
5. **Track feature flags**: Correlate flags with validation failures

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues:

- Validations not appearing in dashboard
- Submission timeouts
- Feature flag extraction issues
- Step status computation

## Architecture

The SDK is a bundled Django app (`spectrace_client/`) inside SpecTrace:

```
spectrace/spectrace_client/
├── models.py           # ValidationResult, ValidationStep, ValidationStatus
├── client.py           # ValidationClient (HTTP submission)
├── context.py          # ValidationRun context manager
├── decorators.py       # @verify_requirement decorator
├── feature_flags.py    # Feature flag extraction helpers
├── admin.py            # create_validation_action helper
├── exceptions.py       # SpecTraceAPIError, ValidationConfigError
├── examples/           # Working examples
│   ├── pms.py
│   ├── mobile_key.py
│   ├── admin_integration.py
│   └── api_integration.py
└── docs/               # Documentation
    ├── INTEGRATION_GUIDE.md
    └── TROUBLESHOOTING.md
```

## Requirements

- **Python**: 3.12+
- **Django**: 5.2+
- **Dependencies**: None (uses stdlib + Django)

## Version History

### v0.1.0 (2026-01-22)
- Initial release
- ValidationRun context manager
- Multi-step validation support
- Vendor tracking
- Feature flag correlation
- Regression detection
- Django admin integration
- REST API examples

## Support

- **Documentation**: `spectrace_client/docs/`
- **Examples**: `spectrace_client/examples/`
- **Issues**: File issues in SpecTrace repository

## License

Same as SpecTrace (project license applies)
