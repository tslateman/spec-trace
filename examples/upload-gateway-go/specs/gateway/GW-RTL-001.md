---
id: GW-RTL-001
title: Per-Tenant Rate Limit
tags: [gateway, limits]
priority: medium
status: active
parent: GW-001
verification_method: test
---

Each tenant may start 5 uploads per window. The sixth waits for the next window.

## Acceptance Criteria

- The first 5 uploads in a window are admitted
- The sixth upload in the same window is refused
- A new window restores the full budget
- One tenant's budget leaves another tenant's untouched
