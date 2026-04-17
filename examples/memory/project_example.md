---
name: Payments v2 Migration
description: Migrating payment flow from legacy endpoint to new provider
type: project
canonicality: state
---

# Payments v2 Migration

State-level file. Updates frequently during the migration window. Do **not** promote to `canonicality: knowledge` — this describes in-flight work that will be stale in 3 months.

If a durable principle emerges from this migration (e.g. "always run shadow mode for 7 days before cutover"), capture THAT in a separate `feedback_*.md` or `project_<principle>.md` file and promote that one.

## Current state

- **Goal:** Migrate all production traffic from Provider A to Provider B by 2026-06-01
- **Why:** Provider A is shutting down their v1 API
- **How to apply:** Flag any PR touching `payments/` — remind me to add shadow-mode logging
- **Blockers:** Waiting on Provider B's webhook spec clarification (ticketed as INFRA-4421)

## Timeline

| Date | Milestone |
|---|---|
| 2026-04-15 | Shadow mode live on 5% traffic |
| 2026-04-22 | Promote to 25% if no alerts |
| 2026-05-15 | Promote to 100%, keep legacy path as fallback |
| 2026-06-01 | Remove legacy path |
