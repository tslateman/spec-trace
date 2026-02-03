---
id: SAMPLE-API-001-001
title: Create Resource Story
parent: SAMPLE-API-001
tags: [story, api, create, sample]
priority: high
status: active
verification_method: test
---

As an API consumer, I want to create new resources via POST request so that I can add data to the system.

## Acceptance Criteria

- POST /api/resources creates a new resource with valid JSON payload
- Required fields are validated (name, type, owner_id)
- Created resource is assigned a unique ID and timestamp
- Response returns 201 Created with full resource representation
- Invalid payloads return 400 Bad Request with validation error details
- Unauthenticated requests return 401 Unauthorized
