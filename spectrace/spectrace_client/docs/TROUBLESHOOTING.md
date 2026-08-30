# Troubleshooting Guide

Common issues and solutions when using the SpecTrace SDK.

## Table of Contents

1. [Validations Not Appearing in Dashboard](#validations-not-appearing-in-dashboard)
2. [Submission Timeouts](#submission-timeouts)
3. [Feature Flag Extraction Issues](#feature-flag-extraction-issues)
4. [Step Status Computation](#step-status-computation)
5. [Django Admin Integration Issues](#django-admin-integration-issues)
6. [API Endpoint Issues](#api-endpoint-issues)

---

## Validations Not Appearing in Dashboard

### Symptom

You run a validation, but it doesn't appear in `/admin/requirements/inappvalidation/`.

### Possible Causes & Solutions

#### 1. SpecTrace URL Not Configured

**Check:**

```python
from spectrace_client import ValidationClient
client = ValidationClient()
print(client.spectrace_url)
```

**Fix:**

```python
# In settings.py
SPECTRACE_URL = "http://localhost:8000"

# Or via environment
export SPECTRACE_URL=http://localhost:8000
```

#### 2. Requirement Doesn't Exist

The SDK submits validations, but they're ignored if the requirement ID doesn't exist.

**Check:**

```python
from requirements.models import Requirement
Requirement.objects.filter(external_id='REQ-PMS-001').exists()
# Should return True
```

**Fix:**
Create the requirement first:

```python
Requirement.add_root(
    external_id='REQ-PMS-001',
    title='Opera PMS Connection',
    description='Test Opera PMS integration'
)
```

#### 3. Network Issues

**Check logs:**

```bash
tail -f /var/log/django/app.log | grep "spectrace_client"
```

Look for:

```
WARNING: Failed to submit validation: Connection refused
```

**Fix:**

- Ensure SpecTrace dashboard is running
- Check firewall rules
- Verify URL is correct (http vs https)

#### 4. Silent Submission Failure

The SDK uses best-effort submission and logs errors without raising exceptions.

**Enable debug logging:**

```python
# In settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
        },
    },
    'loggers': {
        'spectrace_client': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

---

## Submission Timeouts

### Symptom

Validations take a long time or hang when submitting.

### Possible Causes & Solutions

#### 1. Default Timeout Too Long

The SDK uses a 5-second timeout by default.

**Fix: Adjust timeout**

```python
from spectrace_client.client import ValidationClient

# Create custom client with shorter timeout
client = ValidationClient()
client.timeout = 2  # 2 seconds

# Use in ValidationRun
with ValidationRun(...) as run:
    run.client = client  # Override default client
    ...
```

#### 2. SpecTrace Dashboard Slow

If the dashboard is slow to respond, validations will queue up.

**Fix: Use async submission (recommended for production)**

```python
from celery import shared_task
from myapp.validations import validate_opera_pms

@shared_task
def validate_opera_pms_async(hotel_id, feature_flags=None):
    return validate_opera_pms(hotel_id, feature_flags)

# Usage
validate_opera_pms_async.delay(hotel_id=123)
```

#### 3. Large Payload

If you're sending many steps or large context dicts, the payload may be slow to serialize/send.

**Fix: Reduce context size**

```python
# Bad: Sending entire config object
context = {'config': hotel.pms_config}  # May be huge

# Good: Send only relevant fields
context = {
    'vendor': 'Opera',
    'hotel_id': hotel.id,
    'endpoint': hotel.pms_config.get('endpoint')
}
```

---

## Feature Flag Extraction Issues

### Symptom

Feature flags aren't showing up in dashboard or extraction returns empty dict.

### Possible Causes & Solutions

#### 1. Wrong Prefix

**Check:**

```python
from spectrace_client import get_django_feature_flags

flags = get_django_feature_flags(prefix='FEATURE_')
print(flags)  # Should show your flags
```

**Fix: Match your settings prefix**

```python
# If your settings use FF_ prefix:
FEATURE_NEW_AUTH = True  # Won't work

FF_NEW_AUTH = True  # Will work with prefix='FF_'
```

#### 2. Non-Boolean Values

The SDK only extracts boolean flags. Strings, ints, etc. are ignored.

**Check:**

```python
# In settings.py
FEATURE_NEW_AUTH = "enabled"  # Won't work (string)
FEATURE_NEW_AUTH = 1  # Won't work (int)
FEATURE_NEW_AUTH = True  # Will work (bool)
```

#### 3. Model Field Doesn't Exist

**Check:**

```python
hotel = Hotel.objects.get(id=123)
hasattr(hotel, 'feature_flags')  # Should be True
```

**Fix: Add field to model**

```python
class Hotel(models.Model):
    feature_flags = models.JSONField(default=dict, blank=True)
```

Don't forget to run migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

#### 4. Environment Variables Not Parsed

**Check:**

```python
import os
print(os.environ.get('FF_NEW_AUTH'))  # Should show 'true' or '1'
```

**Fix: Set correctly**

```bash
# These work
export FF_NEW_AUTH=true
export FF_NEW_AUTH=1
export FF_NEW_AUTH=yes

# These don't work
export FF_NEW_AUTH=True  # Capital T won't parse as boolean
export FF_NEW_AUTH="true"  # Quotes are fine
```

---

## Step Status Computation

### Symptom

Overall status is incorrect (e.g., showing SUCCESS when steps failed).

### How Status is Computed

```python
# From ValidationResult.overall_status
if not self.steps:
    return self.status  # Use explicit status if no steps

passed = sum(1 for s in self.steps if s.passed)
failed = len(self.steps) - passed

if failed == 0:
    return ValidationStatus.SUCCESS
elif passed > 0:
    return ValidationStatus.DEGRADED  # Mixed results
else:
    return ValidationStatus.FAILURE  # All failed
```

### Common Issues

#### 1. Forgetting to Set `passed=True/False`

**Bad:**

```python
step = ValidationStep(name='auth')  # Missing passed!
```

**Good:**

```python
step = ValidationStep(name='auth', passed=True)
```

#### 2. Using `status` Instead of Relying on Steps

The `ValidationRun` will compute status from steps. Don't override it unless you have no steps.

**Bad:**

```python
with ValidationRun(...) as run:
    run.add_step(ValidationStep(name='auth', passed=False))
    # Status will be computed as FAILURE, don't manually set it
```

**Good:**

```python
with ValidationRun(...) as run:
    run.add_step(ValidationStep(name='auth', passed=False))
    return run.finalize()  # Status computed automatically
```

---

## Django Admin Integration Issues

### Symptom

Admin action doesn't appear or throws errors.

### Possible Causes & Solutions

#### 1. Action Not Added to `actions` List

**Check:**

```python
@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    actions = [...]  # Is your action here?
```

**Fix:**

```python
from spectrace_client.examples.admin_integration import create_pms_test_action
from myapp.validations import validate_opera_pms

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    actions = [create_pms_test_action(validate_opera_pms)]
```

#### 2. Wrong Function Signature

Your validation function must accept `(hotel_id, feature_flags=None)`.

**Bad:**

```python
def validate_opera_pms(hotel):  # Wrong signature
    ...
```

**Good:**

```python
def validate_opera_pms(hotel_id: int, feature_flags: dict | None = None):
    ...
```

#### 3. Model Doesn't Have `id` Attribute

The admin action calls `hotel.id` to get the ID.

**Check:**

```python
hotel = Hotel.objects.first()
print(hotel.id)  # Should work
```

#### 4. Messages Not Showing

Ensure you're using `modeladmin.message_user()` in your action.

**Check:**
The `create_pms_test_action()` helper already does this. If you're writing custom actions:

```python
def my_action(modeladmin, request, queryset):
    modeladmin.message_user(request, "Test passed!", messages.SUCCESS)
```

---

## API Endpoint Issues

### Symptom

API returns 500 errors or validations don't run.

### Possible Causes & Solutions

#### 1. CSRF Token Missing

**Check error:**

```
403 Forbidden: CSRF verification failed
```

**Fix: Exempt endpoint**

```python
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@require_http_methods(["POST"])
def test_connection_api(request, hotel_id):
    ...
```

Or send CSRF token from frontend:

```javascript
fetch('/api/test/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({...})
})
```

#### 2. JSON Parsing Error

**Check error:**

```
JSONDecodeError: Expecting value
```

**Fix: Ensure body is valid JSON**

```python
import json

body = json.loads(request.body) if request.body else {}
```

#### 3. Hotel Not Found

**Check:**

```python
Hotel.objects.filter(id=hotel_id).exists()
```

**Fix: Return 404**

```python
from django.shortcuts import get_object_or_404

def test_connection_api(request, hotel_id):
    hotel = get_object_or_404(Hotel, id=hotel_id)
    ...
```

#### 4. Validation Function Raises Exception

**Check logs:**

```bash
tail -f /var/log/django/app.log | grep "ERROR"
```

**Fix: Add try/catch in view**

```python
try:
    result = validate_opera_pms(hotel_id)
    return JsonResponse({'success': True, ...})
except Exception as e:
    return JsonResponse({'success': False, 'error': str(e)}, status=500)
```

---

## General Debugging Tips

### 1. Enable Verbose Logging

```python
# In settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'level': 'DEBUG'},
    },
    'loggers': {
        'spectrace_client': {'handlers': ['console'], 'level': 'DEBUG'},
        'django.request': {'handlers': ['console'], 'level': 'DEBUG'},
    },
}
```

### 2. Test in Django Shell

```python
python manage.py shell

>>> from myapp.validations import validate_opera_pms
>>> result = validate_opera_pms(hotel_id=123)
>>> print(result.status)
>>> for step in result.steps:
...     print(f"{step.name}: {step.passed}")
```

### 3. Check SpecTrace Dashboard Directly

Create a validation manually to ensure the system is working:

```python
from requirements.models import Requirement, InAppValidation, InAppValidationResult, InAppValidationRun, InAppValidationStatus
from django.utils import timezone

req = Requirement.objects.get(external_id='REQ-PMS-001')
validation = InAppValidation.objects.create(
    requirement=req,
    name='Manual Test',
    vendor='Opera'
)
run = InAppValidationRun.objects.create(source='manual')
InAppValidationResult.objects.create(
    validation_run=run,
    validation=validation,
    status=InAppValidationStatus.SUCCESS,
    message='Manual test',
    checked_at=timezone.now()
)
```

Then check `/admin/requirements/inappvalidation/` to see if it appears.

### 4. Verify SDK Version

```python
import spectrace_client
print(spectrace_client.__version__)  # Should be 0.1.0 or later
```

---

## Still Having Issues?

1. Check SDK tests are passing: `pytest spectrace/spectrace_client/tests.py -v`
2. Review examples in `spectrace_client/examples/`
3. File an issue in the SpecTrace repository with:
   - Error message and full traceback
   - Relevant code snippet
   - Django version and Python version
   - SpecTrace version

## Quick Reference

### Common Commands

```bash
# Test validation function
python manage.py shell -c "from myapp.validations import validate_opera_pms; print(validate_opera_pms(123).status)"

# Check SpecTrace URL
python manage.py shell -c "from spectrace_client import ValidationClient; print(ValidationClient().spectrace_url)"

# Check feature flags
python manage.py shell -c "from spectrace_client import extract_feature_flags; print(extract_feature_flags())"

# View recent validations
python manage.py shell -c "from requirements.models import InAppValidation; print(InAppValidation.objects.count())"
```

### Useful Dashboard URLs

- Validation list: `/admin/requirements/inappvalidation/`
- Vendor coverage: `/admin/vendor-coverage/`
- API submit endpoint: `/api/v1/results/enforcement/`

### Log Locations

- Development: Console output
- Production: `/var/log/django/app.log` (or your configured log path)
