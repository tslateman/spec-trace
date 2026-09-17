---
id: VLT-RET-001
title: Retention Window
tags: [vault, retention, compliance]
priority: medium
status: active
parent: VLT-001
verification_method: test
---

A document lives for the retention window its tier grants and no longer.

## Acceptance Criteria

- A document inside its window is readable
- A document past its window is gone
- Sweeping the vault removes only the expired documents
