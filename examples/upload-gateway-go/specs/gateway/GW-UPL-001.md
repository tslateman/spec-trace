---
id: GW-UPL-001
title: Supported Media Types
tags: [gateway, uploads, validation]
priority: high
status: active
parent: GW-001
verification_method: test
---

The gateway admits the media types the pipeline can process and refuses the rest.

## Acceptance Criteria

- `application/pdf` is accepted
- `image/png` and `image/jpeg` are accepted
- `application/x-msdownload` is refused
- An empty media type is refused
