---
id: COM-BILL-001
kind: commitment
title: Invoice accuracy guarantee
version: 1
status: active
supersedes: null
effective: 2026-01-20
owner: billing
applies_to:
  tags: [billing, finance]
  components: [invoicing]
  paths: ["specs/billing/**"]
  requirement_ids: ["REQ-BILL-002"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
  - id: accuracy-tested
    assert: verification_method in [test, both]
  - id: slo-linked
    assert: slo_status != not_linked
---

We tell enterprise customers that a published invoice is final and that any
billing correction is issued as a credit note, never as a silent restatement.

Any spec that changes how an invoice line is computed MUST state its effect on
already-published invoices and MUST link the SLO that measures billing accuracy.
