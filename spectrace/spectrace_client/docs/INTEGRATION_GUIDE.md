# Integration Guide

Step-by-step guide to integrating SpecTrace SDK into your Django application.

## Table of Contents

1. [Setup](#setup)
2. [Basic Integration](#basic-integration)
3. [Django Admin Integration](#django-admin-integration)
4. [REST API Integration](#rest-api-integration)
5. [Feature Flag Tracking](#feature-flag-tracking)
6. [Production Deployment](#production-deployment)

---

## Setup

### 1. Verify SDK is Available

The SDK is bundled with SpecTrace. Verify it's available:

```python
# In Django shell:
python manage.py shell

>>> from spectrace_client import ValidationRun
>>> ValidationRun.__doc__
```

### 2. Configure SpecTrace Connection

Add to your `settings.py`:

```python
# SpecTrace SDK configuration
SPECTRACE_URL = "http://localhost:8000"  # SpecTrace dashboard URL
SPECTRACE_API_KEY = None  # Optional: Add if you enable auth later
```

For production, use environment variables:

```bash
export SPECTRACE_URL=https://spectrace.yourcompany.com
export SPECTRACE_API_KEY=your-secret-key
```

### 3. Verify Connection

Test the connection:

```python
from spectrace_client import ValidationClient

client = ValidationClient()
print(f"SDK will submit to: {client.spectrace_url}")
```

---

## Basic Integration

### Example: Validate PMS Connection

Let's add a validation for Opera PMS integration.

**Step 1: Create validation function**

Create `myapp/validations.py`:

```python
from spectrace_client import ValidationRun, ValidationStep
from datetime import datetime
from .models import Hotel

def validate_opera_pms(hotel_id: int, feature_flags: dict | None = None):
    """Validate Opera PMS connection for a hotel."""
    feature_flags = feature_flags or {}
    
    with ValidationRun(
        requirement_id="REQ-PMS-OPERA-001",
        name=f"Opera PMS Connection - Hotel {hotel_id}",
        context={
            'vendor': 'Opera',
            'hotel_id': hotel_id,
            'feature_flags': feature_flags
        }
    ) as run:
        # Step 1: Load configuration
        step_config = ValidationStep(
            name='load_config',
            passed=False,
            timestamp=datetime.now()
        )
        
        try:
            hotel = Hotel.objects.get(id=hotel_id)
            pms_config = hotel.pms_config
            step_config.passed = True
            step_config.details = f"Loaded config for {pms_config['endpoint']}"
        except Exception as e:
            step_config.error_message = str(e)
            run.add_step(step_config)
            return run.finalize()
        
        run.add_step(step_config)
        
        # Step 2: Authenticate
        step_auth = ValidationStep(
            name='authenticate',
            passed=False,
            timestamp=datetime.now()
        )
        
        try:
            import requests
            response = requests.post(
                f"{pms_config['endpoint']}/auth",
                json={
                    'client_id': pms_config['client_id'],
                    'client_secret': pms_config['client_secret']
                },
                timeout=5
            )
            response.raise_for_status()
            auth_token = response.json()['access_token']
            
            step_auth.passed = True
            step_auth.details = "Authentication successful"
        except Exception as e:
            step_auth.error_message = str(e)
            run.add_step(step_auth)
            return run.finalize()
        
        run.add_step(step_auth)
        
        # Step 3: Test connection
        step_connect = ValidationStep(
            name='test_connection',
            passed=False,
            timestamp=datetime.now()
        )
        
        try:
            response = requests.get(
                f"{pms_config['endpoint']}/health",
                headers={'Authorization': f'Bearer {auth_token}'},
                timeout=5
            )
            response.raise_for_status()
            
            step_connect.passed = True
            step_connect.details = "Connection test passed"
        except Exception as e:
            step_connect.error_message = str(e)
        
        run.add_step(step_connect)
        
        return run.finalize()
```

**Step 2: Test it**

```python
# In Django shell or view
from myapp.validations import validate_opera_pms

result = validate_opera_pms(hotel_id=123)
print(f"Status: {result.status}")
print(f"Steps: {len(result.steps)}")
for step in result.steps:
    status = "✅" if step.passed else "❌"
    print(f"  {status} {step.name}: {step.details or step.error_message}")
```

**Step 3: Check SpecTrace Dashboard**

1. Go to http://localhost:8000/admin/requirements/inappvalidation/
2. Find "Opera PMS Connection - Hotel 123"
3. Click to see step-by-step breakdown

---

## Django Admin Integration

Add "Test Connection" buttons to your Django admin.

### Simple Integration

```python
# In myapp/admin.py
from django.contrib import admin
from spectrace_client.examples.admin_integration import create_pms_test_action
from myapp.validations import validate_opera_pms
from .models import Hotel

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ['name', 'pms_vendor', 'last_validated_at']
    actions = [create_pms_test_action(validate_opera_pms)]
```

Now admins can:
1. Go to `/admin/myapp/hotel/`
2. Select one or more hotels
3. Choose "Test Opera PMS Connection" from actions
4. Click "Go"
5. See immediate results in admin messages

### Advanced: Multiple Vendors

Support multiple PMS vendors:

```python
from myapp.validations import validate_opera_pms, validate_mews_pms

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ['name', 'pms_vendor', 'last_validated_at']
    actions = [
        create_pms_test_action(validate_opera_pms),
        create_pms_test_action(validate_mews_pms),
    ]
    
    def get_actions(self, request):
        """Only show relevant actions based on hotel's vendor."""
        actions = super().get_actions(request)
        # Custom filtering logic here if needed
        return actions
```

---

## REST API Integration

Expose validation as a REST API endpoint for frontend buttons.

### Step 1: Create View

Create `myapp/views.py`:

```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from myapp.validations import validate_opera_pms

@csrf_exempt
@require_http_methods(["POST"])
def test_pms_connection(request, hotel_id):
    """Test PMS connection for a hotel.
    
    POST /api/hotels/{hotel_id}/test-pms/
    Body: {"feature_flags": {"new_auth": true}}
    """
    try:
        body = json.loads(request.body) if request.body else {}
        feature_flags = body.get('feature_flags', {})
        
        result = validate_opera_pms(hotel_id, feature_flags)
        
        return JsonResponse({
            'success': True,
            'validation': {
                'status': result.status.value,
                'message': result.message,
                'steps': [
                    {
                        'name': step.name,
                        'passed': step.passed,
                        'details': step.details,
                        'error_message': step.error_message
                    }
                    for step in result.steps
                ]
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
```

### Step 2: Add URL

In `myapp/urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('api/hotels/<int:hotel_id>/test-pms/', views.test_pms_connection),
]
```

### Step 3: Call from Frontend

```javascript
// React example
const testPMSConnection = async (hotelId) => {
    const response = await fetch(`/api/hotels/${hotelId}/test-pms/`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            feature_flags: {new_auth: true}
        })
    });
    
    const data = await response.json();
    
    if (data.success && data.validation.status === 'success') {
        alert('✅ PMS connection test passed!');
    } else {
        const failedSteps = data.validation.steps
            .filter(s => !s.passed)
            .map(s => `${s.name}: ${s.error_message}`)
            .join('\n');
        alert(`❌ Test failed:\n${failedSteps}`);
    }
};

// Usage in component
<button onClick={() => testPMSConnection(123)}>
    Test PMS Connection
</button>
```

---

## Feature Flag Tracking

Track which feature flags were active during validations.

### Option 1: Manual Extraction

```python
from spectrace_client import extract_feature_flags

def validate_with_flags(hotel_id):
    hotel = Hotel.objects.get(id=hotel_id)
    
    # Auto-extract from multiple sources
    flags = extract_feature_flags(
        django_prefix='FEATURE_',      # From settings.FEATURE_*
        env_prefix='FF_',               # From FF_* env vars
        model_instance=hotel,           # From hotel.feature_flags
        model_field='feature_flags'
    )
    
    with ValidationRun(..., context={'feature_flags': flags}) as run:
        # Validation logic
        pass
```

### Option 2: Decorator (Auto-Inject)

```python
from spectrace_client import with_feature_flags

@with_feature_flags(model_param='hotel')
def validate_pms(hotel_id, hotel=None, feature_flags=None):
    # feature_flags automatically populated!
    with ValidationRun(..., context={'feature_flags': feature_flags}) as run:
        # Validation logic
        pass
```

### Feature Flag Sources

#### Django Settings

```python
# settings.py
FEATURE_NEW_AUTH = True
FEATURE_LEGACY_MODE = False
FEATURE_DEBUG_LOGGING = True
```

#### Environment Variables

```bash
export FF_NEW_AUTH=true
export FF_LEGACY_MODE=false
export FF_DEBUG_LOGGING=1
```

#### Model Field

```python
class Hotel(models.Model):
    feature_flags = models.JSONField(default=dict, blank=True)
    
hotel.feature_flags = {
    'new_auth': True,
    'beta_features': False
}
```

### Viewing in Dashboard

1. Go to `/admin/vendor-coverage/`
2. See feature flags grouped by vendor
3. Correlate flags with pass/fail rates

---

## Production Deployment

### 1. Environment Configuration

```bash
# Production .env file
SPECTRACE_URL=https://spectrace.internal.company.com
SPECTRACE_API_KEY=prod-secret-key
```

### 2. Async Submission (Recommended)

For high-traffic environments, submit validations asynchronously:

```python
from celery import shared_task
from myapp.validations import validate_opera_pms

@shared_task
def validate_opera_pms_async(hotel_id, feature_flags=None):
    """Run validation in background task."""
    return validate_opera_pms(hotel_id, feature_flags)

# Usage
from myapp.tasks import validate_opera_pms_async
validate_opera_pms_async.delay(hotel_id=123)
```

### 3. Monitoring

Enable logging for SDK:

```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'spectrace_client': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}
```

### 4. Health Checks

Add automated validations:

```python
# management/commands/validate_all_hotels.py
from django.core.management.base import BaseCommand
from myapp.models import Hotel
from myapp.validations import validate_opera_pms

class Command(BaseCommand):
    help = 'Validate all hotel PMS connections'
    
    def handle(self, *args, **options):
        for hotel in Hotel.objects.filter(pms_active=True):
            self.stdout.write(f'Validating {hotel.name}...')
            result = validate_opera_pms(hotel.id)
            if result.status.value == 'success':
                self.stdout.write(self.style.SUCCESS('✅ Passed'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Failed: {result.message}'))
```

Schedule with cron or celery beat:

```python
# Celery beat schedule (hourly validation)
CELERY_BEAT_SCHEDULE = {
    'validate-all-hotels': {
        'task': 'myapp.tasks.validate_all_hotels',
        'schedule': crontab(minute=0, hour='*'),  # Every hour
    },
}
```

### 5. Error Handling

The SDK uses best-effort submission. Monitor logs for issues:

```python
# Check logs for submission failures
tail -f /var/log/django/app.log | grep "spectrace_client"
```

Common issues:
- `Connection refused`: SpecTrace dashboard is down (validations still run)
- `Timeout`: Network issue (validations still run)
- `401 Unauthorized`: API key is invalid (check settings)

---

## Next Steps

- See [README.md](../README.md) for API reference
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
- See [examples/](../examples/) for complete working examples

## Support

File issues in the SpecTrace repository or contact your team's SpecTrace maintainer.
