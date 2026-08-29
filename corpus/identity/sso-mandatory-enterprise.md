---
id: DEC-IAM-001
kind: decision
title: SAML and OIDC only for enterprise identity federation
version: 2
status: active
supersedes: null
effective: 2026-01-08
owner: identity
applies_to:
  tags: [identity, enterprise]
  components: [auth]
  paths: ["specs/identity/**"]
  requirement_ids: ["REQ-IAM-001"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
  - id: federation-tested
    assert: verification_method in [test, both]
  - id: owning-component-named
    assert: component is set
---

We federate enterprise identity through SAML 2.0 and OIDC. We do not build
per-vendor connectors, and we do not accept LDAP bind credentials.

Rejected alternatives: a hosted directory sync service (adds a credential store
we would have to secure) and per-tenant custom connectors (unbounded support
cost). Any spec proposing a third federation protocol reopens this decision.
