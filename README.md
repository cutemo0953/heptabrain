# HeptaBrain

**Heptabase + Claude Code = AI-powered Zettelkasten, built on a small family of specs that keep state and knowledge from leaking into each other.**

Four Claude Code slash commands, two docs, one install script. Used daily by the author since 2026-04-06.

> *"The value of knowledge isn't in the nodes. It's in the links between them."*

## The four slash commands

| Command | Purpose | Spec |
|---|---|---|
| `/heptabrain-sync` | Distill memory files → Heptabase cards (never copy bulk); URI-reference pull; audit; gc | [`docs/02-heptabrain-sync.md`](docs/02-heptabrain-sync.md) |
| `/zettel-walk` | Cross-domain knowledge discovery via **dimensional elevation** — the AI abstracts your concept to an underlying principle first, then searches with that principle | [`docs/03-zettel-walk.md`](docs/03-zettel-walk.md) |
| `/zettel-eval` | Evaluate the quality of discovered links independently (critic agent for `/zettel-walk` output) | (shares the zettel-walk spec) |
| `/kb-restructure` | Restructure wiki-format KBs — merge duplicates, relocate misplaced entries, update stale ones | — |

## The architecture underneath

```
Cyberbrain Architecture (docs/01-cyberbrain-architecture.md)  ← infrastructure
  │  State vs Knowledge separation, per-type canonical authority,
  │  evidence-bearing links, elevation anchors, journal relay
  │
  ├── HeptaBrain Sync       (docs/02-heptabrain-sync.md) ─ shipped
  │     /heptabrain-sync
  │
  ├── Zettel Walk           (docs/03-zettel-walk.md)     ─ shipped
  │     /zettel-walk, /zettel-eval
  │
  ├── KB Restructure        (ad-hoc)                     ─ shipped
  │     /kb-restructure
  │
  ├── Strategic Review System        [not yet shipped]   ─ dog-fooding
  │     Multi-lens feature review (ecosystem / jtbd / brand / trust / ...)
  │
  └── Multidimensional Analysis (MDA)  [not yet shipped] ─ dog-fooding
        extends Strategic Review
        4D+: Proximity / Synergy / Temporal / Perspective
```

The two "not yet shipped" layers are being validated across 10+ real reviews in 3+ projects before they land here. File an issue if you want to pilot them early.

## The key innovation: dimensional elevation

Naive vector search finds neighbours in the same domain. Most useful cross-domain insights don't live there — they live one abstraction level up, where "bundled payment model" and "LC resonance sensor" both turn out to be about *making invisible system state observable*.

`/zettel-walk` forces that elevation:

```
Starting card: "Personal Knowledge Management"
  → Elevated: "Making information visible creates self-correcting feedback loops"
  → Walked to: "LC resonance sensor" (implantable sensor physics)
  → Elevated: "Converting unmeasurable system state into observable proxy signals"
  → Walked to: "Distributed Resilient Operations" (disaster response systems)

Discovery: All three share one principle —
"Observation itself is intervention. Faithful recording is the most
powerful force for improvement."
```

That discovery led to a real clinical insight: daily post-surgical pain tracking has an analgesic effect — not placebo, but perceived control + anti-catastrophizing + expectation reframing.

## The discipline underneath the commands

Full detail: [`docs/01-cyberbrain-architecture.md`](docs/01-cyberbrain-architecture.md). TL;DR:

- **P1 — State vs Knowledge decoupling.** Day/week-level perishable → Claude Memory. Crystallised → Heptabase cards. Canonicality declared in frontmatter, not guessed.
- **P2 — Per-type canonical authority.** Each entity class has one authoritative system. No dual source of truth.
- **P3 — Evidence-bearing links.** Every AI-suggested link carries `relation_type` + `rationale` + `evidence` + `review_state`. Bare `[[link]]` is rejected.
- **P4 — Elevation anchors.** When abstracting upward, map to a user-chosen set of attractors so cross-domain collisions become repeatable, not random.
- **P5 — Journal as relay.** AI discoveries land in Journal first, not as cards. User promotes good parts via "Turn into card" — reduces whiteboard-placement friction to one click.

## Install

Prerequisites:
- [Claude Code](https://claude.com/claude-code) CLI
- A Heptabase account with the [Heptabase MCP](https://heptabase.com/mcp) connected (or adapt per "Porting" below)

```bash
git clone https://github.com/cutemo0953/heptabrain.git
cd heptabrain
./setup/install.sh
```

The install script copies the four slash commands into `~/.claude/commands/`, seeds memory templates into `~/.claude/memory/` (only if that dir is empty — won't clobber existing memory), and creates empty registry JSON skeletons.

After install, open any Claude Code session and run `/heptabrain-sync status` to verify.

## Porting to other card systems

The sync discipline doesn't depend on Heptabase specifically. Viable targets, in roughly descending confidence:

| Target | Adapter path | Status |
|---|---|---|
| Plain filesystem (Markdown dir) | `fs.writeFile` + `ripgrep` for search | **Verified** — simplest port |
| Obsidian | [`obsidian-local-rest-api`](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin | Viable; community plugin, not first-party |
| Logseq | Plugin SDK or direct graph-dir write; no official REST/GraphQL surfaced | Unverified |
| Roam Research | Only unofficial integrations exist | Unverified |
| Any Zettelkasten with a CLI/MCP | Whatever primitives your tool exposes | Works if primitives map to `save / search / list-containers` |

Whichever adapter you choose, two invariants must hold:

1. **Preserve the Step 1.5 "Whiteboard Discovery → Placement Hint" loop.** Letting the user keep placement control is the main UX win.
2. **Keep the registry schema.** The `knowledge_id` / `content_hash` / `superseded_by` triangle is what makes supersession auditable.

If you try a port, file an issue with what worked and what broke — even partial reports help refine the "status" column above.

## Chinese introduction

For a blog-style Chinese walk-through of the philosophy, see [`INTRO_ZH.md`](INTRO_ZH.md).

## Status

| Piece | Maturity |
|---|---|
| Cyberbrain Architecture spec | v2.1 FINAL, in daily use by author since 2026-04-06 |
| HeptaBrain Sync spec + `/heptabrain-sync` | v2.1 FINAL, ~1 card/day distilled in steady state |
| Zettel Walk spec + `/zettel-walk`, `/zettel-eval` | Shipped; the "Pain Tracking Is Pain Relief" discovery was produced by it |
| `/kb-restructure` | Shipped as an atomic skill |
| Strategic Review System (sibling) | Dog-fooding internally; will land after 10+ cross-project reviews |
| Multidimensional Analysis Extension (sibling) | Dog-fooding internally; `Rev 1.5` with experimental stubs |

## License

See [`LICENSE`](LICENSE) for the short explainer. In brief:

- **Docs** (`docs/`, `README.md`, `CONTRIBUTING.md`, `examples/**/*.md`, `INTRO_ZH.md`): [CC BY 4.0](./LICENSE-docs)
- **Code** (`setup/`, future helpers): [MIT](./LICENSE-code)

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Port reports and spec critiques are especially welcome — there are GitHub issue templates for both.
