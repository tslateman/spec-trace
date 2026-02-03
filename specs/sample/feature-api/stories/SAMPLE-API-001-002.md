---
id: SAMPLE-API-001-002
title: List Resources Story
parent: SAMPLE-API-001
tags: [story, api, list, pagination, sample]
priority: high
status: active
verification_method: test
---

As an API consumer, I want to list resources via GET request so that I can retrieve data from the system.

## Acceptance Criteria

- GET /api/resources returns paginated list of resources
- Default page size is 20, configurable via ?page_size= parameter (max 100)
- Response includes pagination metadata (total_count, page, page_size, next, previous)
- Results can be filtered by owner_id and type query parameters
- Only resources the user has permission to view are returned
- Empty results return 200 OK with empty array (not 404)
- Unauthenticated requests return 401 Unauthorized
