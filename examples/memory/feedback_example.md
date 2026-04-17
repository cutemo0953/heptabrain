---
name: Integration tests must use real database
description: Don't mock the DB in integration tests — catches migration drift
type: feedback
canonicality: reference
---

Integration tests must hit a real database (docker compose or emulator), not mocks.

**Why:** Last quarter a mocked test suite stayed green while a schema migration failed in production. The mock didn't know about the new column. We lost half a day diagnosing.

**How to apply:** When I ask for integration tests, default to real DB. If setup is too slow for CI, suggest an emulator (Firestore, Postgres in Docker) before suggesting mocks. Tier 1 pure-logic unit tests can still mock — it's the **integration** layer where real-world drift matters.
