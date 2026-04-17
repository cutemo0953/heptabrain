# Memory Templates

These are starter templates for the four memory types Cyberbrain recognises. They live in `examples/` — the install script copies them to `~/.claude/memory/` **only if that directory is empty**, so they won't clobber an existing setup.

## The four types

| Type | What it captures | Canonicality default |
|---|---|---|
| `user` | Who the user is, what they care about, their mental model | candidate |
| `feedback` | Corrections / confirmations from past sessions | reference |
| `project` | State of an in-flight project: who, why, by when | candidate |
| `reference` | Pointers to external systems (Linear, Slack, dashboards) | reference |

Only `canonicality: knowledge` (declared in frontmatter) is eligible for `/heptabrain-sync push`. Everything else stays in Memory.

## Files in this folder

- `user_example.md` — user profile skeleton
- `feedback_example.md` — feedback entry with why/how-to-apply structure
- `project_example.md` — project status card (note: project files should get bumped to `canonicality: knowledge` only when they contain a durable principle, not current-week state)
- `reference_example.md` — external system pointer

## Index file

Also copied on install: `MEMORY.md` at the root of `~/.claude/memory/` — the index file. Keep entries to one line each, under ~150 chars. Detail goes in the topic files, not the index.
