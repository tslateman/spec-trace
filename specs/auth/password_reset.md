---
id: REQ-AUTH-003
title: Password Reset
tags: [auth, security]
priority: high
status: active
parent: REQ-AUTH-001
verification_method: test
---

Users can reset their password if forgotten.

## Acceptance Criteria

- User requests reset via email address
- Reset link is sent to verified email
- Link expires after 24 hours
- Old sessions are invalidated after password change
