---
id: DOC-ING-002
title: File Type Validation
tags: [pipeline, ingest, validation, security]
priority: high
status: active
parent: DOC-ING-001
verification_method: test
---

The system validates uploaded file types to ensure only allowed formats are processed.

## Acceptance Criteria

- PDF files (.pdf) are accepted
- Microsoft Word files (.docx) are accepted
- Image files (.png, .jpg, .jpeg, .tiff) are accepted
- Executable files (.exe, .bat, .sh) are rejected
- Files with mismatched extensions and MIME types are rejected
- Zero-byte files are rejected
- Oversized files (>100MB) are rejected with size error
