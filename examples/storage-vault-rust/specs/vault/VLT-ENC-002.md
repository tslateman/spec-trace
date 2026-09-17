---
id: VLT-ENC-002
title: Key Identifier
tags: [vault, encryption, rotation]
priority: high
status: active
parent: VLT-001
verification_method: test
---

Every sealed document names the key that sealed it, so a rotation can find the
documents it must reseal.

## Acceptance Criteria

- A sealed document carries a key identifier
- Documents sealed under different keys carry different identifiers
