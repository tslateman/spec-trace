---
id: DOC-TRF-002
title: PDF Conversion
tags: [pipeline, transform, pdf]
priority: high
status: active
parent: DOC-TRF-001
verification_method: test
---

Non-PDF documents are converted to PDF format for standardized viewing.

## Acceptance Criteria

- DOCX files convert to PDF with formatting preserved
- Image files (PNG, JPG) convert to single-page PDFs
- Multi-page TIFF files convert to multi-page PDFs
- Conversion maintains text selectability where possible
- Embedded fonts are preserved or substituted appropriately
- Conversion errors are logged with source file reference
