---
id: SAMPLE-AUTH-001-001
title: User Login Story
parent: SAMPLE-AUTH-001
tags: [story, auth, login, sample]
priority: high
status: active
verification_method: test
---

As a user, I want to log in with my email and password so that I can access my account.

## Acceptance Criteria

- Valid credentials grant access to the application
- Invalid credentials show a clear error message without leaking information
- Failed login attempts are rate-limited (max 5 per minute per IP)
- Session is created on successful login with secure cookie flags
- Login endpoint returns appropriate HTTP status codes (200, 401, 429)
