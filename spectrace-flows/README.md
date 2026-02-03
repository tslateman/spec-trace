# Spectrace Flows

Standalone verification flow engine for SpectTRACE.

## Installation

```bash
pip install spectrace-flows
```

## Usage

```python
from spectrace_flows import SequentialFlowEngine, FlowDef, FlowStepDef

# Define a flow
flow = FlowDef(
    name="api-health-check",
    display_name="API Health Check",
    description="Verify API connectivity",
    steps=[
        FlowStepDef(
            name="ping",
            handler="myapp.handlers.ping",
            display_name="Ping API",
        ),
    ],
)

# Execute with default in-memory storage
engine = SequentialFlowEngine()
result = engine.execute(flow, context={"base_url": "https://api.example.com"})

print(f"Flow {'passed' if result.status.value == 'passed' else 'failed'}")
```

## Django Integration

For Django projects, install with the Django extra:

```bash
pip install spectrace-flows[django]
```

Then use `DjangoFlowStorage` for persistence:

```python
from spectrace_flows import SequentialFlowEngine
from spectrace_flows.django_storage import DjangoFlowStorage

engine = SequentialFlowEngine(storage=DjangoFlowStorage())
```
