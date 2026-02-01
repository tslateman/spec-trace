# Flow Status Dashboard Demo

## Overview

Demonstrate the flow status dashboard for visualizing multi-step verification flows.

---

## Setup (before demo)

Run the setup command:

```bash
python manage.py setup_flow_demo --clear
```

This creates 3 runs for the Linear Connection flow:
- **Run passed** (all 3 steps) - shows full pipeline success
- **Run failed at auth** (step 2) - shows early exit behavior
- **Run failed at config** (step 1) - shows config error

### Manual Setup (alternative)

```python
# In Django shell (python manage.py shell)
from requirements.flows.definitions import LINEAR_CONNECTION_FLOW
from requirements.models import VerificationFlow, VerificationFlowRun, VerificationFlowStep, VerificationFlowStatus, VerificationFlowSource
from django.utils import timezone
from datetime import timedelta

# Sync flow to DB
flow, _ = VerificationFlow.objects.update_or_create(
    name=LINEAR_CONNECTION_FLOW.name,
    defaults={
        'display_name': LINEAR_CONNECTION_FLOW.display_name,
        'description': LINEAR_CONNECTION_FLOW.description,
        'steps': [{'name': s.name, 'handler': s.handler, 'display_name': s.display_name} for s in LINEAR_CONNECTION_FLOW.steps],
        'version': LINEAR_CONNECTION_FLOW.version,
        'synced_at': timezone.now(),
    }
)

# Create a run that fails at step 2 (auth)
run = VerificationFlowRun.objects.create(
    flow=flow, status=VerificationFlowStatus.FAILED,
    source=VerificationFlowSource.MANUAL,
    completed_at=timezone.now()
)

steps = [
    ('config', True, 'LINEAR_API_KEY present, format valid', ''),
    ('auth', False, '', 'Authentication failed: API key rejected'),
]
for i, (name, passed, details, error) in enumerate(steps):
    VerificationFlowStep.objects.create(
        flow_run=run, step_order=i, name=name, passed=passed,
        details=details, error_message=error,
        started_at=timezone.now() - timedelta(seconds=10-i),
        completed_at=timezone.now() - timedelta(seconds=9-i),
    )
```

---

## Demo Script (3 minutes)

### 1. Dashboard Entry (30s)

- Start at `/admin/` home
- Point out "Flow Status" button in Quick Actions
- Click it

### 2. Flow List Overview (45s)

- Show summary stats: flows with pass/fail status
- Linear Connection: pipeline preview shows 3 steps
- "This gives at-a-glance health for all verification flows"

### 3. Drill into Runs (30s)

- Click "All Runs" on a flow
- Shows run history table with status, duration, step counts
- Pipeline reference shows the step sequence

### 4. Run Detail - The Money Shot (60s)

- Click into a run
- **Pipeline visualization**: boxes show pass/fail per step
- Config ✓, Auth ✗ (red), Permissions grayed out
- Remaining steps grayed out (early exit)
- Expand failed step → shows error details
- "Expand All" button for debugging sessions
- Previous/Next navigation between runs

### 5. Wrap Up (15s)

- Breadcrumbs show full navigation path
- Link back to all flows
- "Perfect for debugging multi-step integrations"

---

## Key Points to Highlight

- **Pipeline visualization** catches the eye
- **Early-exit behavior** visible (steps after failure are pending)
- **Expandable details** for debugging without clutter
- **Stats roll up** from individual steps → runs → flows

---

## URLs

| View | URL |
|------|-----|
| Flow list | `/admin/flow-status/` |
| Linear runs | `/admin/flow-status/linear-connection/` |
| Run detail | `/admin/flow-status/run/<id>/` |

---

## Quick Start

```bash
# Set up demo data
python manage.py setup_flow_demo --clear

# Start server
python manage.py runserver

# Open browser
open http://localhost:8000/admin/flow-status/
```
