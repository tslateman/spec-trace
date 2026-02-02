"""Tests for run_flow management command."""
import json
from io import StringIO
from unittest.mock import patch

import pytest
import responses
from django.core.management import call_command
from django.core.management.base import CommandError

from requirements.models import (
    VerificationFlow,
    VerificationFlowRun,
    VerificationFlowSource,
    VerificationFlowStatus,
)


@pytest.fixture
def flow_with_api_call(db):
    """Create a test flow with api_call step."""
    return VerificationFlow.objects.create(
        name="test-api-flow",
        display_name="Test API Flow",
        steps=[
            {
                'name': 'health_check',
                'type': 'api_call',
                'display_name': 'Health Check',
                'config': {
                    'method': 'GET',
                    'url': 'http://localhost:8000/api/health/',
                    'expected_status': 200,
                }
            }
        ],
        version=1,
    )


@pytest.fixture
def flow_with_wait_step(db):
    """Create a test flow with a simple wait step."""
    return VerificationFlow.objects.create(
        name="wait-flow",
        display_name="Wait Flow",
        steps=[
            {
                'name': 'brief_wait',
                'type': 'wait',
                'display_name': 'Brief Wait',
                'config': {
                    'seconds': 0.01,
                }
            }
        ],
        version=1,
    )


# ============================================================================
# Lookup tests
# ============================================================================


@pytest.mark.django_db
def test_run_flow__finds_flow_by_name(flow_with_wait_step):
    """run_flow test-api-flow finds correct flow."""
    stdout = StringIO()
    call_command('run_flow', 'wait-flow', stdout=stdout)

    output = stdout.getvalue()
    assert 'Wait Flow (wait-flow)' in output
    assert 'Status: passed' in output


@pytest.mark.django_db
def test_run_flow__finds_flow_by_id(flow_with_wait_step):
    """run_flow <id> finds correct flow."""
    stdout = StringIO()
    call_command('run_flow', str(flow_with_wait_step.pk), stdout=stdout)

    output = stdout.getvalue()
    assert 'Wait Flow (wait-flow)' in output
    assert 'Status: passed' in output


@pytest.mark.django_db
def test_run_flow__not_found_error():
    """run_flow nonexistent raises CommandError."""
    with pytest.raises(CommandError, match="Flow not found: nonexistent"):
        call_command('run_flow', 'nonexistent')


@pytest.mark.django_db
def test_run_flow__not_found_by_numeric_id():
    """run_flow 9999 raises CommandError when ID doesn't exist."""
    with pytest.raises(CommandError, match="Flow not found: 9999"):
        call_command('run_flow', '9999')


# ============================================================================
# Execution tests (mock HTTP)
# ============================================================================


@pytest.mark.django_db
@responses.activate
def test_run_flow__passes_when_all_steps_pass(flow_with_api_call):
    """Mock successful HTTP, verify exit 0."""
    responses.add(
        responses.GET,
        'http://localhost:8000/api/health/',
        json={'status': 'ok'},
        status=200,
    )

    stdout = StringIO()
    # call_command doesn't raise SystemExit, but we can check output
    call_command('run_flow', flow_with_api_call.name, stdout=stdout)

    output = stdout.getvalue()
    assert 'Status: passed' in output
    assert '[PASS]' in output


@pytest.mark.django_db
@responses.activate
def test_run_flow__fails_when_step_fails(flow_with_api_call):
    """Mock 500 response, verify exit 1."""
    responses.add(
        responses.GET,
        'http://localhost:8000/api/health/',
        json={'error': 'Internal Server Error'},
        status=500,
    )

    stdout = StringIO()
    with pytest.raises(SystemExit) as exc_info:
        call_command('run_flow', flow_with_api_call.name, stdout=stdout)

    assert exc_info.value.code == 1
    output = stdout.getvalue()
    assert 'Status: failed' in output
    assert '[FAIL]' in output


@pytest.mark.django_db
@responses.activate
def test_run_flow__outputs_step_results(flow_with_api_call):
    """Verify output contains step names and status."""
    responses.add(
        responses.GET,
        'http://localhost:8000/api/health/',
        json={'status': 'ok'},
        status=200,
    )

    stdout = StringIO()
    call_command('run_flow', flow_with_api_call.name, stdout=stdout)

    output = stdout.getvalue()
    assert 'health_check' in output
    assert 'Steps:' in output
    assert 'Duration:' in output


# ============================================================================
# Context tests
# ============================================================================


@pytest.mark.django_db
def test_run_flow__parses_json_context(flow_with_wait_step):
    """--context '{"key": "value"}' passed to engine."""
    stdout = StringIO()
    context_json = json.dumps({"test_key": "test_value"})
    call_command('run_flow', flow_with_wait_step.name, '--context', context_json, stdout=stdout)

    # Verify the run was created with context
    run = VerificationFlowRun.objects.filter(flow=flow_with_wait_step).first()
    assert run is not None
    assert run.context.get('test_key') == 'test_value'


@pytest.mark.django_db
def test_run_flow__invalid_json_raises_error(flow_with_wait_step):
    """--context 'not json' raises CommandError."""
    with pytest.raises(CommandError, match="Invalid JSON context"):
        call_command('run_flow', flow_with_wait_step.name, '--context', 'not json')


@pytest.mark.django_db
def test_run_flow__empty_context_when_not_provided(flow_with_wait_step):
    """Default empty context when --context not provided."""
    stdout = StringIO()
    call_command('run_flow', flow_with_wait_step.name, stdout=stdout)

    run = VerificationFlowRun.objects.filter(flow=flow_with_wait_step).first()
    assert run is not None
    assert run.context == {}


# ============================================================================
# Timeout tests
# ============================================================================


@pytest.mark.django_db
@patch('requirements.flows.engine.SequentialFlowEngine.execute', autospec=True)
def test_run_flow__passes_timeout_to_engine(mock_execute, flow_with_wait_step):
    """Verify engine called with correct timeout values."""
    # Create a real saved run to return (with proper related manager)
    mock_run = VerificationFlowRun.objects.create(
        flow=flow_with_wait_step,
        status=VerificationFlowStatus.PASSED,
    )
    mock_execute.return_value = mock_run

    stdout = StringIO()
    call_command(
        'run_flow',
        flow_with_wait_step.name,
        '--timeout', '120',
        '--step-timeout', '30',
        stdout=stdout,
    )

    # Check engine was called with correct params
    mock_execute.assert_called_once()
    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs['flow_timeout'] == 120
    assert call_kwargs['step_timeout'] == 30
    assert call_kwargs['source'] == VerificationFlowSource.MANUAL


@pytest.mark.django_db
@patch('requirements.flows.engine.SequentialFlowEngine.execute', autospec=True)
def test_run_flow__uses_default_timeouts(mock_execute, flow_with_wait_step):
    """Verify default timeout values when not specified."""
    mock_run = VerificationFlowRun.objects.create(
        flow=flow_with_wait_step,
        status=VerificationFlowStatus.PASSED,
    )
    mock_execute.return_value = mock_run

    stdout = StringIO()
    call_command('run_flow', flow_with_wait_step.name, stdout=stdout)

    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs['flow_timeout'] == 300  # default
    assert call_kwargs['step_timeout'] == 60   # default


# ============================================================================
# Integration tests
# ============================================================================


@pytest.mark.django_db
@responses.activate
def test_run_flow__executes_yaml_flow_with_api_call_and_assertion():
    """Execute multi-step flow with api_call and assertion, verify database records."""
    flow = VerificationFlow.objects.create(
        name="integration-test",
        display_name="Integration Test",
        steps=[
            {
                'name': 'health_endpoint',
                'type': 'api_call',
                'display_name': 'Health Endpoint Check',
                'config': {
                    'method': 'GET',
                    'url': 'http://testserver/api/health/',
                    'expected_status': 200,
                }
            },
            {
                'name': 'response_format',
                'type': 'assertion',
                'display_name': 'Response Format Check',
                'config': {
                    'field': 'status',
                    'operator': 'equals',
                    'value': 'ok',
                }
            },
        ],
        version=1,
    )

    # Mock API response
    responses.add(
        responses.GET,
        'http://testserver/api/health/',
        json={'status': 'ok'},
        status=200,
    )

    stdout = StringIO()
    call_command('run_flow', flow.name, stdout=stdout)

    # Verify output
    output = stdout.getvalue()
    assert 'Status: passed' in output

    # Verify database records
    run = VerificationFlowRun.objects.filter(flow=flow).first()
    assert run is not None
    assert run.status == VerificationFlowStatus.PASSED
    assert run.source == VerificationFlowSource.MANUAL

    # Verify both steps recorded
    steps = list(run.steps.order_by('step_order'))
    assert len(steps) == 2
    assert steps[0].name == 'health_endpoint'
    assert steps[0].passed is True
    assert steps[1].name == 'response_format'
    assert steps[1].passed is True


@pytest.mark.django_db
@responses.activate
def test_run_flow__records_run_in_database():
    """Verify flow execution creates proper database records."""
    flow = VerificationFlow.objects.create(
        name="db-record-test",
        display_name="DB Record Test",
        steps=[
            {
                'name': 'step_one',
                'type': 'api_call',
                'display_name': 'Step One',
                'config': {
                    'method': 'GET',
                    'url': 'http://example.com/api/',
                    'expected_status': 200,
                }
            },
        ],
        version=1,
    )

    responses.add(
        responses.GET,
        'http://example.com/api/',
        json={'result': 'success'},
        status=200,
    )

    stdout = StringIO()
    call_command('run_flow', flow.name, stdout=stdout)

    # Query run
    runs = VerificationFlowRun.objects.filter(flow=flow)
    assert runs.count() == 1

    run = runs.first()
    assert run.status == VerificationFlowStatus.PASSED
    assert run.source == VerificationFlowSource.MANUAL
    assert run.started_at is not None
    assert run.completed_at is not None

    # Verify step
    steps = list(run.steps.all())
    assert len(steps) == 1
    assert steps[0].step_order == 0
    assert steps[0].name == 'step_one'
    assert steps[0].passed is True


@pytest.mark.django_db
def test_run_flow__handles_metadata_in_steps():
    """Flow with _metadata entry executes correctly, metadata filtered out."""
    flow = VerificationFlow.objects.create(
        name="metadata-test",
        display_name="Metadata Test",
        steps=[
            {'_metadata': {'source_file': 'test.yaml', 'requirements': []}},
            {
                'name': 'actual_step',
                'type': 'wait',
                'display_name': 'Actual Step',
                'config': {'seconds': 0.01}
            },
        ],
        version=1,
    )

    stdout = StringIO()
    call_command('run_flow', flow.name, stdout=stdout)

    output = stdout.getvalue()
    assert 'Status: passed' in output

    # Verify only one step recorded (metadata filtered)
    run = VerificationFlowRun.objects.filter(flow=flow).first()
    assert run is not None
    steps = list(run.steps.all())
    assert len(steps) == 1
    assert steps[0].name == 'actual_step'
