"""PMS (Property Management System) validation examples.

This module demonstrates how to integrate SpecTrace SDK with PMS providers
like Opera, Mews, etc. Each validation follows a 5-step pattern:

1. Load configuration from database
2. Authenticate with PMS API
3. Test connection
4. Test read access (fetch reservations)
5. Test write access (update reservation)

Usage:
    # In your Django view/API/admin action:
    from spectrace_client.examples.pms import validate_opera_pms
    
    result = validate_opera_pms(hotel_id=123)
    if result.status == ValidationStatus.SUCCESS:
        print("✅ Opera PMS is working!")
"""
from typing import Any
from datetime import datetime
import requests

from spectrace_client import (
    ValidationRun,
    ValidationStatus,
    ValidationStep,
    verify_requirement,
)


def validate_opera_pms(hotel_id: int, feature_flags: dict[str, bool] | None = None) -> Any:
    """Validate Opera PMS integration for a specific hotel.
    
    Args:
        hotel_id: Hotel database ID
        feature_flags: Optional feature flags to track (e.g., {'new_auth': True})
    
    Returns:
        ValidationResult with 5-step breakdown
    """
    feature_flags = feature_flags or {}
    
    with ValidationRun(
        requirement_id="REQ-PMS-001",
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
            config = _load_pms_config(hotel_id, 'Opera')
            step_config.passed = True
            step_config.details = f"Loaded config for {config['endpoint']}"
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
            auth_token = _authenticate_opera(config, feature_flags)
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
            _test_opera_connection(config, auth_token)
            step_connect.passed = True
            step_connect.details = "Connection test passed"
        except Exception as e:
            step_connect.error_message = str(e)
            run.add_step(step_connect)
            return run.finalize()
        
        run.add_step(step_connect)
        
        # Step 4: Test read access
        step_read = ValidationStep(
            name='test_read_access',
            passed=False,
            timestamp=datetime.now()
        )
        
        try:
            reservations = _fetch_opera_reservations(config, auth_token, limit=1)
            step_read.passed = True
            step_read.details = f"Fetched {len(reservations)} reservation(s)"
        except Exception as e:
            step_read.error_message = str(e)
            run.add_step(step_read)
            return run.finalize()
        
        run.add_step(step_read)
        
        # Step 5: Test write access (read-only check in this example)
        step_write = ValidationStep(
            name='test_write_access',
            passed=False,
            timestamp=datetime.now()
        )
        
        try:
            # In production, you'd do a real write test (e.g., update a test reservation)
            # For this example, we just verify we have write permissions in auth token
            if 'write' in auth_token.get('scopes', []):
                step_write.passed = True
                step_write.details = "Write permissions verified"
            else:
                step_write.passed = False
                step_write.error_message = "Missing write permissions"
        except Exception as e:
            step_write.error_message = str(e)
        
        run.add_step(step_write)
        
        return run.finalize()


def validate_mews_pms(hotel_id: int, feature_flags: dict[str, bool] | None = None) -> Any:
    """Validate Mews PMS integration for a specific hotel.
    
    Args:
        hotel_id: Hotel database ID
        feature_flags: Optional feature flags to track
    
    Returns:
        ValidationResult with 5-step breakdown
    """
    feature_flags = feature_flags or {}
    
    with ValidationRun(
        requirement_id="REQ-PMS-002",
        name=f"Mews PMS Connection - Hotel {hotel_id}",
        context={
            'vendor': 'Mews',
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
            config = _load_pms_config(hotel_id, 'Mews')
            step_config.passed = True
            step_config.details = f"Loaded config for {config['endpoint']}"
        except Exception as e:
            step_config.error_message = str(e)
            run.add_step(step_config)
            return run.finalize()
        
        run.add_step(step_config)
        
        # Step 2: Authenticate (Mews uses client token)
        step_auth = ValidationStep(
            name='authenticate',
            passed=False,
            timestamp=datetime.now()
        )
        
        try:
            client_token = _authenticate_mews(config, feature_flags)
            step_auth.passed = True
            step_auth.details = "Client token validated"
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
            _test_mews_connection(config, client_token)
            step_connect.passed = True
            step_connect.details = "Connection test passed"
        except Exception as e:
            step_connect.error_message = str(e)
            run.add_step(step_connect)
            return run.finalize()
        
        run.add_step(step_connect)
        
        # Step 4: Test read access
        step_read = ValidationStep(
            name='test_read_access',
            passed=False,
            timestamp=datetime.now()
        )
        
        try:
            reservations = _fetch_mews_reservations(config, client_token, limit=1)
            step_read.passed = True
            step_read.details = f"Fetched {len(reservations)} reservation(s)"
        except Exception as e:
            step_read.error_message = str(e)
            run.add_step(step_read)
            return run.finalize()
        
        run.add_step(step_read)
        
        # Step 5: Test write access
        step_write = ValidationStep(
            name='test_write_access',
            passed=False,
            timestamp=datetime.now()
        )
        
        try:
            # Mews uses scoped tokens - check for write scope
            if _check_mews_write_permissions(client_token):
                step_write.passed = True
                step_write.details = "Write permissions verified"
            else:
                step_write.passed = False
                step_write.error_message = "Missing write permissions"
        except Exception as e:
            step_write.error_message = str(e)
        
        run.add_step(step_write)
        
        return run.finalize()


# Helper functions (stub implementations - replace with real logic)

def _load_pms_config(hotel_id: int, vendor: str) -> dict[str, Any]:
    """Load PMS configuration from database.
    
    In production, this would query your Hotel/PMSConfig model.
    """
    # Stub implementation
    return {
        'endpoint': f'https://{vendor.lower()}.example.com/api',
        'client_id': 'test_client_id',
        'client_secret': 'test_secret',
    }


def _authenticate_opera(config: dict, feature_flags: dict) -> dict[str, Any]:
    """Authenticate with Opera PMS API.
    
    Args:
        config: PMS configuration
        feature_flags: Feature flags to use (e.g., {'new_auth': True})
    
    Returns:
        Auth token with scopes
    """
    # Stub implementation
    # In production, you'd make a real OAuth request:
    # response = requests.post(f"{config['endpoint']}/oauth/token", ...)
    
    # Simulate using new auth flow if feature flag is enabled
    if feature_flags.get('new_auth'):
        # Use new OAuth 2.0 flow
        pass
    else:
        # Use legacy API key flow
        pass
    
    return {
        'access_token': 'mock_token',
        'scopes': ['read', 'write'],
        'expires_in': 3600,
    }


def _test_opera_connection(config: dict, auth_token: dict) -> None:
    """Test basic connectivity to Opera API.
    
    Raises:
        Exception: If connection test fails
    """
    # Stub implementation
    # In production:
    # response = requests.get(
    #     f"{config['endpoint']}/health",
    #     headers={'Authorization': f"Bearer {auth_token['access_token']}"}
    # )
    # response.raise_for_status()
    pass


def _fetch_opera_reservations(config: dict, auth_token: dict, limit: int = 1) -> list[dict]:
    """Fetch reservations from Opera to test read access.
    
    Returns:
        List of reservation dicts
    """
    # Stub implementation
    # In production:
    # response = requests.get(
    #     f"{config['endpoint']}/reservations",
    #     headers={'Authorization': f"Bearer {auth_token['access_token']}"},
    #     params={'limit': limit}
    # )
    # return response.json()
    return [{'id': 'RES-123', 'guest_name': 'Test Guest'}]


def _authenticate_mews(config: dict, feature_flags: dict) -> dict[str, Any]:
    """Authenticate with Mews API using client token."""
    # Stub implementation
    return {
        'client_token': 'mock_mews_token',
        'scopes': ['reservations.read', 'reservations.write'],
    }


def _test_mews_connection(config: dict, client_token: dict) -> None:
    """Test basic connectivity to Mews API."""
    # Stub implementation
    pass


def _fetch_mews_reservations(config: dict, client_token: dict, limit: int = 1) -> list[dict]:
    """Fetch reservations from Mews."""
    # Stub implementation
    return [{'id': 'MEWS-456', 'guest': 'Test Guest'}]


def _check_mews_write_permissions(client_token: dict) -> bool:
    """Check if client token has write permissions."""
    # Stub implementation
    return 'reservations.write' in client_token.get('scopes', [])
