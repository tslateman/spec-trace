---
id: DEC-BILL-001
kind: decision
title: Nightly batch rollup as the metering source of truth
version: 1
status: superseded
supersedes: null
effective: 2025-09-01
owner: billing
enforcement: advisory
applies_to:
  tags: [billing, finance]
  components: [metering]
  paths: ["specs/billing/**"]
  requirement_ids: ["REQ-BILL-002"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high, medium]
---

Usage counters are aggregated by a nightly batch job. The batch output is the
billable record; the event stream is advisory only.

Superseded by DEC-BILL-002, which moved the source of truth to the event stream
after the batch job dropped a day of usage during the 2025-11 incident.
