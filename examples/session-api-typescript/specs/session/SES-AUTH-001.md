---
id: SES-AUTH-001
title: Issue A Session
tags: [session, auth]
priority: high
status: active
parent: SES-001
verification_method: test
---

A caller who presents the right password receives a session token naming the
account it belongs to.

## Acceptance Criteria

- A correct password issues a token
- The token names its subject
- A wrong password issues no token
