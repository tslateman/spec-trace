---
id: GW-UPL-002
title: Upload Size Cap
tags: [gateway, uploads, limits]
priority: high
status: active
parent: GW-001
verification_method: test
---

The gateway caps a single upload at 100 MB.

## Acceptance Criteria

- An upload of exactly 100 MB is accepted
- An upload of 100 MB plus one byte is refused
- A zero-byte upload is refused
