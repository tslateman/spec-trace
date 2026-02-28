---
id: REQ-WRK-001
title: Workspace Management
status: active
priority: high
tags: [core, workspaces]
---

# Workspace Management

Users collaborate within isolated environments called "Workspaces".

## Requirements

1. **Creation**: Any user with the `Tenant Admin` or `Member` role MUST be able to create a new Workspace.
2. **Limits**: The number of active Workspaces MUST be limited by the tenant's subscription tier (`max_workspaces` flag).
3. **Archiving**: Workspaces can be archived. Archived workspaces are read-only and do not count toward the subscription limit.
