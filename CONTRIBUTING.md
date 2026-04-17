# Contributing

Cyberbrain is a young framework with a specific shape: it was dog-fooded by one person for a few weeks before being shared. That means the easiest ways to help are asymmetric to the kind of contributions you might send to a mature OSS project.

## What's high-value right now

- **Port reports.** If you wire the sync skill up to Obsidian, Logseq, Roam, Bear, Apple Notes, or a plain filesystem, write it up. Even a failed port is useful — it tells us which assumptions baked into HeptaBrain are Heptabase-specific.
- **Real-world case write-ups.** If you use `/heptabrain-sync` for a week and want to contribute a case study (what you distilled, what you killed, what surprised you), open a discussion.
- **Spec critique.** The two specs in `docs/` went through two rounds of Gemini + ChatGPT review but have limited real-world diversity. If you see a principle that looks wrong in your context, open an issue — tension is exactly the signal we want to hear.

## What's lower priority

- **Automation features.** Spec §6 of HeptaBrain Sync lists "out of scope" items (auto-triggers, reverse Memory write, whiteboard organisation, tag API, three-layer registry). These were deferred for good reasons; opening an issue for one of them means arguing against the reasons first.
- **New commands.** The `push / pull / status / audit / gc / gc confirm` surface is deliberately narrow. A new command needs to come with at least one real use case that the existing 6 can't serve.

## How to propose changes to the specs

Specs in `docs/` follow the convention used in their original private form: multi-round review with at least two external reviewers before a version bumps to `FINAL`. For this public repo:

1. Open an issue describing the problem (not the solution).
2. Wait for maintainer ACK that the problem is real and in-scope.
3. Draft a spec revision as a PR against `docs/0X-<name>.md`. Include a "Review Feedback Disposition" section appending your addressed feedback.
4. Expect at least one round of maintainer + community review before merge.

Small docs fixes (typos, broken links, clarifications) can go straight to PR without an issue.

## Filename conventions

- `docs/0N-<topic>.md` — numbered so navigation reflects dependency order
- `examples/memory/<type>_<name>.md` — always include `type: {user|feedback|project|reference}` in frontmatter
- `.claude/commands/<name>.md` — slash command Markdown; follow the YAML frontmatter shape used by existing commands

## Attribution

All merged contributions are credited in the relevant file's changelog section. You keep copyright on your contributions; by opening a PR you license them under CC BY 4.0 (docs) or MIT (code).
