---
description: "Sync knowledge between Claude Memory and Heptabase. Usage: /heptabrain-sync push or /heptabrain-sync pull [topic]"
argument-hint: "push | push [filename] | pull [topic] | status | audit | gc | gc confirm"
allowed-tools: Read, Glob, Grep, Bash, Write, Edit, mcp__heptabase-mcp__save_to_note_card, mcp__heptabase-mcp__semantic_search_objects, mcp__heptabase-mcp__search_whiteboards, mcp__heptabase-mcp__get_object


---

# HeptaBrain Sync — Knowledge Distillation between Claude Memory and Heptabase

Spec: `~/.claude/projects/<YOUR_PROJECT>/memory/DEV_SPEC_HEPTABRAIN_SYNC.md` v2.1

## Arguments

`$ARGUMENTS` = one of: `push`, `push [filename]`, `pull [topic]`, `status`, `audit`, `gc`, `gc confirm`

## Registries

- **Sync Registry:** `~/.claude/projects/<YOUR_PROJECT>/memory/_heptabrain_registry.json`
- **Heptabase Refs:** `~/.claude/projects/<YOUR_PROJECT>/memory/_heptabase_refs.json`

Initialize registry files if they don't exist (empty `{"version":"2.1","lastSync":null,"entries":[]}` and `{"session_id":null,"refs":[]}`).

## Commands

### `push` — Memory → Heptabase (Knowledge Distillation)

1. **Read all memory files** in `~/.claude/projects/<YOUR_PROJECT>/memory/`
   - Only `.md` files with YAML frontmatter
   - Skip files starting with `_` (registries), `MEMORY.md` (index), `SKILLS_SPEC.md`, `DEV_SPEC_*`

2. **Canonicality filter** (metadata-first, heuristic-fallback):
   - If frontmatter has `canonicality: knowledge` → PASS
   - If frontmatter has `canonicality: state` → SKIP
   - If `type: feedback` or `type: user` → SKIP
   - If filename contains `session_`, `bugs_`, date pattern `_YYYYMMDD` → SKIP (state heuristic)
   - If content contains 策略/結論/原則/架構/strategy/principle → likely knowledge
   - Otherwise → ask user to confirm

3. **Read sync registry** → check which files already synced (by knowledge_id or filename)
   - If found AND content_hash matches → skip ("already synced")
   - If found AND hash different → will supersede

4. **Whiteboard Discovery** — search Heptabase whiteboards using the file's core keywords. Cache the whiteboard list for the entire push session.

5. **For each eligible file, distill** (NOT copy):
   - Extract 3-5 core insights (bullet points)
   - Extract 1-2 sentence underlying principle ("the so-what that won't expire")
   - Identify related Heptabase cards (semantic search)
   - Suggest whiteboard placement (from Step 4 results)
   - Generate `knowledge_id` as `kb-{slug}` from filename

6. **Create Heptabase card** with this format:

```markdown
# {knowledge title}

## Core Insights
- {insight 1}
- {insight 2}
- {insight 3}

## Underlying Principle
{1-2 sentences}

## Relations
- Relates to: [{card}] — {relation_type}: {rationale}

## Whiteboard Placement
- Suggested whiteboard: "{name}"
- Connect to: [{card 1}], [{card 2}]
- Position hint: "{description}"

---
**Knowledge ID:** {knowledge_id}
**Authority:** canonical
**Source:** Claude Code Memory → `{filename}`
**Distilled:** {ISO timestamp}
**Tags:** #knowledge-sync #{topic}
```

7. **Update registry** with new entry (knowledge_id, content_hash, aliases, card title, timestamp)

8. **Report** results in CLI:
   - How many files scanned, skipped (state/feedback/already synced), pushed
   - List of created cards with knowledge_ids

### `push [filename]` — Push specific file

Same as `push` but only process the named file. Skip canonicality filter (user explicitly chose it).

### `pull [topic]` — Heptabase → Session Context (URI Reference)

1. Search Heptabase with topic + any aliases from registry
2. For top 5 relevant cards: record card_id, title, 2-line summary
3. Write to `_heptabase_refs.json` with session_id = current ISO timestamp
4. **Display results in CLI** — show card titles + summaries
5. Tell user: "When you need full content from any of these cards, I'll read it on demand via Heptabase MCP."

### `status` — Registry Summary

Read registry, output:
- Total entries, last sync time
- Breakdown: knowledge / superseded / by source_system
- Any entries with `superseded_by` not yet GC'd

### `audit` — Consistency Check

1. Read registry
2. For each entry with aliases, semantic search Heptabase:
   - **Possible duplicates:** Multiple cards matching same aliases
   - **Orphan entries:** Registry entry but card not findable in Heptabase
   - **Untracked cards:** Heptabase cards with `#knowledge-sync` tag text but not in registry
3. Output audit report in CLI

### `gc` — Garbage Collection List

1. Read registry, find all entries where `superseded_by` is not null
2. Output markdown checklist with card titles
3. Tell user: "Please delete these in Heptabase UI, then run `/heptabrain-sync gc confirm`"

### `gc confirm` — Mark GC'd entries as cleaned

1. Remove entries with `superseded_by` from registry (or mark status: "gc_cleaned")
2. Report how many entries cleaned

## Important Rules

- **Never copy full memory file content to Heptabase.** Always distill.
- **State files must never reach Heptabase.** When in doubt, ask user.
- All CLI output in zh-TW.
- Content hash: use first 12 chars of sha256 of file content (compute via: `echo -n "content" | shasum -a 256 | cut -c1-12`)
