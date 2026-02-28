---
id: REQ-BILL-001
title: Subscription Tiers
status: active
priority: high
tags: [billing, subscriptions]
---

# Subscription Tiers

The platform operates on a tiered SaaS subscription model.

## Requirements

1. **Plans**: The system MUST support at least three tiers: Free, Pro, and Enterprise.
2. **Feature Flags**: Each tier MUST define a set of boolean or quantitative feature flags (e.g., `can_export_data: true`, `max_users: 50`).
3. **Enforcement**: The application code MUST verify the tenant's current active subscription feature flags before allowing restricted actions.
4. **Upgrades/Downgrades**: Tenants MUST be able to self-serve upgrades. Downgrades MUST take effect at the end of the current billing cycle.
