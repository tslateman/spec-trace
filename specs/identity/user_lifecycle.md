---
id: REQ-IAM-003
title: User Lifecycle Management
status: active
priority: medium
tags: [identity, user_management]
---

# User Lifecycle Management

The system must provide tools for managing the lifecycle of a user within a tenant.

## Requirements

1. **Invitations**: Tenant admins MUST be able to invite users via email.
2. **Deactivation**: Admins MUST be able to deactivate a user. Deactivated users MUST immediately lose all access and API tokens MUST be revoked.
3. **Offboarding**: The system MUST support SCIM 2.0 for automated user provisioning and deprovisioning from standard enterprise IdPs (e.g., Okta, Azure AD).
