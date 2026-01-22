"""Tests for SpecTrace validation SDK."""
import os
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase, override_settings

from spectrace_client import (
    ValidationClient,
    ValidationRun,
    ValidationStatus,
    verify_requirement,
)


class ValidationClientTests(TestCase):
    """Tests for ValidationClient configuration and submission."""
    
    def test_from_settings_uses_env_vars(self):
        """Client should read config from environment variables."""
        with patch.dict(os.environ, {
            'SPECTRACE_URL': 'https://spectrace.example.com',
            'SPECTRACE_API_KEY': 'test-key-123',
            'SPECTRACE_ENABLED': 'true',
        }):
            client = ValidationClient.from_settings()
            
            assert client.api_url == 'https://spectrace.example.com'
            assert client.api_key == 'test-key-123'
            assert client.enabled is True
    
    @override_settings(SPECTRACE={
        'API_URL': 'https://settings.example.com',
        'API_KEY': 'settings-key',
        'ENABLED': False,
    })
    def test_from_settings_uses_django_settings(self):
        """Client should fall back to Django settings if env vars not set."""
        client = ValidationClient.from_settings()
        
        assert client.api_url == 'https://settings.example.com'
        assert client.api_key == 'settings-key'
        assert client.enabled is False
    
    @patch('spectrace_client.client.requests.Session')
    def test_submit_validation_disabled(self, mock_session):
        """Client should skip submission when disabled."""
        client = ValidationClient(
            api_url='https://example.com',
            enabled=False,
        )
        
        from spectrace_client.models import ValidationResult
        result = ValidationResult(
            requirement_id='REQ-TEST-001',
            name='Test',
            status=ValidationStatus.SUCCESS,
        )
        
        success = client.submit_validation(result)
        
        assert success is True
        mock_session.return_value.post.assert_not_called()


class ValidationRunTests(TestCase):
    """Tests for ValidationRun context manager."""
    
    @patch('spectrace_client.context.ValidationClient')
    def test_validation_run_all_pass(self, mock_client_class):
        """ValidationRun should compute SUCCESS when all steps pass."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client
        
        with ValidationRun('REQ-TEST-001', 'Test Validation') as run:
            run.step('step1', passed=True, details='Step 1 ok')
            run.step('step2', passed=True, details='Step 2 ok')
        
        assert run.result is not None
        assert run.result.status == ValidationStatus.SUCCESS
        assert len(run.result.steps) == 2
        assert run.result.message == 'All 2 checks passed'
        mock_client.submit_validation.assert_called_once()
    
    @patch('spectrace_client.context.ValidationClient')
    def test_validation_run_mixed_results(self, mock_client_class):
        """ValidationRun should compute DEGRADED when some steps fail."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client
        
        with ValidationRun('REQ-TEST-001', 'Test Validation') as run:
            run.step('step1', passed=True, details='Step 1 ok')
            run.step('step2', passed=False, error_message='Step 2 failed')
            run.step('step3', passed=True, details='Step 3 ok')
        
        assert run.result is not None
        assert run.result.status == ValidationStatus.DEGRADED
        assert run.result.message == '2 passed, 1 failed'
    
    @patch('spectrace_client.context.ValidationClient')
    def test_validation_run_all_fail(self, mock_client_class):
        """ValidationRun should compute FAILURE when all steps fail."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client
        
        with ValidationRun('REQ-TEST-001', 'Test Validation') as run:
            run.step('step1', passed=False, error_message='Failed 1')
            run.step('step2', passed=False, error_message='Failed 2')
        
        assert run.result is not None
        assert run.result.status == ValidationStatus.FAILURE
        assert run.result.message == 'All 2 checks failed'
    
    @patch('spectrace_client.context.ValidationClient')
    def test_validation_run_exception_handling(self, mock_client_class):
        """ValidationRun should mark status as ERROR on exception."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client
        
        run = None
        with pytest.raises(ValueError):
            with ValidationRun('REQ-TEST-001', 'Test Validation') as run:
                run.step('step1', passed=True)
                raise ValueError("Something went wrong")
        
        assert run is not None
        assert run.result is not None
        assert run.result.status == ValidationStatus.ERROR
        assert 'Something went wrong' in run.result.message


class VerifyRequirementDecoratorTests(TestCase):
    """Tests for @verify_requirement decorator."""
    
    @patch('spectrace_client.decorators.ValidationClient')
    def test_decorator_injects_validation_run(self, mock_client_class):
        """Decorator should inject validation_run kwarg to function."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client
        
        @verify_requirement('REQ-TEST-001', name='Test')
        def validate_something(validation_run: ValidationRun):
            validation_run.step('check', passed=True)
            return validation_run.result
        
        result = validate_something()  # type: ignore[call-arg]
        
        assert result is not None
        assert result.requirement_id == 'REQ-TEST-001'
        assert result.status == ValidationStatus.SUCCESS
        mock_client.submit_validation.assert_called_once()
    
    @patch('spectrace_client.decorators.ValidationClient')
    def test_decorator_with_function_args(self, mock_client_class):
        """Decorator should pass through function args."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client
        
        @verify_requirement('REQ-TEST-001', name='Test')
        def validate_with_args(obj, validation_run: ValidationRun):
            validation_run.step('check', passed=True, details=f'Checked {obj.name}')
            return validation_run.result
        
        mock_obj = Mock()
        mock_obj.name = 'TestObject'
        
        result = validate_with_args(mock_obj)  # type: ignore[call-arg]
        
        assert result is not None
        assert result.steps[0].details == 'Checked TestObject'
    
    @patch('spectrace_client.decorators.ValidationClient')
    def test_decorator_with_context_fn(self, mock_client_class):
        """Decorator should extract context using context_fn."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client
        
        @verify_requirement(
            'REQ-TEST-001',
            name='Test',
            context_fn=lambda obj: {'obj_id': obj.id, 'obj_name': obj.name}
        )
        def validate_with_context(obj, validation_run: ValidationRun):
            validation_run.step('check', passed=True)
            return validation_run.result
        
        mock_obj = Mock()
        mock_obj.id = 123
        mock_obj.name = 'TestObject'
        
        result = validate_with_context(mock_obj)  # type: ignore[call-arg]
        
        assert result.context == {'obj_id': 123, 'obj_name': 'TestObject'}
    
    @patch('spectrace_client.decorators.ValidationClient')
    def test_decorator_without_validation_run_kwarg(self, mock_client_class):
        """Decorator should work even if function doesn't accept validation_run."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client
        
        @verify_requirement('REQ-TEST-001', name='Test')
        def validate_without_kwarg():
            # Function doesn't accept validation_run
            return "done"
        
        result = validate_without_kwarg()
        
        # Since function didn't use validation_run, should return ValidationResult
        # with empty steps (from wrapper's default behavior)
        assert result is not None
