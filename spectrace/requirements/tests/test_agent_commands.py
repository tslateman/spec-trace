"""Tests for agent task CLI commands."""

import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time

from requirements.models import (
    Agent,
    AgentRole,
    AgentTask,
    AgentTaskStatus,
    AgentSprint,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def coder_agent(db):
    """Create a coder agent."""
    return Agent.objects.create(
        agent_id='coder-1',
        role=AgentRole.CODER,
        is_active=True,
    )


@pytest.fixture
def reviewer_agent(db):
    """Create a reviewer agent."""
    return Agent.objects.create(
        agent_id='reviewer-1',
        role=AgentRole.REVIEWER,
        is_active=True,
    )


@pytest.fixture
def unclaimed_task(db):
    """Create an unclaimed task."""
    return AgentTask.objects.create(
        external_id='task-001',
        title='Implement login',
        status=AgentTaskStatus.UNCLAIMED,
    )


@pytest.fixture
def sprint(db):
    """Create a sprint."""
    return AgentSprint.objects.create(
        name='Sprint 1',
        goal_description='Complete auth flow',
    )


# =============================================================================
# Test: agent_tasks command
# =============================================================================


class TestAgentTasksCommand:
    """Tests for agent_tasks command."""

    def test_agent_tasks__lists_all(self, unclaimed_task):
        """Lists all tasks."""
        out = StringIO()
        call_command('agent_tasks', stdout=out)
        output = out.getvalue()

        assert 'task-001' in output
        assert 'Implement login' in output

    def test_agent_tasks__json_format(self, unclaimed_task):
        """JSON format outputs valid JSON."""
        out = StringIO()
        call_command('agent_tasks', format='json', stdout=out)
        data = json.loads(out.getvalue())

        assert 'tasks' in data
        assert len(data['tasks']) == 1
        assert data['tasks'][0]['external_id'] == 'task-001'

    def test_agent_tasks__filter_by_status(self, db):
        """Filters by status."""
        AgentTask.objects.create(
            external_id='task-a',
            title='Task A',
            status=AgentTaskStatus.UNCLAIMED,
        )
        AgentTask.objects.create(
            external_id='task-b',
            title='Task B',
            status=AgentTaskStatus.MERGED,
        )

        out = StringIO()
        call_command('agent_tasks', status='unclaimed', format='json', stdout=out)
        data = json.loads(out.getvalue())

        assert len(data['tasks']) == 1
        assert data['tasks'][0]['external_id'] == 'task-a'

    def test_agent_tasks__filter_by_sprint(self, sprint, db):
        """Filters by sprint."""
        AgentTask.objects.create(
            external_id='task-sprint',
            title='Sprint task',
            status=AgentTaskStatus.UNCLAIMED,
            sprint=sprint,
        )
        AgentTask.objects.create(
            external_id='task-no-sprint',
            title='No sprint',
            status=AgentTaskStatus.UNCLAIMED,
        )

        out = StringIO()
        call_command('agent_tasks', sprint=sprint.id, format='json', stdout=out)
        data = json.loads(out.getvalue())

        assert len(data['tasks']) == 1
        assert data['tasks'][0]['external_id'] == 'task-sprint'


# =============================================================================
# Test: agent_claim command
# =============================================================================


class TestAgentClaimCommand:
    """Tests for agent_claim command."""

    @freeze_time('2025-01-15 12:00:00')
    def test_agent_claim__succeeds(self, coder_agent, unclaimed_task):
        """Claims task successfully."""
        out = StringIO()
        call_command(
            'agent_claim', 'task-001',
            agent='coder-1',
            format='json',
            stdout=out,
        )
        data = json.loads(out.getvalue())

        assert data['success'] is True
        assert data['to_status'] == 'claimed'

        unclaimed_task.refresh_from_db()
        assert unclaimed_task.status == AgentTaskStatus.CLAIMED

    def test_agent_claim__fails_invalid_agent(self, unclaimed_task):
        """Fails for invalid agent."""
        out = StringIO()
        err = StringIO()

        with pytest.raises(SystemExit) as exc_info:
            call_command(
                'agent_claim', 'task-001',
                agent='nonexistent',
                format='json',
                stdout=out,
                stderr=err,
            )

        assert exc_info.value.code == 1
        data = json.loads(out.getvalue())
        assert data['success'] is False
        assert data['code'] == 'AGENT_NOT_FOUND'


# =============================================================================
# Test: agent_start command
# =============================================================================


class TestAgentStartCommand:
    """Tests for agent_start command."""

    def test_agent_start__succeeds(self, coder_agent, db):
        """Starts claimed task."""
        task = AgentTask.objects.create(
            external_id='task-start',
            title='Start me',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
        )

        out = StringIO()
        call_command(
            'agent_start', 'task-start',
            agent='coder-1',
            format='json',
            stdout=out,
        )
        data = json.loads(out.getvalue())

        assert data['success'] is True
        assert data['to_status'] == 'in_progress'

    def test_agent_start__fails_wrong_owner(self, coder_agent, db):
        """Fails if not task owner."""
        coder2 = Agent.objects.create(
            agent_id='coder-2',
            role=AgentRole.CODER,
            is_active=True,
        )
        task = AgentTask.objects.create(
            external_id='task-other',
            title='Other task',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder2,
        )

        out = StringIO()
        err = StringIO()

        with pytest.raises(SystemExit):
            call_command(
                'agent_start', 'task-other',
                agent='coder-1',
                format='json',
                stdout=out,
                stderr=err,
            )

        data = json.loads(out.getvalue())
        assert data['code'] == 'NOT_OWNER'


# =============================================================================
# Test: agent_submit command
# =============================================================================


class TestAgentSubmitCommand:
    """Tests for agent_submit command."""

    def test_agent_submit__succeeds(self, coder_agent, db):
        """Submits in-progress task."""
        task = AgentTask.objects.create(
            external_id='task-submit',
            title='Submit me',
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=coder_agent,
        )

        out = StringIO()
        call_command(
            'agent_submit', 'task-submit',
            agent='coder-1',
            commit_sha='abc123def456',
            format='json',
            stdout=out,
        )
        data = json.loads(out.getvalue())

        assert data['success'] is True
        assert data['to_status'] == 'ready_for_review'
        assert data['commit_sha'] == 'abc123def456'


# =============================================================================
# Test: agent_review command
# =============================================================================


class TestAgentReviewCommand:
    """Tests for agent_review command."""

    def test_agent_review__approve(self, coder_agent, reviewer_agent, db):
        """Approves task."""
        task = AgentTask.objects.create(
            external_id='task-review',
            title='Review me',
            status=AgentTaskStatus.READY_FOR_REVIEW,
            claimed_by=coder_agent,
            commit_sha='abc123',
        )

        out = StringIO()
        call_command(
            'agent_review', 'task-review',
            reviewer='reviewer-1',
            decision='approved',
            feedback='LGTM',
            format='json',
            stdout=out,
        )
        data = json.loads(out.getvalue())

        assert data['success'] is True
        assert data['to_status'] == 'approved'
        assert data['decision'] == 'approved'

    def test_agent_review__changes_requested(self, coder_agent, reviewer_agent, db):
        """Requests changes."""
        task = AgentTask.objects.create(
            external_id='task-changes',
            title='Needs changes',
            status=AgentTaskStatus.READY_FOR_REVIEW,
            claimed_by=coder_agent,
            commit_sha='abc123',
        )

        out = StringIO()
        call_command(
            'agent_review', 'task-changes',
            reviewer='reviewer-1',
            decision='changes_requested',
            feedback='Fix X',
            blocking_issues=['Issue X'],
            format='json',
            stdout=out,
        )
        data = json.loads(out.getvalue())

        assert data['success'] is True
        assert data['to_status'] == 'changes_requested'

    def test_agent_review__self_review_fails(self, db):
        """Self-review fails."""
        agent = Agent.objects.create(
            agent_id='dual-agent',
            role=AgentRole.REVIEWER,
            is_active=True,
        )
        task = AgentTask.objects.create(
            external_id='task-self',
            title='Self review',
            status=AgentTaskStatus.READY_FOR_REVIEW,
            claimed_by=agent,
            commit_sha='abc123',
        )

        out = StringIO()
        err = StringIO()

        with pytest.raises(SystemExit):
            call_command(
                'agent_review', 'task-self',
                reviewer='dual-agent',
                decision='approved',
                format='json',
                stdout=out,
                stderr=err,
            )

        data = json.loads(out.getvalue())
        assert data['code'] == 'SELF_REVIEW_NOT_ALLOWED'


# =============================================================================
# Test: agent_merge command
# =============================================================================


class TestAgentMergeCommand:
    """Tests for agent_merge command."""

    def test_agent_merge__succeeds(self, db):
        """Merges approved task."""
        task = AgentTask.objects.create(
            external_id='task-merge',
            title='Merge me',
            status=AgentTaskStatus.APPROVED,
        )

        out = StringIO()
        call_command(
            'agent_merge', 'task-merge',
            format='json',
            stdout=out,
        )
        data = json.loads(out.getvalue())

        assert data['success'] is True
        assert data['to_status'] == 'merged'

    def test_agent_merge__fails_not_approved(self, db):
        """Fails for non-approved task."""
        task = AgentTask.objects.create(
            external_id='task-not-approved',
            title='Not approved',
            status=AgentTaskStatus.IN_PROGRESS,
        )

        out = StringIO()
        err = StringIO()

        with pytest.raises(SystemExit):
            call_command(
                'agent_merge', 'task-not-approved',
                format='json',
                stdout=out,
                stderr=err,
            )

        data = json.loads(out.getvalue())
        assert data['code'] == 'NOT_APPROVED'


# =============================================================================
# Test: agent_register command
# =============================================================================


class TestAgentRegisterCommand:
    """Tests for agent_register command."""

    def test_agent_register__creates(self, db):
        """Registers new agent."""
        out = StringIO()
        call_command(
            'agent_register', 'new-coder',
            role='coder',
            format='json',
            stdout=out,
        )
        data = json.loads(out.getvalue())

        assert data['success'] is True
        assert data['agent_id'] == 'new-coder'
        assert data['role'] == 'coder'

        agent = Agent.objects.get(agent_id='new-coder')
        assert agent.role == AgentRole.CODER

    def test_agent_register__with_config(self, db):
        """Registers with config."""
        out = StringIO()
        call_command(
            'agent_register', 'config-agent',
            role='reviewer',
            config='{"model": "claude-3"}',
            format='json',
            stdout=out,
        )

        agent = Agent.objects.get(agent_id='config-agent')
        assert agent.config == {'model': 'claude-3'}


# =============================================================================
# Test: expire_leases command
# =============================================================================


class TestExpireLeasesCommand:
    """Tests for expire_leases command."""

    @freeze_time('2025-01-15 12:00:00')
    def test_expire_leases__releases_expired(self, coder_agent, db):
        """Releases expired leases."""
        task = AgentTask.objects.create(
            external_id='task-expired',
            title='Expired',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
            lease_expires=timezone.now() - timedelta(minutes=5),
        )

        out = StringIO()
        call_command('expire_leases', format='json', stdout=out)
        data = json.loads(out.getvalue())

        assert data['expired_count'] == 1
        assert data['tasks'][0]['released'] is True

        task.refresh_from_db()
        assert task.status == AgentTaskStatus.UNCLAIMED

    @freeze_time('2025-01-15 12:00:00')
    def test_expire_leases__dry_run(self, coder_agent, db):
        """Dry run reports but doesn't modify."""
        task = AgentTask.objects.create(
            external_id='task-dry',
            title='Dry run',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
            lease_expires=timezone.now() - timedelta(minutes=5),
        )

        out = StringIO()
        call_command('expire_leases', dry_run=True, format='json', stdout=out)
        data = json.loads(out.getvalue())

        assert data['dry_run'] is True
        assert data['expired_count'] == 1
        assert data['tasks'][0]['released'] is False

        task.refresh_from_db()
        assert task.status == AgentTaskStatus.CLAIMED  # Unchanged

    @freeze_time('2025-01-15 12:00:00')
    def test_expire_leases__no_expired(self, coder_agent, db):
        """No expired leases reports zero."""
        AgentTask.objects.create(
            external_id='task-valid',
            title='Valid',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
            lease_expires=timezone.now() + timedelta(minutes=25),
        )

        out = StringIO()
        call_command('expire_leases', format='json', stdout=out)
        data = json.loads(out.getvalue())

        assert data['expired_count'] == 0
