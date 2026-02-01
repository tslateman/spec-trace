"""Tests for invariant checking logic."""

import pytest
from django.utils import timezone

from requirements.invariants import (
    InvariantCheckResult,
    InvariantViolation,
    check_all_invariants,
    check_inv_a_status_consistency,
    check_inv_b_slo_override,
    check_inv_d_link_uniqueness,
    check_inv_e_review_flag,
    check_inv_f_flow_completion,
    check_inv_g_claimed_has_agent,
    check_inv_h_claimed_has_lease,
    check_inv_i_nondraft_has_history,
    check_inv_j_approved_has_review,
    check_inv_k_no_self_review,
)
from requirements.models import (
    Agent,
    AgentRole,
    AgentTask,
    AgentTaskHistory,
    AgentTaskReview,
    AgentTaskStatus,
    Requirement,
    ReviewDecision,
    SLOStatus,
    TestRequirementLink,
    TestResult,
    TestRun,
    VerificationFlow,
    VerificationFlowRun,
    VerificationFlowStatus,
)


@pytest.fixture
def requirement(db):
    """Create a basic requirement."""
    return Requirement.add_root(
        external_id='REQ-001',
        title='Test Requirement',
        status='active',
        source_file='test.md',
        verification_status='passing',
    )


@pytest.fixture
def test_run(db):
    """Create a test run."""
    return TestRun.objects.create(source_file='results.xml')


class TestInvAStatusConsistency:
    """Tests for INV-A: status matches computed status."""

    @pytest.mark.django_db
    def test_check_inv_a__passes_when_status_matches(self, requirement, test_run):
        """No violation when stored status matches computed status."""
        # Create passing test result
        result_obj = TestResult.objects.create(
            test_run=test_run,
            test_nodeid='test.py::test_one',
            name='test_one',
            status='passed',
        )
        result_obj.requirements.add(requirement)

        result = check_inv_a_status_consistency(test_run)

        assert not result.has_violations
        assert result.checks_performed == 1

    @pytest.mark.django_db
    def test_check_inv_a__detects_mismatch(self, requirement, test_run):
        """Violation when stored status differs from computed."""
        # Create failing test but leave requirement as 'passing'
        result_obj = TestResult.objects.create(
            test_run=test_run,
            test_nodeid='test.py::test_one',
            name='test_one',
            status='failed',
        )
        result_obj.requirements.add(requirement)

        result = check_inv_a_status_consistency(test_run)

        assert result.has_violations
        assert len(result.violations) == 1
        assert result.violations[0].code == 'INV-A'
        assert result.violations[0].requirement_id == 'REQ-001'
        assert result.violations[0].details['stored_status'] == 'passing'
        assert result.violations[0].details['computed_status'] == 'failing'

    @pytest.mark.django_db
    def test_check_inv_a__fix_updates_status(self, requirement, test_run):
        """Fix mode updates stored status to match computed."""
        result_obj = TestResult.objects.create(
            test_run=test_run,
            test_nodeid='test.py::test_one',
            name='test_one',
            status='failed',
        )
        result_obj.requirements.add(requirement)

        result = check_inv_a_status_consistency(test_run, fix=True)

        assert result.fixed_count == 1
        requirement.refresh_from_db()
        assert requirement.verification_status == 'failing'


class TestInvBSloOverride:
    """Tests for INV-B: breached SLO forces failing status."""

    @pytest.mark.django_db
    def test_check_inv_b__passes_when_breached_is_failing(self, requirement):
        """No violation when breached SLO requirement is failing."""
        requirement.slo_status = SLOStatus.BREACHED
        requirement.verification_status = 'failing'
        requirement.save()

        result = check_inv_b_slo_override()

        assert not result.has_violations

    @pytest.mark.django_db
    def test_check_inv_b__detects_breached_but_not_failing(self, requirement):
        """Violation when breached SLO but status is not failing."""
        requirement.slo_status = SLOStatus.BREACHED
        requirement.verification_status = 'passing'
        requirement.save()

        result = check_inv_b_slo_override()

        assert result.has_violations
        assert len(result.violations) == 1
        assert result.violations[0].code == 'INV-B'
        assert result.violations[0].requirement_id == 'REQ-001'

    @pytest.mark.django_db
    def test_check_inv_b__fix_sets_failing(self, requirement):
        """Fix mode sets status to failing."""
        requirement.slo_status = SLOStatus.BREACHED
        requirement.verification_status = 'passing'
        requirement.save()

        result = check_inv_b_slo_override(fix=True)

        assert result.fixed_count == 1
        requirement.refresh_from_db()
        assert requirement.verification_status == 'failing'


class TestInvDLinkUniqueness:
    """Tests for INV-D: unique links per (test, requirement) pair."""

    @pytest.mark.django_db
    def test_check_inv_d__passes_with_unique_links(self, requirement):
        """No violation when all links are unique."""
        TestRequirementLink.objects.create(
            test_nodeid='test.py::test_one',
            requirement=requirement,
        )

        result = check_inv_d_link_uniqueness()

        assert not result.has_violations


class TestInvEReviewFlag:
    """Tests for INV-E: regression sets needs_review flag."""

    @pytest.mark.django_db
    def test_check_inv_e__passes_when_flagged(self, requirement):
        """No violation when failed link is flagged for review."""
        TestRequirementLink.objects.create(
            test_nodeid='test.py::test_one',
            requirement=requirement,
            last_status='failed',
            needs_review=True,
        )

        result = check_inv_e_review_flag()

        assert not result.has_violations

    @pytest.mark.django_db
    def test_check_inv_e__detects_unflagged_failure(self, requirement):
        """Warning when failed link is not flagged."""
        TestRequirementLink.objects.create(
            test_nodeid='test.py::test_one',
            requirement=requirement,
            last_status='failed',
            needs_review=False,
        )

        result = check_inv_e_review_flag()

        assert result.has_violations
        assert len(result.violations) == 1
        assert result.violations[0].code == 'INV-E'
        assert result.violations[0].severity == 'warning'

    @pytest.mark.django_db
    def test_check_inv_e__fix_sets_review_flag(self, requirement):
        """Fix mode sets needs_review flag."""
        link = TestRequirementLink.objects.create(
            test_nodeid='test.py::test_one',
            requirement=requirement,
            last_status='failed',
            needs_review=False,
        )

        result = check_inv_e_review_flag(fix=True)

        assert result.fixed_count == 1
        link.refresh_from_db()
        assert link.needs_review is True


class TestInvFFlowCompletion:
    """Tests for INV-F: flow run completion consistency."""

    @pytest.fixture
    def flow(self, db):
        """Create a verification flow."""
        return VerificationFlow.objects.create(
            name='test-flow',
            display_name='Test Flow',
        )

    @pytest.mark.django_db
    def test_check_inv_f__passes_when_consistent(self, flow):
        """No violation when completion state is consistent."""
        # Running without completed_at
        VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.RUNNING,
            completed_at=None,
        )

        # Passed with completed_at
        VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.PASSED,
            completed_at=timezone.now(),
        )

        result = check_inv_f_flow_completion()

        assert not result.has_violations

    @pytest.mark.django_db
    def test_check_inv_f__detects_running_with_timestamp(self, flow):
        """Violation when running status has completed_at."""
        VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.RUNNING,
            completed_at=timezone.now(),  # Should be None
        )

        result = check_inv_f_flow_completion()

        assert result.has_violations
        assert result.violations[0].code == 'INV-F'

    @pytest.mark.django_db
    def test_check_inv_f__detects_passed_without_timestamp(self, flow):
        """Violation when passed status has no completed_at."""
        VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.PASSED,
            completed_at=None,  # Should have timestamp
        )

        result = check_inv_f_flow_completion()

        assert result.has_violations
        assert result.violations[0].code == 'INV-F'


class TestCheckAllInvariants:
    """Tests for the combined invariant checker."""

    @pytest.mark.django_db
    def test_check_all__aggregates_results(self, requirement, test_run):
        """All checks run and results are combined."""
        result = check_all_invariants(test_run)

        # Should have performed checks (exact count depends on data)
        assert result.checks_performed > 0

    @pytest.mark.django_db
    def test_check_all__respects_fix_flag(self, requirement):
        """Fix flag is passed to individual checks."""
        requirement.slo_status = SLOStatus.BREACHED
        requirement.verification_status = 'passing'
        requirement.save()

        result = check_all_invariants(fix=True)

        assert result.fixed_count >= 1
        requirement.refresh_from_db()
        assert requirement.verification_status == 'failing'


class TestInvariantCheckResult:
    """Tests for the InvariantCheckResult dataclass."""

    def test_to_dict__serializes_correctly(self):
        """Result converts to JSON-compatible dict."""
        result = InvariantCheckResult(
            violations=[
                InvariantViolation(
                    code='INV-A',
                    requirement_id='REQ-001',
                    message='Test message',
                    severity='error',
                    details={'key': 'value'},
                    fixable=True,
                )
            ],
            checks_performed=10,
            fixed_count=1,
        )

        data = result.to_dict()

        assert data['summary']['checks_performed'] == 10
        assert data['summary']['total_violations'] == 1
        assert data['summary']['errors'] == 1
        assert data['summary']['warnings'] == 0
        assert data['summary']['fixed'] == 1
        assert data['violations'][0]['code'] == 'INV-A'
        assert data['violations'][0]['fixable'] is True
        assert data['violations'][0]['key'] == 'value'


# =============================================================================
# Agent Task Invariants (INV-G through INV-K)
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


class TestInvGClaimedHasAgent:
    """Tests for INV-G: Claimed tasks have claimed_by set."""

    @pytest.mark.django_db
    def test_check_inv_g__passes_with_agent(self, coder_agent):
        """No violation when claimed task has claimed_by."""
        AgentTask.objects.create(
            external_id='task-001',
            title='Test',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
        )

        result = check_inv_g_claimed_has_agent()

        assert not result.has_violations

    @pytest.mark.django_db
    def test_check_inv_g__detects_orphan_task(self, db):
        """Violation when claimed task has no claimed_by."""
        AgentTask.objects.create(
            external_id='task-orphan',
            title='Orphan',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=None,
        )

        result = check_inv_g_claimed_has_agent()

        assert result.has_violations
        assert len(result.violations) == 1
        assert result.violations[0].code == 'INV-G'
        assert result.violations[0].requirement_id == 'task-orphan'

    @pytest.mark.django_db
    def test_check_inv_g__checks_in_progress_too(self, db):
        """Also checks IN_PROGRESS tasks."""
        AgentTask.objects.create(
            external_id='task-in-progress',
            title='In Progress',
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=None,
        )

        result = check_inv_g_claimed_has_agent()

        assert result.has_violations
        assert result.violations[0].code == 'INV-G'


class TestInvHClaimedHasLease:
    """Tests for INV-H: CLAIMED status has lease_expires."""

    @pytest.mark.django_db
    def test_check_inv_h__passes_with_lease(self, coder_agent):
        """No violation when claimed task has lease_expires."""
        AgentTask.objects.create(
            external_id='task-001',
            title='Test',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
            lease_expires=timezone.now(),
        )

        result = check_inv_h_claimed_has_lease()

        assert not result.has_violations

    @pytest.mark.django_db
    def test_check_inv_h__detects_no_lease(self, coder_agent):
        """Violation when claimed task has no lease_expires."""
        AgentTask.objects.create(
            external_id='task-no-lease',
            title='No Lease',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
            lease_expires=None,
        )

        result = check_inv_h_claimed_has_lease()

        assert result.has_violations
        assert len(result.violations) == 1
        assert result.violations[0].code == 'INV-H'


class TestInvINondraftHasHistory:
    """Tests for INV-I: Non-draft tasks have history entry."""

    @pytest.mark.django_db
    def test_check_inv_i__passes_with_history(self, coder_agent):
        """No violation when non-draft task has history."""
        task = AgentTask.objects.create(
            external_id='task-001',
            title='Test',
            status=AgentTaskStatus.CLAIMED,
            claimed_by=coder_agent,
        )
        AgentTaskHistory.objects.create(
            task=task,
            agent=coder_agent,
            action='CLAIMED',
            from_status='unclaimed',
            to_status='claimed',
        )

        result = check_inv_i_nondraft_has_history()

        assert not result.has_violations

    @pytest.mark.django_db
    def test_check_inv_i__detects_no_history(self, db):
        """Warning when non-draft task has no history."""
        AgentTask.objects.create(
            external_id='task-no-history',
            title='No History',
            status=AgentTaskStatus.UNCLAIMED,  # Non-draft
        )

        result = check_inv_i_nondraft_has_history()

        assert result.has_violations
        assert result.violations[0].code == 'INV-I'
        assert result.violations[0].severity == 'warning'

    @pytest.mark.django_db
    def test_check_inv_i__ignores_draft(self, db):
        """Draft tasks without history are not violations."""
        AgentTask.objects.create(
            external_id='task-draft',
            title='Draft',
            status=AgentTaskStatus.DRAFT,
        )

        result = check_inv_i_nondraft_has_history()

        assert not result.has_violations


class TestInvJApprovedHasReview:
    """Tests for INV-J: Approved tasks have approved review."""

    @pytest.mark.django_db
    def test_check_inv_j__passes_with_review(self, coder_agent, reviewer_agent):
        """No violation when approved task has approved review."""
        task = AgentTask.objects.create(
            external_id='task-approved',
            title='Approved',
            status=AgentTaskStatus.APPROVED,
            claimed_by=coder_agent,
        )
        AgentTaskReview.objects.create(
            task=task,
            reviewer=reviewer_agent,
            decision=ReviewDecision.APPROVED,
            commit_sha='abc123',
        )

        result = check_inv_j_approved_has_review()

        assert not result.has_violations

    @pytest.mark.django_db
    def test_check_inv_j__detects_missing_review(self, db):
        """Violation when approved task has no approved review."""
        AgentTask.objects.create(
            external_id='task-no-review',
            title='No Review',
            status=AgentTaskStatus.APPROVED,
        )

        result = check_inv_j_approved_has_review()

        assert result.has_violations
        assert result.violations[0].code == 'INV-J'

    @pytest.mark.django_db
    def test_check_inv_j__checks_merged_too(self, db):
        """Also checks MERGED tasks."""
        AgentTask.objects.create(
            external_id='task-merged',
            title='Merged',
            status=AgentTaskStatus.MERGED,
        )

        result = check_inv_j_approved_has_review()

        assert result.has_violations
        assert result.violations[0].code == 'INV-J'


class TestInvKNoSelfReview:
    """Tests for INV-K: Reviewers can't review own work."""

    @pytest.mark.django_db
    def test_check_inv_k__passes_different_reviewer(self, coder_agent, reviewer_agent):
        """No violation when reviewer differs from worker."""
        task = AgentTask.objects.create(
            external_id='task-001',
            title='Test',
            status=AgentTaskStatus.APPROVED,
            claimed_by=coder_agent,
        )
        AgentTaskReview.objects.create(
            task=task,
            reviewer=reviewer_agent,
            decision=ReviewDecision.APPROVED,
            commit_sha='abc123',
        )

        result = check_inv_k_no_self_review()

        assert not result.has_violations

    @pytest.mark.django_db
    def test_check_inv_k__detects_self_review(self, db):
        """Violation when reviewer is same as worker."""
        agent = Agent.objects.create(
            agent_id='dual-agent',
            role=AgentRole.REVIEWER,
            is_active=True,
        )
        task = AgentTask.objects.create(
            external_id='task-self',
            title='Self Review',
            status=AgentTaskStatus.APPROVED,
            claimed_by=agent,
        )
        AgentTaskReview.objects.create(
            task=task,
            reviewer=agent,  # Same as claimed_by
            decision=ReviewDecision.APPROVED,
            commit_sha='abc123',
        )

        result = check_inv_k_no_self_review()

        assert result.has_violations
        assert result.violations[0].code == 'INV-K'
        assert 'dual-agent' in result.violations[0].message
