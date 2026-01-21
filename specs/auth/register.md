---
id: REQ-AUTH-002
title: User Registration
tags: [auth, onboarding]
priority: high
status: active
parent: REQ-AUTH-001
verification_method: test
---

New users can create an account with email and password.

## Acceptance Criteria

- Email must be unique across all accounts
- Password must meet complexity requirements (8+ chars, mixed case, number)
- Confirmation email is sent after registration
