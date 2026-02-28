---
id: REQ-IAM-002
title: Role-Based Access Control (RBAC)
status: active
priority: high
tags: [identity, security, permissions]
---

# Role-Based Access Control (RBAC)

The system must support granular permissions to ensure users only have access to resources necessary for their job function.

## Requirements

1. **Standard Roles**: The system MUST ship with the following built-in roles:
   - `Tenant Admin`: Full access to tenant settings, billing, and user management.
   - `Member`: Standard read/write access to business resources.
   - `Viewer`: Read-only access to business resources.
2. **Permission Checks**: All backend API endpoints MUST enforce permission checks before executing any read or write operation.
3. **Custom Roles**: Enterprise tier tenants MUST be able to define custom roles by selecting a subset of granular permissions.
