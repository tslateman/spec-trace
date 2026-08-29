---
id: REQ-BILL-002
title: Usage-Based Invoicing
status: active
priority: medium
tags: [billing, finance]
parent: REQ-BILL-001
complies_with:
  - DEC-BILL-001@1
  - DEC-BILL-002@1
---

# Usage-Based Invoicing

In addition to base subscription fees, the system must support metered billing for specific resources.

## Requirements

1. **Usage Aggregation**: A cron job MUST run daily to aggregate usage metrics (e.g., API calls, storage used) for each active tenant.
2. **Invoice Generation**: On the billing cycle anchor date, the system MUST generate a PDF invoice detailing both the base subscription fee and any usage overages.
3. **Payment Collection**: If the tenant has a card on file (e.g., via Stripe), the system MUST automatically attempt to charge the total invoice amount.
4. **Dunning**: If payment fails, the system MUST send up to 3 reminder emails over 14 days before automatically pausing the subscription.
