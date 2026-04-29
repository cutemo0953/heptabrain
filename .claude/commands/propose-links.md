---
description: "Propose new connections within a single whiteboard via TF-IDF Pass 1 + Claude native LLM Pass 2 + NetworkX gap signals. Usage: /propose-links \"whiteboard name or id\""
argument-hint: "\"{whiteboard name or id}\""
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, mcp__heptabase-mcp__search_whiteboards, mcp__heptabase-mcp__get_whiteboard_with_objects, mcp__heptabase-mcp__get_object, mcp__heptabase-mcp__save_to_note_card
category: utility
projects: [all]
---

# Propose-Links — Closed-Set Connection Discovery

Spec: `docs/04-heptabrain-propose-links.md` v1.2.2 + `docs/IMPLEMENTATION_PLAN_PHASE_2.md`

## Arguments

`$ARGUMENTS` = whiteboard name keyword OR whiteboard id (UUID).
- Keyword → `mcp__heptabase-mcp__search_whiteboards`; ambiguous matches prompt user to disambiguate.
- ID → used directly.

## Registries

- **Discovered Links:** `memory/_discovered_links.json` (initialize as `[]` if absent)

## Snapshot-drift Discipline

Every run uses a unique `run_id = {YYYYMMDDTHHMMSSZ}-{wb-slug}` and a private tmp directory:

```
/tmp/heptabrain-propose-links/{run_id}/
├── snapshot.json     # frozen whiteboard fixture
├── pairs.json        # CLI --emit-pairs output (Pass 1 → Pass 2 input)
├── pass2.json        # native LLM Pass 2 results (Pass 2 → CLI input)
└── suggestion.md     # CLI --suggestion-card output (audit trail)
```

Both CLI calls MUST receive the same `--fixture {run_dir}/snapshot.json`. Pass 2 envelope MUST carry `whiteboard_id`; every analysis MUST echo back `pair_id` + `from_id` + `to_id` so the writer can detect drift.

## Pipeline

### Step 1 — Discover whiteboard (or use direct ID)

If `$ARGUMENTS` matches the Heptabase ID shape (UUID-style, e.g.
`wb-7b3a-...`), **skip search** and go straight to Step 2 with that id.

Otherwise, treat `$ARGUMENTS` as a name keyword:
```
mcp__heptabase-mcp__search_whiteboards(keyword=$ARGUMENTS)
```

If 0 matches → ask user to refine. If 1 match → confirm with user. If ≥ 2 matches → list and ask user to pass an exact id.

### Step 2 — Snapshot

```
mcp__heptabase-mcp__get_whiteboard_with_objects(whiteboard_id={id})
```

Wrap the response into `{whiteboards: [{id, name, objects, connections}]}` and write to `{run_dir}/snapshot.json`. This is now a fixture compatible with `FakeHeptabaseMCPClient`. The id-direct path (Step 1's first branch) reaches this same call without a prior search.

### Step 3 — Phase 1 + 2.1 dry-run + emit pairs

```bash
python -m scripts.propose_links.cli "{id}" \
  --fixture "{run_dir}/snapshot.json" \
  --emit-pairs "{run_dir}/pairs.json"
```

CLI exits non-zero on hard-stop (>50 cards), seed maturity (<8 cards), or CJK gate failure — surface the error to the user verbatim and stop.

### Step 4 — Native LLM Pass 2

Read `{run_dir}/pairs.json`. The `pairs` array contains every NEW pair (existing connections already filtered by Phase 2.1). For **each** pair, perform the 5 analyses from spec §2.3 Step 4:

1. **Core principles** — extract 2-3 underlying principles from each card.
2. **Elevation anchor** — map each principle to a Cyberbrain dimension if applicable.
3. **Relation type** — choose ONE from the 11-frozen taxonomy. If genuinely none fit, return `related_to` (the merger flags it `needs_review`):

   | Relation | Use when |
   |----------|----------|
   | `supports` | A argues for B |
   | `contradicts` | A and B claim opposites |
   | `derives_from` | A is derived from B |
   | `applies_to` | B applies A to a domain |
   | `example_of` | A is example of B |
   | `bridge_to` | A and B span different domains |
   | `tensions_with` | A and B reveal a productive tension |
   | `synergizes-with` | A and B amplify each other |
   | `attracts` | A and B sit close in concept space |
   | `precedes` | A temporally precedes B |
   | `shares_principle` | A and B express the SAME concept (different vocabulary) |
   | `related_to` (fallback) | None of the above; merger flags needs_review |

4. **Rationale** — 1-2 sentences. Plain text; no markdown tables. Focus on WHY the relation holds, not WHAT each card says.
5. **Confidence** — `high` / `med` / `low`:
   - `high` — both cards explicitly invoke the same principle / contradiction
   - `med` — strong inference; surface evidence in rationale
   - `low` — speculative; the rationale should hedge

Write results to `{run_dir}/pass2.json`:

```json
{
  "whiteboard_id": "{id}",
  "analyses": [
    {
      "pair_id": "p-{i}-{j}",
      "from_id": "{card_id_a}",
      "to_id": "{card_id_b}",
      "relation_type": "shares_principle",
      "rationale": "Both cards posit recursion as the boundary-crossing mechanism.",
      "confidence": "high",
      "evidence_kind": ["text_overlap"]
    }
  ]
}
```

**Fidelity rules (snapshot-drift guards):**
- `pair_id` MUST match the input format from `pairs.json`
- `from_id` / `to_id` MUST be the literal strings from `pairs.json` for that pair (the merger compares them as an unordered set)
- Don't invent `pair_id` values not in the input; the merger emits a warning if it sees an unknown one

**Don't**: send EXISTS pairs to LLM (they're already filtered out of `pairs.json`); produce duplicate `pair_id`s; return non-string rationale.

### Step 5 — Merge + signals + persist + render card body

```bash
python -m scripts.propose_links.cli "{id}" \
  --fixture "{run_dir}/snapshot.json" \
  --with-pass2 "{run_dir}/pass2.json" \
  --signals \
  --discovered-json "memory/_discovered_links.json" \
  --suggestion-card "{run_dir}/suggestion.md"
```

CLI surfaces:
- `[discovered-json] wrote N entries (skipped M, invalid K, registry now T entries)`
- `[suggestion-card] wrote N bytes to {path}`
- `[signals warn]` and `[with-pass2 warn]` for any drift / partial coverage

Invalid entries are skipped with the pair_id + reason — propagate to the user.

### Step 6 — (Optional) Create suggestion card on Heptabase

Ask the user: **"要不要在 whiteboard 上建一張 🗂️ Suggestion Card？(y/n)"**

If yes:
```
mcp__heptabase-mcp__save_to_note_card(
  title="🗂️ {whiteboard name} 組織建議 — {YYYY-MM-DD}",
  content=<contents of {run_dir}/suggestion.md>,
)
```

Then add the card to the target whiteboard via the MCP attach tool if available, or instruct the user to drag it in manually.

### Step 7 — Cleanup

Remove `{run_dir}/snapshot.json` `pairs.json` `pass2.json`. **Keep** `suggestion.md` (audit trail). Do not remove `_discovered_links.json` (registry).

## Boundary

- Phase 2C does NOT auto-accept proposed links. Every entry has `link_class='proposed'` + `acceptance_state='proposed'`. User upgrades to `accepted` separately (Phase 3 work).
- Suggestion card title MUST start with `🗂️`. Footer MUST include "移除本卡不影響 whiteboard 結構".
- The card is informational only — never modifies existing connections / sections / cards.
- Cross-run dedup of `_discovered_links.json` (re-propose cooldown) is deferred. Re-running today writes new entries with new `link_id`; the user is responsible for running this skill judiciously.

## Failure modes (CLI exits non-zero)

| Exit | Meaning | Recovery |
|------|---------|----------|
| `2` user error | unknown / ambiguous wb, hard-stop, seed maturity, missing --with-pass2 prereq, malformed pass2.json shape, snapshot-drift outer guard | Surface the message; don't auto-retry |
| `1` runtime error | atomic_write failure, registry corrupted, unwritable suggestion-card path, CJK gate fail | Inspect filesystem state |
| `0` ok | Pipeline succeeded; check stderr for warnings | Read the markdown / suggestion card |

## See also

- Phase 1 dry-run details: `scripts/propose_links/cli.py` docstring
- Pass 2 merge contracts: `scripts/propose_links/pass2_merge.py`
- Gap signals taxonomy: `scripts/propose_links/gap_signals.py` module docstring
