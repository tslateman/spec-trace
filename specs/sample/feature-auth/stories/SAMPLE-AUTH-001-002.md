---
id: SAMPLE-AUTH-001-002
title: Password Reset Story
parent: SAMPLE-AUTH-001
tags: [story, auth, password-reset, sample]
priority: medium
status: active
verification_method: test
---

As a user, I want to reset my password when I forget it so that I can regain access to my account.

## Acceptance Criteria

- Users can request a password reset link via email
- Reset links expire after 1 hour
- Reset links are single-use only
- Email addresses are not disclosed (same response for valid/invalid emails)
- Password strength requirements are enforced during reset (min 8 chars, mixed case, numbers)
- Successfully reset password invalidates all existing sessions
