---
name: External System Pointers
description: Where to look for things that live outside this project
type: reference
canonicality: reference
---

# External References

Pointers to systems that hold authoritative data Claude can't read directly. Claude uses these when you mention an external topic, so it can direct you to the right source instead of guessing.

## Examples

- **Bug tracking:** All pipeline bugs live in Linear project `INGEST`. Pull a ticket with `gh api linear ...` (or use the Linear MCP if installed).
- **Ops dashboards:** Request-latency oncall dashboard: `grafana.internal/d/api-latency`. Check this before/after any request-path change.
- **Team communication:** Architecture decisions are discussed in Slack `#eng-architecture` before they land in a PR. If I suggest a large refactor, remind me to post there first.
