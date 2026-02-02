"""Django management command for running verification flows from CLI."""
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from requirements.flows.engine import SequentialFlowEngine
from requirements.models import (
    VerificationFlow,
    VerificationFlowSource,
    VerificationFlowStatus,
)


class Command(BaseCommand):
    """Run a verification flow by name or ID."""

    help = 'Run a verification flow by name or ID'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            'flow_id',
            type=str,
            help='Flow ID (numeric) or name (string)'
        )
        parser.add_argument(
            '--context',
            type=str,
            default='{}',
            help='JSON string with execution context'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=300,
            help='Flow timeout in seconds (default 300)'
        )
        parser.add_argument(
            '--step-timeout',
            type=int,
            default=60,
            help='Per-step timeout in seconds (default 60)'
        )

    def handle(self, *args, **options):
        """Execute the flow."""
        flow_id = options['flow_id']

        # Lookup flow by ID or name
        flow = self._lookup_flow(flow_id)

        # Parse context JSON
        context = self._parse_context(options['context'])

        # Execute flow
        engine = SequentialFlowEngine()
        run = engine.execute(
            flow=flow,
            context=context,
            source=VerificationFlowSource.MANUAL,
            step_timeout=options['step_timeout'],
            flow_timeout=options['timeout'],
        )

        # Output results
        self._output_results(flow, run)

        # Exit code based on status
        if run.status != VerificationFlowStatus.PASSED:
            sys.exit(1)

    def _lookup_flow(self, flow_id: str) -> VerificationFlow:
        """Look up flow by ID (numeric) or name (string).

        Args:
            flow_id: Flow identifier (numeric ID or name)

        Returns:
            VerificationFlow instance

        Raises:
            CommandError: If flow not found
        """
        # Try numeric ID first
        try:
            pk = int(flow_id)
            return VerificationFlow.objects.get(pk=pk)
        except ValueError:
            # Not numeric, try name lookup
            pass
        except VerificationFlow.DoesNotExist:
            # Numeric but not found, fall through to name lookup
            pass

        # Try name lookup
        try:
            return VerificationFlow.objects.get(name=flow_id)
        except VerificationFlow.DoesNotExist:
            raise CommandError(f"Flow not found: {flow_id}")

    def _parse_context(self, context_str: str) -> dict:
        """Parse JSON context string.

        Args:
            context_str: JSON string

        Returns:
            Parsed dictionary

        Raises:
            CommandError: If JSON is invalid
        """
        try:
            return json.loads(context_str)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON context: {e}")

    def _output_results(self, flow: VerificationFlow, run) -> None:
        """Output flow execution results.

        Args:
            flow: The executed flow
            run: The VerificationFlowRun instance
        """
        # Header
        self.stdout.write(f"\nFlow: {flow.display_name} ({flow.name})")

        # Status with appropriate styling
        if run.status == VerificationFlowStatus.PASSED:
            status_str = self.style.SUCCESS(f"Status: {run.status}")
        else:
            status_str = self.style.WARNING(f"Status: {run.status}")
        self.stdout.write(status_str)

        # Duration
        if run.duration_ms is not None:
            self.stdout.write(f"Duration: {run.duration_ms}ms")

        # Steps
        self.stdout.write("\nSteps:")
        for step in run.steps.order_by('step_order'):
            if step.passed:
                status_marker = self.style.SUCCESS("[PASS]")
                self.stdout.write(f"  {status_marker} {step.name}")
                if step.details:
                    self.stdout.write(f"         Details: {step.details}")
            else:
                status_marker = self.style.ERROR("[FAIL]")
                self.stdout.write(f"  {status_marker} {step.name}")
                if step.error_message:
                    self.stdout.write(f"         Error: {step.error_message}")

        self.stdout.write("")  # Trailing newline
