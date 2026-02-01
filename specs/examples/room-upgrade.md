---
id: REQ-UPGRADE-001
title: Guest Room Upgrade Request
priority: medium
tags: [guest-services, upgrades]
verification_method: test
---

# Guest Room Upgrade Request

Guest can request a room upgrade through the mobile app.

## Scope

When guest has an active reservation.

## Condition

Guest taps "Request Upgrade" with a selected room type.

## Component

UpgradeService.create_request

## Response

System shall:
1. Create upgrade request with status=PENDING
2. Record requested room type and current room type
3. Notify front desk via internal queue
4. Return confirmation with request ID

## Timing

Within 500ms

## Acceptance Criteria

- Returns request_id when upgrade request created
- Sets status to PENDING
- Fails with INVALID_RESERVATION if reservation not found
- Fails with ALREADY_REQUESTED if pending request exists
