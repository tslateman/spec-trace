---
id: REQ-PLAT-002
title: System Audit Logging
status: active
priority: medium
tags: [platform, security, compliance]
parent: REQ-PLAT-001
---

# System Audit Logging

To maintain compliance and allow security investigations, all significant system events must be recorded in an immutable audit log.

## Requirements

1. **Event Capture**: The system MUST log the following events:
   - Successful and failed login attempts.
   - User creation, deletion, or role changes.
   - API key generation or revocation.
   - Data exports or bulk deletions.
2. **Log Metadata**: Each log entry MUST include:
   - Timestamp (UTC)
   - Actor ID (User ID or Service Account ID)
   - Tenant ID
   - IP Address
   - Action type (e.g., `user.created`)
   - Resource ID (e.g., the ID of the user that was created)
3. **Immutability**: Audit logs MUST be write-only and stored in a database or system where modification by application code is impossible.
4. **Retention**: Logs MUST be retained for a minimum of 365 days.
