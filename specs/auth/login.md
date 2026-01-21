---
id: REQ-AUTH-001
title: User Login
tags: [auth, security]
priority: high
status: active
verification_method: test
---

Users must be able to log in with email and password.

## Acceptance Criteria

- Valid credentials grant access to the application
- Invalid credentials show a clear error message
- Failed login attempts are rate-limited (max 5 per minute)
- Session is created on successful login
