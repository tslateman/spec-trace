---
id: VLT-ENC-001
title: Seal On Write
tags: [vault, encryption, security]
priority: high
status: active
parent: VLT-001
verification_method: test
---

The vault seals a document before storing it, so the stored bytes never match
the plaintext.

## Acceptance Criteria

- Stored bytes differ from the plaintext
- Opening a sealed document returns the original plaintext
- Opening with the wrong key fails
