---
description: "Evaluate discovered links quality — independent critic for zettel-walk outputs. Usage: /zettel-eval or /zettel-eval stale"
argument-hint: "[blank] | stale"
allowed-tools: Read, Write, Edit, Bash, mcp__heptabase-mcp__semantic_search_objects, mcp__heptabase-mcp__get_object
---

# Zettel Eval — Independent Link Quality Evaluator

**Principle:** "You can't let someone grade their own homework." (Harness Engineering)

Zettel-walk discovers links. Zettel-eval validates them. They are deliberately separate skills so the critic is independent of the discoverer.

## Arguments

`$ARGUMENTS`:
- (empty) — evaluate all `proposed` links in the registry
- `stale` — find and downgrade links that have been `proposed` for >30 days without review

## Registry

`~/.claude/projects/-Users-QmoMBA/memory/_discovered_links.json`

## Default Mode: Evaluate Proposed Links

1. Read `_discovered_links.json`
2. Filter entries where `review_state == "proposed"`
3. For each proposed link:

**Step A: Re-read the evidence**
- If `from_knowledge_id` or `to_knowledge_id` reference Heptabase cards, search and read them
- If they reference Memory files, read those files

**Step B: Independent critique (different persona)**
Adopt the role of a **skeptical reviewer**, NOT the discoverer. Ask:

| Question | What you're looking for |
|----------|----------------------|
| Is this a genuine principle-level connection, or just word overlap? | "Both use feedback" is shallow. "Both convert invisible state to observable proxy signal via the same mechanism" is deep. |
| Could you explain this link to a non-expert and have them understand why it's surprising? | If it's not surprising, it's not cross-domain insight — it's just categorization. |
| Is the evidence specific? | "Card A §section" is good. "Card A mentions something similar" is vague. |
| Would the link still hold if you replaced the specific examples with different ones from the same domains? | If yes → principle-level (good). If no → surface-level coincidence (bad). |

**Step C: Score and verdict**

| Verdict | Criteria | Action |
|---------|----------|--------|
| **confirmed** | Deep principle connection, specific evidence, would survive example substitution | Change `review_state` to `accepted` |
| **weak** | Some connection but shallow or evidence is vague | Keep as `proposed`, add `eval_note` explaining weakness |
| **rejected** | Word overlap only, not surprising, evidence doesn't hold up | Change `review_state` to `rejected` |

4. Output report in CLI:

```
## Zettel Eval Report — {date}

Evaluated: {N} proposed links

| # | From → To | Type | Verdict | Note |
|---|-----------|------|---------|------|
| 1 | A → B | shares_principle | confirmed | Deep mechanism match |
| 2 | C → D | bridge_to | weak | Evidence too vague |
| 3 | E → F | tensions_with | rejected | Just word overlap |

Confirmed: {N} | Weak: {N} | Rejected: {N}
```

5. Update `_discovered_links.json` with new `review_state` and add `eval_note` field.

## Stale Mode: TTL Enforcement

```
/zettel-eval stale
```

1. Read `_discovered_links.json`
2. Find entries where:
   - `review_state == "proposed"`
   - `discovered_at` is more than 30 days ago
3. Change their `review_state` to `stale`
4. Report:

```
## Stale Links Report — {date}

{N} links have been proposed for >30 days without review.
Downgraded to "stale":

| # | From → To | Discovered | Age |
|---|-----------|-----------|-----|
| 1 | A → B | 2026-03-05 | 32 days |

These links are preserved but deprioritized.
To revive a stale link, manually change review_state back to "proposed".
```

## Important Rules

- **You are the CRITIC, not the discoverer.** Your job is to find weaknesses, not confirm biases.
- A link being "interesting" is not enough. It must be principle-level, evidence-backed, and surprising.
- When in doubt, mark as `weak` rather than `confirmed` or `rejected`.
- All output in zh-TW.
- Never modify links that are already `accepted` or `rejected` — only evaluate `proposed` ones.
