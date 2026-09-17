---
id: SES-TTL-001
title: Session Expiry
tags: [session, security]
priority: medium
status: active
parent: SES-001
verification_method: test
---

A session token lives for one hour.

## Acceptance Criteria

- A token inside its hour resolves to its subject
- A token past its hour resolves to nothing
