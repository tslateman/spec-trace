"""REST API endpoint integration example.

This module demonstrates how to create REST API endpoints that trigger
on-demand validations using the SpecTrace SDK. Useful for:
- Frontend "Test Connection" buttons
- Webhook-triggered validations
- Scheduled health checks via cron/celery

Usage:
    # In your urls.py:
    from spectrace_client.examples.api_integration import hotel_validation_views
    
    urlpatterns = [
        path('api/hotels/<int:hotel_id>/validate-pms/', 
             hotel_validation_views.test_pms_connection),
        path('api/hotels/<int:hotel_id>/validate-mobile-key/', 
             hotel_validation_views.test_mobile_key),
    ]
"""
from typing import Any
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from spectrace_client import ValidationStatus


# Example: Single hotel validation endpoint
@csrf_exempt
@require_http_methods(["POST"])
def test_pms_connection(request: HttpRequest, hotel_id: int) -> JsonResponse:
    """Test PMS connection for a specific hotel.
    
    POST /api/hotels/{hotel_id}/validate-pms/
    
    Request body (optional):
        {
            "vendor": "Opera",  # If not provided, uses hotel's configured vendor
            "feature_flags": {"new_auth": true}
        }
    
    Response:
        {
            "success": true,
            "validation": {
                "requirement_id": "REQ-PMS-001",
                "name": "Opera PMS Connection - Hotel 123",
                "status": "success",
                "message": "All steps passed",
                "steps": [
                    {"name": "load_config", "passed": true, "details": "..."},
                    {"name": "authenticate", "passed": true, "details": "..."},
                    ...
                ]
            }
        }
    """
    try:
        # Parse request body
        body = json.loads(request.body) if request.body else {}
        vendor = body.get('vendor')
        feature_flags = body.get('feature_flags', {})
        
        # Dynamically choose validation function based on vendor
        from spectrace_client.examples.pms import validate_opera_pms, validate_mews_pms
        
        if vendor == 'Mews':
            result = validate_mews_pms(hotel_id, feature_flags)
        else:
            # Default to Opera
            result = validate_opera_pms(hotel_id, feature_flags)
        
        return JsonResponse({
            'success': True,
            'validation': {
                'requirement_id': result.requirement_id,
                'name': result.name,
                'status': result.status.value,
                'message': result.message,
                'steps': [
                    {
                        'name': step.name,
                        'passed': step.passed,
                        'details': step.details,
                        'error_message': step.error_message,
                        'duration_ms': step.duration_ms,
                    }
                    for step in result.steps
                ],
                'context': result.context,
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def test_mobile_key(request: HttpRequest, hotel_id: int) -> JsonResponse:
    """Test mobile key connection for a specific hotel.
    
    POST /api/hotels/{hotel_id}/validate-mobile-key/
    
    Request body (optional):
        {
            "vendor": "Ambiance",
            "feature_flags": {"new_protocol": true}
        }
    
    Response: Same format as test_pms_connection
    """
    try:
        body = json.loads(request.body) if request.body else {}
        vendor = body.get('vendor')
        feature_flags = body.get('feature_flags', {})
        
        from spectrace_client.examples.mobile_key import (
            validate_ambiance_mobile_key,
            validate_openkey_mobile_key,
            validate_vostio_mobile_key,
        )
        
        if vendor == 'OpenKey':
            result = validate_openkey_mobile_key(hotel_id, feature_flags)
        elif vendor == 'Vostio':
            result = validate_vostio_mobile_key(hotel_id, feature_flags)
        else:
            # Default to Ambiance
            result = validate_ambiance_mobile_key(hotel_id, feature_flags)
        
        return JsonResponse({
            'success': True,
            'validation': {
                'requirement_id': result.requirement_id,
                'name': result.name,
                'status': result.status.value,
                'message': result.message,
                'steps': [
                    {
                        'name': step.name,
                        'passed': step.passed,
                        'details': step.details,
                        'error_message': step.error_message,
                    }
                    for step in result.steps
                ],
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Example: Batch validation endpoint
@csrf_exempt
@require_http_methods(["POST"])
def batch_validate_hotels(request: HttpRequest) -> JsonResponse:
    """Validate multiple hotels in a single request.
    
    POST /api/hotels/batch-validate/
    
    Request body:
        {
            "hotel_ids": [123, 456, 789],
            "validation_type": "pms",  # or "mobile_key"
            "feature_flags": {"new_auth": true}
        }
    
    Response:
        {
            "success": true,
            "results": {
                "123": {"status": "success", "message": "All steps passed"},
                "456": {"status": "degraded", "message": "2/5 steps passed"},
                "789": {"status": "failure", "message": "Connection failed"}
            },
            "summary": {
                "total": 3,
                "success": 1,
                "degraded": 1,
                "failure": 1
            }
        }
    """
    try:
        body = json.loads(request.body)
        hotel_ids = body.get('hotel_ids', [])
        validation_type = body.get('validation_type', 'pms')
        feature_flags = body.get('feature_flags', {})
        
        results = {}
        summary = {'total': len(hotel_ids), 'success': 0, 'degraded': 0, 'failure': 0, 'error': 0}
        
        for hotel_id in hotel_ids:
            try:
                if validation_type == 'pms':
                    from spectrace_client.examples.pms import validate_opera_pms
                    result = validate_opera_pms(hotel_id, feature_flags)
                else:
                    from spectrace_client.examples.mobile_key import validate_ambiance_mobile_key
                    result = validate_ambiance_mobile_key(hotel_id, feature_flags)
                
                results[str(hotel_id)] = {
                    'status': result.status.value,
                    'message': result.message,
                    'steps_passed': sum(1 for s in result.steps if s.passed),
                    'steps_total': len(result.steps),
                }
                
                # Update summary
                if result.status == ValidationStatus.SUCCESS:
                    summary['success'] += 1
                elif result.status == ValidationStatus.DEGRADED:
                    summary['degraded'] += 1
                elif result.status == ValidationStatus.FAILURE:
                    summary['failure'] += 1
                else:
                    summary['error'] += 1
            
            except Exception as e:
                results[str(hotel_id)] = {
                    'status': 'error',
                    'message': str(e)
                }
                summary['error'] += 1
        
        return JsonResponse({
            'success': True,
            'results': results,
            'summary': summary
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Example URLConf
"""
# In your urls.py:

from django.urls import path
from spectrace_client.examples import api_integration

urlpatterns = [
    # Single hotel validations
    path('api/hotels/<int:hotel_id>/validate-pms/',
         api_integration.test_pms_connection,
         name='test-pms-connection'),
    
    path('api/hotels/<int:hotel_id>/validate-mobile-key/',
         api_integration.test_mobile_key,
         name='test-mobile-key'),
    
    # Batch validation
    path('api/hotels/batch-validate/',
         api_integration.batch_validate_hotels,
         name='batch-validate-hotels'),
]


# Frontend usage example (React):
const testPMSConnection = async (hotelId) => {
    const response = await fetch(`/api/hotels/${hotelId}/validate-pms/`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            vendor: 'Opera',
            feature_flags: {new_auth: true}
        })
    });
    
    const data = await response.json();
    
    if (data.success && data.validation.status === 'success') {
        alert('✅ PMS connection test passed!');
    } else {
        const failedSteps = data.validation.steps
            .filter(s => !s.passed)
            .map(s => s.name)
            .join(', ');
        alert(`❌ Test failed at steps: ${failedSteps}`);
    }
};


# Curl example:
curl -X POST http://localhost:8000/api/hotels/123/validate-pms/ \\
  -H "Content-Type: application/json" \\
  -d '{"vendor": "Opera", "feature_flags": {"new_auth": true}}'
"""
