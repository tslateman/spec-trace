---
id: DOC-TRF-003
title: Image Optimization
tags: [pipeline, transform, images, optimization]
priority: medium
status: active
parent: DOC-TRF-001
verification_method: test
---

Images are optimized for efficient web delivery while maintaining acceptable quality.

## Acceptance Criteria

- Generates thumbnail (150px), preview (800px), and full-size variants
- Applies lossy compression to reduce file size by 60-80%
- Converts to WebP format with JPEG fallback
- Preserves aspect ratio during resizing
- Strips unnecessary metadata from optimized versions
- Maintains original image in cold storage
