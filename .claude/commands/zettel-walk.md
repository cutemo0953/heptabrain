---
description: "Zettelkasten walk — discover cross-domain knowledge connections via dimensional elevation. Usage: /zettel-walk wander \"concept\" or /zettel-walk shuffle 3 \"anchor\""
argument-hint: "wander \"concept\" | shuffle N \"anchor\" | bridge \"A\" \"B\" | journal"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, mcp__heptabase-mcp__semantic_search_objects, mcp__heptabase-mcp__search_whiteboards, mcp__heptabase-mcp__get_object, mcp__heptabase-mcp__get_whiteboard_with_objects, mcp__heptabase-mcp__append_to_journal, mcp__heptabase-mcp__get_journal_range
category: utility
projects: [all]
---

# Zettel Walk — Cross-Domain Connection Discovery

Spec: `~/.claude/projects/<YOUR_PROJECT>/memory/DEV_SPEC_ZETTEL_WALK.md` v2.1

## Arguments

`$ARGUMENTS` = one of:
- `wander "{starting concept}"` — Dimensional elevation walk
- `shuffle N "{anchor card}"` — Random N cards + 1 anchor
- `bridge "{card A}" "{card B}"` — Find bridge + dialectic tension
- `journal` — Review last 7 days of journal

## Registries

- **Discovered Links:** `~/.claude/projects/<YOUR_PROJECT>/memory/_discovered_links.json`

Initialize if not exists: `[]`

## Elevation Anchors

When abstracting concepts, **prioritize mapping to these core dimensions** (but allow free abstraction if none fit):

1. System Resilience (系統韌性)
2. Economic Incentives & Boundary Conditions (經濟誘因與邊界條件)
3. Clinical Feedback Loops (臨床回饋迴圈)
4. Scaling & Governance (規模化與治理)
5. Human-AI Collaboration (人機協作)

## Mode 1: Wander (升維漫遊)

```
/zettel-walk wander "ExampleProject recovery loop"
```

**Flow:**

1. **Find starting card:** Semantic search Heptabase for the concept. Read full content.

2. **Extract + Elevate:** From the card content:
   - Extract 2-3 raw concepts
   - Abstract each to an underlying principle
   - Map to an Elevation Anchor if applicable
   - Example: "E-P-E-R" → Anchor 3 → "uncertainty reduction through observation loops"

3. **Search with elevated concept:** Use the abstracted principle (NOT the raw concept) as the search query.
   - Exclude `visited_ids` (cards already walked)
   - Prefer cards from different whiteboards (cross-domain)
   - Internally score candidates:
     - `novelty_score` = domain distance from starting card (0-1)
     - `evidence_score` = semantic relevance to abstracted principle (0-1)
     - Pick: `novelty * 0.6 + evidence * 0.4` highest

4. **Walk next card:** Read full content → extract → elevate → search again

5. **Repeat** 3-5 steps. Stop conditions:
   - 5 steps reached (hard limit)
   - 2 consecutive steps with all results in visited_set
   - Abstraction becomes too generic (>3 words AND very common phrase) → drop one level

6. **Synthesize:** Review the full path, identify:
   - Hidden pattern across all walked cards
   - Bottom-line logic (one sentence)
   - Link evidence for each discovered connection

7. **Output** full results in CLI (always shown to user)

8. **Ask user:** "寫入今天的 Heptabase Journal？ (y/n)"
   - **y (default):** `append_to_journal` with today's date. Links → `_discovered_links.json` (review_state: proposed)
   - **n:** Links still written to `_discovered_links.json` (review_state: rejected)

**Cycle Guard:**
- Maintain `visited_ids: Set` throughout the walk
- Each search result filtered against visited_ids
- If 2 consecutive search steps return only visited cards → end walk

## Mode 2: Shuffle (隨機抽牌)

```
/zettel-walk shuffle 3 "CMS TEAM bundled payment"
```

**Flow:**

1. Search Heptabase using 3 different Elevation Anchor dimensions as queries
   - e.g., "system resilience", "economic incentives", "clinical feedback"
2. From each dimension's results, randomly pick 1 card (exclude PDFs, empty, <100 chars)
3. Add user's anchor card (find via semantic search)
4. Read all 4 cards' full content
5. Elevate each card to its underlying principle
6. Analyze:
   - Which principles overlap? → cross-domain commonality
   - Which principles conflict? → tension / dialectic
   - If you had to write one article connecting all 4, what's the angle?
7. Output in CLI + ask to write to Journal

## Mode 3: Bridge (辯證橋接)

```
/zettel-walk bridge "PartnerA Health" "Safety-II"
```

**Flow:**

1. Find and read both target cards
2. Elevate each to underlying principle (P_A, P_B)
3. Three-layer bridge search:
   a. **Direct:** Do P_A and P_B share concepts?
   b. **One-hop:** Is there a card C related to both P_A and P_B?
   c. **Meta-elevation:** Can P_A and P_B be abstracted further to a shared meta-principle?
4. **Dialectic dimension (MANDATORY):**
   - "Under what boundary conditions do these two principles conflict?"
   - Output a `tensions_with` relation alongside any `shares_principle`
   - Frame the tension as a productive question (e.g., "how to be lean in peace AND redundant in crisis?")
5. Output in CLI + ask to write to Journal

## Mode 4: Journal (日誌回顧)

```
/zettel-walk journal
```

**Flow:**

1. Read Heptabase Journal for last 7 days (`get_journal_range`)
2. Identify:
   - Recurring themes (mentioned 2+ times across days)
   - Fragments that connect to existing Heptabase cards (semantic search)
   - Fragments worth promoting to standalone cards (candidate → canonical)
3. Output analysis in CLI
4. For each promotable fragment, ask: "Turn this into a Journal entry with card-ready format? (y/n)"

## Output Format (all modes)

Always display the full result in CLI first, THEN ask about Journal.

```markdown
## Zettel Walk — {mode} | {YYYY-MM-DD}

### Path
1. **[Card Title 1]**
   - Raw concept: "{extracted concept}"
   - Elevation anchor: {anchor name or "free abstraction"}
   - Abstracted principle: "{principle}"

2. **[Card Title 2]**
   - Raw concept: "..."
   - Elevation anchor: ...
   - Abstracted principle: "..."

### Hidden Pattern
{1-2 paragraphs explaining the cross-domain connection discovered}

### Link Evidence
| From | To | Type | Rationale | Evidence |
|------|----|------|-----------|----------|
| {card} | {card} | shares_principle | {why} | {source} |
| {card} | {card} | tensions_with | {why} | {source} |

### Bottom-Line Logic
{One sentence — the deepest insight}

### Suggested Actions
- [ ] Turn into card: "{title}"
- [ ] Blog angle: "{title}"
- [ ] Connect to existing: [{card}]
```

## Journal Entry Format

When writing to Heptabase Journal via `append_to_journal`:

**CRITICAL: Journal entries must be DETAILED, not compressed.** User explicitly requested rich context over brevity. Each card in the path needs full explanation of WHY it was chosen, WHAT the core concept is, HOW the elevation worked, and the bridging logic to the next card. Hidden pattern must show reasoning process, not just conclusion. Tensions must include concrete conflict and possible reconciliation. Aim for 400-800 words.

```markdown
---

## Zettel Walk — {mode} (完整版) | {time}

### 起點：{Card 1 title}
{2-3 sentences on card content and why we started here}
{Which concepts extracted, which chosen for elevation, why}
升維抽象：{elevated principle}
Elevation Anchor: {anchor name}

### 第二步：{Card 2 title}（{whiteboard name}）
{Why this card appeared in elevated search results}
{How it bridges to previous card's principle — the connection logic}
升維抽象：{next elevated principle}

### 第三步：{Card 3 title}
{Same detailed treatment}

### 隱藏模式
{Full reasoning — not just "they share X" but WHY they share it,
HOW the pattern manifests differently in each domain,
and WHAT this tells us about the underlying principle}

### 張力
{Specific conflict points with concrete examples}
{Possible reconciliation or productive question}

### 底層邏輯
{One sentence}

### 連結
{Each link: from ↔ to, relation_type, rationale}

### 可能的下一步
{Actionable: card to create, blog angle, cards to connect}

---
```

Use `date` parameter = today's date in YYYY-MM-DD format.

## Discovered Links Registry

After every walk (regardless of user's Journal choice), write discovered links to `_discovered_links.json`:

```json
{
  "link_id": "lk-{timestamp}-{seq}",
  "from_knowledge_id": "{kb-id or card title}",
  "to_knowledge_id": "{kb-id or card title}",
  "relation_type": "shares_principle|tensions_with|bridge_to|derives_from|applies_to|example_of",
  "rationale": "{one sentence}",
  "evidence_refs": ["{source 1}", "{source 2}"],
  "novelty_score": 0.0-1.0,
  "evidence_score": 0.0-1.0,
  "review_state": "proposed|accepted|rejected",
  "discovered_at": "{ISO timestamp}",
  "discovered_by": "zettel-walk {mode}"
}
```

Before creating links, check existing `_discovered_links.json` for duplicate from+to+relation_type. If found, update rather than create new.

## Important Rules

- **Always show full results in CLI first.** Journal is secondary output, CLI is primary.
- **Never auto-create Heptabase cards.** Journal → user decides → "Turn into card" in Heptabase UI.
- **Elevation is mandatory.** Never search with raw concepts. Always abstract first.
- **Dialectic is mandatory for Bridge mode.** Always find the tension, not just the commonality.
- All CLI output in the user's preferred language.
- If a card has `hasMore` flag in search results, use `getObject` to read full content before analyzing.
