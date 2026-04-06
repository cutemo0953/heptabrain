# HeptaBrain

**Heptabase + Claude Code = AI-powered Zettelkasten**

A set of Claude Code skills that turn Heptabase into an AI-driven knowledge discovery system. Instead of manually browsing your cards, let AI walk through your knowledge base, find cross-domain connections you'd never see, and write the discoveries into your Heptabase Journal.

## What This Does

Two skills:

### `/zettel-walk` — Cross-Domain Knowledge Discovery

Ask AI to wander through your Heptabase cards and find hidden connections between seemingly unrelated concepts.

```
/zettel-walk wander "bundled payment model"
```

The key innovation is **dimensional elevation**: instead of searching for similar cards (which just finds neighbors in the same domain), the AI first abstracts your concept to an underlying principle, then searches with that principle. This produces genuine cross-domain collisions.

**Example from real usage:**

```
Starting card: "電馭大腦" (Personal Knowledge Management)
  → Elevated: "Making information visible creates self-correcting feedback loops"
  → Walked to: "LC resonance sensor" (Implantable sensor physics)
  → Elevated: "Converting unmeasurable system state into observable proxy signals"
  → Walked to: "Distributed Resilient Operations" (Disaster response systems)

Discovery: All three share one principle —
"Observation itself is intervention. Faithful recording is the most powerful force for improvement."
```

This discovery led to a clinical insight: daily post-surgical pain tracking has analgesic effect — not through placebo, but through perceived control, anti-catastrophizing, and expectation reframing.

**Four modes:**

| Mode | Command | What it does |
|------|---------|-------------|
| Wander | `/zettel-walk wander "concept"` | Walk 3-5 steps via dimensional elevation |
| Shuffle | `/zettel-walk shuffle 3 "anchor"` | Random 3 cards + your anchor, find common principles |
| Bridge | `/zettel-walk bridge "A" "B"` | Find connection + dialectic tension between two cards |
| Journal | `/zettel-walk journal` | Review last 7 days, find patterns worth promoting to cards |

Results are shown in CLI first, then optionally written to your Heptabase Journal. You decide what to promote to a card — AI discovers, you decide.

### `/heptabrain-sync` — Knowledge Distillation

Sync knowledge between Claude Code's memory system and Heptabase.

```
/heptabrain-sync push          # Distill memory → Heptabase cards
/heptabrain-sync pull "topic"  # Find relevant Heptabase cards for current session
/heptabrain-sync gc            # List superseded cards for cleanup
/heptabrain-sync audit         # Check for duplicates and orphans
```

Key design decisions:
- **Distill, don't copy.** AI extracts core insights and underlying principles, not raw file content.
- **State vs Knowledge.** Only crystallized knowledge gets synced — not in-progress work, session logs, or bug lists.
- **Journal as intermediary.** Zettel-walk results go to Journal first. You promote the good ones to cards in Heptabase UI (right-click → "Turn into card"). This avoids cluttering your whiteboards with AI-generated cards.

## Design Principles

### 1. Connections > Nodes

Inspired by Luhmann's Zettelkasten: the value of knowledge is not in individual notes, but in the connections between them. AI can traverse thousands of cards in seconds and find patterns humans miss.

### 2. Dimensional Elevation

Don't search with raw concepts — you'll only find same-domain neighbors. Abstract first, search second.

```
Raw: "rotator cuff repair technique"
  → only finds: "ACL reconstruction", "shoulder arthroscopy"

Elevated: "restoring function under mechanical constraint"
  → finds: "disaster triage resource allocation", "battery-free sensor design"
  → genuine cross-domain insight
```

### 3. Observation Is Intervention

The deepest principle discovered through using this system: making information visible creates self-correcting feedback loops. This applies to:
- Knowledge management (externalize thoughts → automatic organization)
- Clinical practice (track pain daily → pain decreases)
- System design (event sourcing → operational clarity)

### 4. Journal-First Output

Heptabase's MCP API can create cards but cannot place them on whiteboards. Instead of dumping cards into your main space (requiring manual organization), discoveries go to your Journal. You browse the Journal in Heptabase and promote the good parts with one click.

## Setup

### Prerequisites

- [Claude Code](https://claude.ai/code) (CLI or desktop app)
- [Heptabase](https://heptabase.com/) with MCP integration enabled
- Heptabase MCP server configured in Claude Code

### Installation

1. Copy the skill files to your Claude Code commands directory:

```bash
cp skills/zettel-walk.md ~/.claude/commands/
cp skills/heptabrain-sync.md ~/.claude/commands/
```

2. Create the registry files:

```bash
mkdir -p ~/.claude/projects/default/memory

echo '{"version":"2.1","lastSync":null,"entries":[]}' \
  > ~/.claude/projects/default/memory/_heptabrain_registry.json

echo '[]' \
  > ~/.claude/projects/default/memory/_discovered_links.json
```

3. Configure your Elevation Anchors by editing `zettel-walk.md` — replace the default anchors with your own focus areas:

```markdown
## Elevation Anchors
1. Your Domain A (e.g., "System Resilience")
2. Your Domain B (e.g., "Economic Incentives")
3. Your Domain C (e.g., "Clinical Feedback Loops")
4. Your Domain D (e.g., "Scaling & Governance")
5. Your Domain E (e.g., "Human-AI Collaboration")
```

4. (Optional) Update the memory path in both skill files if your Claude Code project path differs from the default.

## Architecture

```
You ──→ Claude Code CLI ──→ Heptabase MCP
              │                    │
         [zettel-walk]        [read cards]
         [heptabrain-sync]    [search cards]
              │               [write journal]
              ↓               [create cards]
       _discovered_links.json
       _heptabrain_registry.json
```

**Data flow for zettel-walk:**
```
1. You type: /zettel-walk wander "concept"
2. AI searches Heptabase → finds starting card
3. AI extracts concepts → elevates to principle → searches again
4. Repeats 3-5 steps (with cycle guard)
5. Synthesizes path → shows result in CLI
6. You confirm → AI writes to Heptabase Journal
7. Links saved to _discovered_links.json
8. You browse Journal in Heptabase → promote good discoveries to cards
```

**Data flow for heptabrain-sync push:**
```
1. You type: /heptabrain-sync push
2. AI reads memory files → filters by canonicality (knowledge only, not state)
3. AI distills each file → core insights + underlying principle
4. AI searches Heptabase whiteboards → suggests placement
5. Creates cards with placement hints
6. Updates registry with knowledge_id + content_hash
```

## Discovered Links Registry

Every zettel-walk saves discovered connections as structured data:

```json
{
  "link_id": "lk-20260406-001",
  "from_knowledge_id": "電馭大腦",
  "to_knowledge_id": "LC resonance",
  "relation_type": "shares_principle",
  "rationale": "Both convert invisible state into observable signals",
  "evidence_refs": ["電馭大腦 §observation", "LC resonance §frequency proxy"],
  "novelty_score": 0.9,
  "evidence_score": 0.7,
  "review_state": "proposed",
  "discovered_at": "2026-04-06T16:45:00+08:00",
  "discovered_by": "zettel-walk wander"
}
```

This prevents rediscovering the same connections and lets you track which links you accepted or rejected over time.

## Design Specs

The full architecture went through multi-AI review (Claude → Gemini → ChatGPT → revise → re-review). The specs and review logs are in `specs/`:

- `DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md` — Overall architecture (v2.1)
- `DEV_SPEC_HEPTABRAIN_SYNC.md` — Sync design (v2.1)
- `DEV_SPEC_ZETTEL_WALK.md` — Walk design (v2.1)

## Limitations

| Limitation | Workaround |
|-----------|-----------|
| Heptabase MCP can't place cards on whiteboards | Journal-first pattern: write to Journal, you promote in UI |
| Heptabase MCP can't edit or delete cards | `supersedes` tracking + `gc` command for cleanup lists |
| Heptabase MCP can't add tags | `Tags:` text in card content (searchable but not filterable) |
| Vector search finds same-domain neighbors | Dimensional elevation: abstract first, search second |
| Skills are prompts, not executable code | They work because Claude Code interprets them — same as gstack, CLAUDE.md workflows |

## License

MIT (skill files and schemas) + CC BY 4.0 (documentation and examples)

## Credits

- [Heptabase](https://heptabase.com/) — the visual knowledge base
- [Claude Code](https://claude.ai/code) — the AI development environment
- Niklas Luhmann — the Zettelkasten method
- Timothy Gallwey — "observation itself brings improvement" (The Inner Game of Tennis)
- The concept of "dimensional elevation" was developed during a multi-AI architecture review session with Claude, Gemini, and ChatGPT
