---
id: SES-AUTH-002
title: Refuse A Locked Account
tags: [session, auth, security]
priority: high
status: active
parent: SES-001
verification_method: test
---

A locked account receives no session token, whatever password it presents.

## Acceptance Criteria

- A locked account with the right password receives no token
- Unlocking the account restores sign-in
