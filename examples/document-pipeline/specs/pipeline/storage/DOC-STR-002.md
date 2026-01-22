---
id: DOC-STR-002
title: Encryption at Rest
tags: [pipeline, storage, security, encryption]
priority: critical
status: active
parent: DOC-STR-001
verification_method: test
---

All stored documents must be encrypted at rest using industry-standard encryption.

## Acceptance Criteria

- Documents are encrypted with AES-256-GCM
- Encryption keys are managed via HSM-backed key management
- Each customer has isolated encryption keys
- Key rotation occurs automatically every 90 days
- Decryption requires authenticated access token
- Encryption/decryption overhead is <10ms for average document
