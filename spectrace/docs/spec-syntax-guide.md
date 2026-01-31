# Spec Syntax Guide

Write requirements using FRET-inspired structured fields. [FRET](https://github.com/NASA-SW-VnV/fret) is NASA's Formal Requirements Elicitation Tool for unambiguous requirements.

## The Formula

```
SCOPE + CONDITION + COMPONENT shall TIMING RESPONSE
```

*"When in scope, if condition, the component shall within timing respond."*

## Structured Fields

| Field | Question | Example |
|-------|----------|---------|
| **scope** | When does this apply? | `when in active_session` |
| **condition** | What triggers it? | `battery_level < 10%` |
| **component** | What system owns this? | `notification_service` |
| **timing** | Performance constraint? | `within 2 seconds` |
| **response** | What must happen? | `display low_battery_warning` |

All fields are optional. More fields = higher completeness score = better automated analysis.

## File Format

Requirements are Markdown files with YAML frontmatter in `specs/`:

```yaml
---
id: REQ-NOTIF-042
title: Low Battery Warning
priority: high
status: active
verification_method: both

# FRET structured fields
scope: when in active_session
condition: battery_level < 10%
component: notification_service
timing: within 2 seconds
response: display low_battery_warning AND vibrate_device
---

The system must warn users when battery is critically low.
```

### Required Fields

- `id` — Unique identifier (e.g., `REQ-AUTH-001`)
- `title` — Short descriptive title

### Metadata Fields

| Field | Values | Default |
|-------|--------|---------|
| `status` | `draft`, `active`, `deprecated` | `draft` |
| `priority` | `high`, `medium`, `low` | — |
| `verification_method` | `test`, `inapp`, `both` | `unspecified` |
| `tags` | list | — |
| `parent` | requirement ID | — |

## Hierarchical Requirements

Use `parent` to create requirement trees:

```yaml
# specs/mobile_key/index.md
---
id: REQ-MKEY-000
title: Mobile Key Feature
status: active
---

# specs/mobile_key/provisioning.md
---
id: REQ-MKEY-001
title: Key Provisioning
parent: REQ-MKEY-000
status: active
---
```

## Writing Tips

**Active voice.** "The system displays an error" not "An error is displayed."

**Specific timing.** `within 200ms` not `quickly`.

**Consistent naming.** Snake_case components matching your codebase: `auth_service`, `payment_gateway`.

**Evaluatable conditions.** `user.role == 'admin' AND feature_flag.enabled` not `when appropriate`.

## Conflict Detection

Structured fields enable automated conflict detection:

| Conflict Type | Detects |
|---------------|---------|
| Condition Overlap | Two requirements with overlapping conditions but different responses |
| Timing Conflict | Incompatible timing constraints on the same component |
| Response Contradiction | Same condition triggers contradictory responses |

Run detection:

```bash
python manage.py detect_conflicts --alert
```
