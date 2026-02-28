---
id: REQ-PLAT-001
title: Tenant Data Isolation
status: active
priority: high
tags: [platform, security, compliance]
---

# Tenant Data Isolation

To support a multi-tenant architecture securely, the system must logically isolate all customer data by a unique Tenant ID.

## Requirements

1. **Database Schema**: All application tables containing customer data MUST include a `tenant_id` foreign key.
2. **Query Scoping**: All database queries MUST automatically scope to the authenticated user's active `tenant_id`. No query should be able to read data across tenants unless executed by a system administrator role.
3. **API Validation**: Every incoming API request MUST validate that the requested resources belong to the `tenant_id` associated with the API key or JWT token.
4. **Storage Isolation**: Uploaded files and attachments MUST be stored in paths or buckets prefixed with the `tenant_id` (e.g., `s3://bucket-name/tenant_id/file.pdf`).

## Exceptions
- Global configuration data.
- System audit logs (which track the tenant ID but are managed globally).
