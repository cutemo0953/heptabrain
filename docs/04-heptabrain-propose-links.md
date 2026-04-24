# Dev Spec: Heptabrain Propose Links (whiteboard 內收斂式組織)

**Version:** v1.2 DRAFT
**Date:** 2026-04-24
**Author:** Architect (Claude Code)
**Parent Spec:** `DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md` **v3.0** (2026-04-24)
**Cyberbrain Role:** Loop 2 — **Converge**（whiteboard 內收斂組織，提議 inter-card 連結與分群）
**Related Specs:**
- `DEV_SPEC_HEPTABRAIN_SYNC.md` v2.2 — knowledge transfer (Crystallize loop)
- `DEV_SPEC_ZETTEL_WALK.md` v2.2 — cross-domain divergent discovery (Diverge loop)
- `DEV_SPEC_MULTIDIMENSIONAL_ANALYSIS_EXTENSION.md` Rev 1.5 — feature-family 4D assessment (private companion)

**Status:** DRAFT — 待簽收 before implementation
**Changelog:**
- v1.0: Initial draft（2026-04-24，早版）
- v1.1: Aligned to Cyberbrain v3.0（2026-04-24 下午）:
  - 引用 v3 Four-Loop Operating Model（本 skill = Converge loop）
  - 採用 Registry Schema v2（6 provenance fields）
  - 採用 Link Class 三分法（本 skill 全部 proposed class）
  - 採用 Whiteboard Maturity gating（forming+ only）
  - 採用 Feature Family Whiteboard class（§7）取代 v1.0 的鬆散 MDA trigger
  - 新增 Gemini 建議：output option B — `🗂️` suggestion card create 到 whiteboard 本身
  - 明示 Three-plane split（CLI trigger / MCP bulk read / GUI disposition）
- **v1.2 (2026-04-24 晚):** Gemini deep-think review 收斂，6/7 採納：
  - **Auto-Accept detection**（§5.1 新增）— 若 proposed link 已出現在 whiteboard 實體 connections，自動升 `acceptance_state: accepted`；純 registry 邏輯，不改 HB 內容（對齊 Cyberbrain v3 P5 implicit acceptance 理念）
  - **Two-Pass funnel**（§2.3 Scale Tiers 改寫）— 不論 N，pair > 50 就 TF-IDF/embedding 預篩 Top 50，避免 LLM attention decay
  - **NetworkX offload**（§2.3 Step 6/7 明示）— modularity + betweenness centrality 用 Python `networkx` 計算，LLM 只做 theme naming + rationale；新增 ADR PL19
  - **Gap Signal 新增 2 種**：Merge Candidate（core principles 極度重疊 + connection pattern 相似）、Spaghetti Warning（某卡 degree > N/3 黑洞化）
  - **Spatial Anomaly**（Gemini G2）**2026-04-24 實測後 REJECTED** — `get_whiteboard_with_objects` 不返回 x/y/position；等 Heptabase AI Agent API 演進後 revisit
  - **G1 CLI batch dump 拒絕**（ADR PL6 note 更新）— CLI 是 `mcp-remote` wrapper 非 local，MCP-first 結論不變
  - ADR 新增 PL19 / PL20 / PL21（NetworkX / Auto-accept / Spatial-gated）

---

## 1. Problem

### 1.1 現有 stack 的缺口

Cyberbrain 家族目前解決了三件事：

| Skill | 行為 | 知識空間邊界 |
|-------|------|------------|
| `/heptabrain-sync push` | Memory → Heptabase（結晶化） | open（全部 memory）|
| `/heptabrain-sync pull` | Heptabase → Memory URI refs | open（全部 HB）|
| `/zettel-walk wander/shuffle/bridge` | 跨域**發散**發現 | open（跨 whiteboards）|
| `/strategic-review` + MDA | 1 feature × 4D assessment | 1 個 feature |

**缺口：** whiteboard 內的**收斂式組織**沒有工具。

使用者痛點（2026-04-24 session 提出）：
> 「whiteboard 內卡片群，由 cli 幫我 propose 彼此連結、自動幫我拉線和群組，之後我再調整？」

現況：
- Heptabase API **不支援** 拉線 / 定位 / 建 section（GUI 專屬）
- Zettel-walk 是**發散**的（出 whiteboard 找跨域連結），不是**收斂**的（同 whiteboard 內盤整）
- 手動整理 20 張卡片的 whiteboard = N(N-1)/2 = 190 pair 要想一遍，人腦極限

### 1.2 為什麼 propose（建議）而非 wire（拉線）

Cyberbrain P5 已明言：空間佈局保留給 human cognition。API 不開放 wire 不是 bug，是設計哲學。

此 skill 遵循：
- **AI propose（建議）** — 算好關係候選、分群邏輯、gap signal
- **Human dispose（決定）** — 在 HB GUI 對照 propose 文件手動拉線
- 這是 Cyberbrain P3（連結必須帶 evidence）+ P5（Journal 中繼不建卡）的延伸到 inter-card 層

### 1.3 與其他 skills 的 positioning（v1.1 對齊 Cyberbrain v3 Four-Loop Model）

```
Loop 1: Crystallize      Loop 2: Converge         Loop 3: Diverge
─────────────────        ─────────────────        ─────────────────
/heptabrain-sync         /heptabrain-propose-links /zettel-walk
  (本 skill 位置)          (本 spec)

memory → HB cards        單 whiteboard 盤整        跨 whiteboard 找橋
                         ↑                        ↓
                    intra-convergence      inter-divergence
                    收斂 / 鞏固             發散 / 擴張

Loop 4: Abstract
─────────────────
/strategic-review + MDA
  (feature × 4D)
                         ↑ reuses
                    edges for MDA sketch
```

四迴圈皆讀寫 `_discovered_links.json`（registry v2）作為 governance layer，見 Cyberbrain v3 §4.

---

## 2. Core Mechanism

### 2.1 Closed-Set Discipline

Propose-Links **只看使用者指定的單一 whiteboard**，不進行跨 whiteboard 探索。

```
Input:  whiteboard_id 或 whiteboard keyword
        ↓
Scope:  該 whiteboard 上的 N 張 cards（包括 card / pdfCard / mediaCard / highlightElement）
        ↓
Output: 建議 links + 建議 groupings + 比對既有 connections + gap signal
        (+ optional: 🗂️ suggestion card 建進 whiteboard 本身，見 §4.5)
```

**為什麼 closed-set：** 若同時打開跨 whiteboard，功能上與 zettel-walk 重疊，且 N² 分析爆炸。要做跨 whiteboard 的收斂，先用 zettel-walk 發現連結 → 該連結進同一 whiteboard → 再跑 propose-links。

### 2.1.1 Whiteboard Maturity Gating（v1.1 新增，對齊 Cyberbrain v3 §6）

依 target whiteboard 的 maturity 決定是否執行：

| Whiteboard maturity | Propose-Links 執行 | 理由 |
|--------------------|------------------|------|
| `seed`（<5 cards）| ❌ **拒絕執行** | 資料太少，分群無意義 |
| `forming`（5-15 cards）| ✅ 核心使用場景 | 結構正在形成，AI 提議最有價值 |
| `structured`（15-40 cards）| ✅ 可定期 audit | 用於定期 convergence 檢查 |
| `canonical`（stable, low write）| ⚠️ 限制執行 | 結構穩定，不該頻繁 re-organize；若用則給「audit-only mode」warning |

Maturity 偵測：
1. 讀 whiteboard title 是否含 `[maturity:<state>]` 字串（v3.0 convention）
2. 若無，依 card count heuristic 推斷，提示 user 補標記

### 2.2 Relation Taxonomy — 重用既有

**不創造新 edge types**。本 skill 重用 Cyberbrain family 已定義的 11 種：

**Zettel-Walk 定義的 7 種：**
- `supports` — A 支持 B 的論點
- `contradicts` — A 與 B 矛盾
- `derives_from` — A 源自 B
- `applies_to` — A 是 B 的應用實例
- `example_of` — A 是 B 原則的範例
- `bridge_to` — A 架橋到 B（跨域）
- `tensions_with` — A 與 B 有張力（辯證）

**MDA 新增的 3 種：**
- `synergizes-with` — 雙向互增強（multiplies_with 的 edge 形式）
- `attracts` — proximity pull（拉近 actor 關係）
- `precedes` — temporal 前置（B 要等 A 已在位）

**Zettel-Walk output 中用到的 1 種（未正式列但已存在 registry）：**
- `shares_principle` — A 和 B 共享底層原則

共 **11 種**。若 propose 時發現 AI 想用的關係不在此表 → fallback `related_to` 並標 `needs_taxonomy_review: true`，進 audit queue。不可私自擴充詞彙。

### 2.3 分析流程（AI 模型角色）

**Scale tiers（v1.2 改為 Two-Pass funnel，不論 N 統一 top 50 hard cap）：**

| N（分析中的 cards）| 處理 |
|-------------------|------|
| N < 8 | 不執行分群；仍可做 pair analysis（至多 28 pair），主訴 user「whiteboard 太小，分群無意義」|
| 8 ≤ N ≤ 50 | **Two-Pass funnel**：Pass 1（TF-IDF / keyword overlap / embedding 預篩）→ Top 50 pairs；Pass 2（LLM 深度分析）僅這 50 pair |
| N > 50 | **Hard stop**。回報「whiteboard 超過 50 cards，請先於 HB UI 拆 section 或縮小 scope 再跑」|

**為什麼連 N ≤ 20 都要 funnel（v1.2 修正 v1.1）：** N=20 產生 190 pair，即便不觸 hard stop，LLM 在單 prompt 內評估 190 對會 attention decay（偷懶 / 硬湊 rationale）。Gemini 2026-04-24 review 明言此點，實驗證據充分。統一 50 hard cap 給所有 N，避免不同 tier 行為差異。

（同 scale 決策反映於 §8.7 ADR PL7。）

**Two-Pass funnel 實作建議：**
- Pass 1 用 Python script 計算（成本低、精準度夠）：
  - TF-IDF on card titles + tags + first 500 chars
  - Cosine similarity → rank → top 50 pair
- Pass 2 LLM 對每 pair 做：core principles 萃取 / elevation anchor 映射 / relation_type 決定 / rationale 撰寫 / confidence 評級

```
Step 1: Whiteboard discovery
  - 若輸入是 keyword → search_whiteboards → 可能多個 match → user 挑選
  - 若輸入是 id → 直接用
  → 取得 whiteboard_id

Step 2: Card inventory
  - get_whiteboard_with_objects(whiteboard_id)
  - 結果含：所有 objects + 既有 connections
  - 過濾：只保留 card / pdfCard / mediaCard / highlightElement（不分析 section 文字、image）
  - 依上表 scale tier 決定下一步；N > 50 → hard stop

Step 3: Parallel card read
  - 對每張 card 跑 get_object（並行，MCP session）
  - 抽取：title + core concepts（3-5 個）+ tags + lastEdited
  - PDF cards：只讀 title + tags，不讀全文（內容量過大）

Step 4: Pair analysis（依 §2.3 scale tiers 決定 pair 數）
  - 對每 pair 跑：
      - 萃取雙方 core principles
      - 映射至 Elevation Anchor（zettel-walk 共用的 5 維）
      - 決定 relation_type（從 11 種中選 1，或 related_to + needs_review）
      - 寫 rationale（1-2 sentence）
      - 評分 confidence（high / med / low）

Step 5: Existing connection diff
  - 從 Step 2 的 whiteboard objects 中萃取既有 connections
  - 對每個提議 link 標記：
      - NEW：AI 提議，whiteboard 無此連結
      - EXISTS：已存在（AI 為你驗證一次 rationale 合理性）
      - REDUNDANT：已存在相同或近似連結，不必重複
      - CONFLICT：既有 connection 與 AI 分析結果矛盾（標 warning）

Step 6: Clustering proposal（v1.2 明示 NetworkX offload）
  - 以 proposed + existing links 為 graph edges
  - **不由 LLM 腦算 modularity**（不可靠）→ 寫 edge list + node list 到 `/tmp/propose_links_{ts}.json`
  - 跑 Python helper `scripts/hb_clustering_helper.py` 用 `networkx.algorithms.community.louvain_communities`
  - Python 輸出 JSON: `{clusters: [{nodes: [...], density: float}], ...}`
  - LLM 讀回 JSON → 為每 cluster 命名 theme（3-8 張卡片 / 群）+ 寫 rationale
  - 孤島卡片（degree < 2）由 Step 7 handle

Step 7: Gap signal（v1.2 擴充至 5 類）
  - NetworkX 同一次 script 計算 betweenness centrality + 各 node degree
  - LLM 依 Python 算出的數字判定以下 5 類 gap signal：

    **🔹 Weak integration**（v1.1 既有）: degree < 2 的卡片。建議 user 拉多 1-2 條連結或 rethink 位置
    **🔹 Central hub**（v1.1 既有）: 高 betweenness 的卡片。建議放 whiteboard 物理中央
    **🔹 Fragile bridge**（v1.1 既有）: community 間只靠 1-2 條 bridge edge 的脆弱結構。建議加 redundant bridge
    **🔹 Merge candidate**（v1.2 新增，Gemini G6）: pair 的 confidence = high + rationale 指向「相同概念不同詞彙」 + 兩卡 existing connections 重疊度 > 70%。建議 user 在 HB GUI 考慮合併為一張（真正的降維去冗餘）
    **🔹 Spaghetti warning**（v1.2 新增，Gemini G7）: 某卡 degree > N/3（dynamic threshold）— 概念過載 / 黑洞化。建議（1）抽象為高維原則另建卡、或（2）拆為 2-3 張子卡

  - 若 `scripts/hb_clustering_helper.py` 失敗（例 networkx 未安裝）→ fallback LLM 粗估 + warning「圖論精度降級」

Step 8: Output
  - 寫 propose_links/<date>_<whiteboard-slug>.md（human-readable）
  - 寫 entries 到 _discovered_links.json（machine-readable，同 zettel-walk registry）
  - 可選：append 摘要到今天 Heptabase Journal（同 zettel-walk 模式）
```

### 2.4 Feature Family Whiteboard Integration（v1.1 升級，引用 Cyberbrain v3 §7）

**v1.0 原本是「MDA auto-detect」**，v1.1 改用 Cyberbrain v3 正式的 **Feature Family Whiteboard class** 作為 trigger 條件。

**Feature Family Whiteboard class 最低組成**（對齊 v3 §7.1）：1 Case Card + 1 Principle Card + 1 Open Question Card + 1 Lens Card/MDA Anchor + ≥ 3 Accepted Edges。

Propose-Links 偵測 target 符合 Feature Family class → 自動啟用 4D 投影素描；不符合但 user 用 `--mda` 強制 → 仍執行但附 warning「此 whiteboard 未達 Feature Family 最低組成，4D 分析可能稀薄」。

**4D 投影素描內容（例：一個產品功能或倡議所集結的 specs / ADRs / retrospectives 群集）：**

- **Synergy lens**: 提議的 links 中哪些屬 synergy（amplifies / depends_on / enables / multiplies_with / blocks）？產生 synergy sub-graph。
- **Proximity lens**: 若卡片有 actor 標記（L0-L3），畫出 proximity layers 分布。
- **Temporal lens**: 若卡片含 release date / phase，推斷 temporal precedence。
- **Perspective lens**: 若某 actor 的卡片密集，建議其 Perspective Card 的存在/缺失。

**Trigger：** whiteboard title 或 tag 包含 `feature`, `spec`, `strategic-review`, `mda` 時自動提示 user「是否啟用 4D MDA 素描？」

**Output：** 額外寫一個 `mda_sketch/` 子檔，不混在主 propose 檔。

### 2.5 Clustering 決策邏輯

**為什麼用 modularity optimization 而非 hierarchical clustering：**
- Whiteboard 的卡片群傾向扁平（使用者已手動分過層）
- Modularity 對小 N（10-50）表現好，不需 cut threshold tuning
- Density-based（如 DBSCAN）需要 distance metric，語意距離不穩

**不套用時機：**
- N < 8：直接列 cards 不分群（分群無意義）
- Single dominant theme：單一主題 whiteboard 不強分群

---

## 3. Skill Interface

```
/heptabrain-propose-links "{whiteboard name or keywords}"       — 基本模式
/heptabrain-propose-links "{whiteboard}" --max-links N          — 限制建議數
/heptabrain-propose-links "{whiteboard}" --mda                  — 強制啟用 4D 素描
/heptabrain-propose-links "{whiteboard}" --dry-run              — 只跑 Step 1-3 看 inventory，不分析 pair
/heptabrain-propose-links "{whiteboard}" --journal              — 強制附到今天 Journal
/heptabrain-propose-links "{whiteboard}" --suggestion-card      — 產 🗂️ 建議卡到 whiteboard（v1.1 新增）
/heptabrain-propose-links "{whiteboard}" --audit-only           — 僅對 canonical maturity whiteboard 跑審計
```

**Arguments：**

| Arg | 用途 |
|-----|------|
| whiteboard | 必填。Name keyword 或 id。Name match 若多個則 user 挑。|
| `--max-links N` | 可選。預設 20。超過 20 的低信心建議折進 appendix。|
| `--mda` | 可選。強制啟用 4D 素描（預設 Feature Family class 才 auto-trigger）。|
| `--dry-run` | 可選。只跑 inventory（Step 1-3），不跑 pair analysis。|
| `--journal` | 可選。強制 append Journal。預設是問 user。|
| `--suggestion-card` | 可選。產 🗂️ 建議卡進 whiteboard（§4.5）。Opt-in，預設不產。 |
| `--audit-only` | 可選。針對 `canonical` maturity 的 whiteboard，只跑 audit（不提新 link，僅驗 existing + stale detection）。 |

**Three-plane 執行角色（v1.1 新增，對齊 Cyberbrain v3 §8）：**

| Plane | 本 skill 使用方式 |
|-------|---------------|
| CLI (Control) | 未來 cron 可跑 `heptabase search-whiteboards` 預掃；互動觸發 by `/heptabrain-propose-links` |
| MCP (Data) | 核心 — 並行 `get_object` N 張 card + `get_whiteboard_with_objects` |
| GUI (Confirmation) | User 依 propose_links.md 在 HB 手動拉線 / 圈 section；選擇性以 🗂️ 建議卡留痕 |

---

## 4. Output Format

### 4.1 Main output: `propose_links/YYYY-MM-DD_<slug>.md`

**Re-run within same day policy：** 若同一天對同一 whiteboard 重跑，檔名加 `_rN` 後綴（e.g. `2026-04-24_irehab-service_r2.md`）。不 overwrite 先前輸出；保留所有 run 方便 user 比對。跨天 run 無需後綴（不同日期已區分）。Registry 層 (`_discovered_links.json`) 仍走 §5.1 重複偵測邏輯，不因 main output 版本化而重複寫 entry。


```markdown
# Propose Links — {whiteboard name} | {YYYY-MM-DD}

## Inventory

- Whiteboard: {name} (id: {whiteboard_id})
- Cards analyzed: {N} (skipped: {pdf_skipped}, filtered: {sections/images})
- Existing connections: {M}
- Analysis mode: {standard | mda}

## Proposed New Links ({count})

Confidence: 🟢 high / 🟡 med / 🔴 low

### 🟢 High confidence ({n1})

- [ ] **{Card A title}** → **{Card B title}**
  - Type: `shares_principle`
  - Rationale: {一句話}
  - Evidence: {Card A 的 §X / Card B 的 §Y}
  - Action in HB: 拉線 + 標 "shares_principle"

### 🟡 Medium confidence ({n2})
...

### 🔴 Low confidence ({n3}, appendix)
{摺疊於 details block，供 user 翻閱}

## Existing Connections (已有，驗證一次)

- ✅ {Card A} ↔ {Card B} (current, 與 AI 分析一致)
- ⚠️ {Card C} ↔ {Card D} (current, AI 分析認為 relation type 應為 `tensions_with` 而非現有 `supports`)
- 🔁 {Card E} ↔ {Card F} (current, AI 也提議此連結 — REDUNDANT)

## Proposed Groupings

- **Group α** — 主題：{detected pattern}
  Cards: [{Card 1}, {Card 2}, {Card 3}, {Card 4}]
  Intra-group density: {X}%
  建議動作：HB 圈 section，命名 "{theme}"

- **Group β** — ...

## Gap Signals

- 🔹 **Weak integration** (degree < 2): 
    - {Card Z} — 目前只連到 {Card Y}。建議：{1-2 specific proposed links from above that would strengthen this card}
- 🔹 **Central hub** (高 betweenness): 
    - {Card Q} — 連結多個 cluster，建議 HB 物理位置放中央
- 🔹 **Fragile bridge** (單一連結跨 community):
    - {Group α ↔ Group β} 只靠 {Card M → Card N}。建議加 1-2 條 redundant bridge。

## MDA Sketch (若 --mda)

### Synergy sub-graph
- `amplifies`: {pair list}
- `depends_on`: {pair list}
- ...

### Proximity layers
{若可偵測}

### Temporal precedence
{若可偵測}

### Perspective Rotation suggestions
- 此 whiteboard 主要是 {actor} 視角。建議補 Perspective Card 從 {另一 actor} 角度。

## Summary

- Links NEW: {count}
- Links EXIST: {count}
- Groups suggested: {count}
- Weak-integration cards: {count}
- Estimated GUI drawing time: ~{N} min
```

### 4.2 Machine-readable: `_discovered_links.json` entries (Schema v2)

每個 NEW link 寫一 entry，對齊 **Cyberbrain v3 §3.2 Registry Schema v2**：

```json
{
  "link_id": "lk-{timestamp}-{seq}",
  "from_knowledge_id": "hb-card:{card_id_or_slug}",
  "to_knowledge_id": "hb-card:{card_id_or_slug}",
  "relation_type": "shares_principle",
  "rationale": "...",
  "evidence_refs": ["Card A §X", "Card B §Y"],
  "novelty_score": null,      // propose-links 不算 novelty（closed set）
  "evidence_score": 0.0-1.0,

  "// v3 provenance fields": "",
  "link_class": "proposed",
  "acceptance_state": "proposed",
  "scope_type": "whiteboard",
  "scope_whiteboard_id": "{whiteboard_id}",
  "source_mode": "propose-links",
  "evidence_kind": ["text_overlap", "shared_actor"],
  "last_verified_at": "{ISO timestamp}",
  "verified_by": "ai",

  "// legacy compat": "",
  "confidence": "high|med|low",
  "review_state": "proposed",
  "discovered_at": "{ISO timestamp}",
  "discovered_by": "propose-links"
}
```

**Class 固定為 `proposed`**（本 skill 產出的 links 均為 proposed class，不產 canonical / exploratory）。Acceptance 流向 canonical 由 user 手動升級，對齊 v3 §5.4 workflow。

### 4.3 Journal append（optional，user prompt）

類似 zettel-walk 的 journal flow：

```markdown
---

## Propose Links — {whiteboard name} | {time}

### Whiteboard 掃描結果
{inventory summary}

### 最有料的 5 個新連結
1. {Card A} → {Card B}: {rationale}
...

### 建議分群
- Group α: {theme} — {N} cards
- Group β: {theme} — {N} cards

### 最弱的 2 張卡片
- {Card Z}: 只有 1 連結。可能需要 rethink 位置或加補連結。

### 下一步建議
- [ ] HB 按 propose_links/{file}.md 執行拉線
- [ ] 若 Gap Signal 嚴重 → 考慮寫新卡片補洞
- [ ] 若某 Group 自然浮現 → 考慮獨立為新 whiteboard

---
```

### 4.4 Output Rules

- **CLI first, Journal second**：無論 user 選不選 journal，CLI 永遠先顯示完整結果（同 zettel-walk 原則）
- **不自動改既有 whiteboard 結構**：不拉線、不移位、不刪卡
- **可選擇性 create 一張明確標記的建議卡**（§4.5 新增，v1.1）— 對齊 Cyberbrain v3 P5 的 ephemeral-vs-canonical 邊界：新卡不改既有語義
- **所有 CLI output 中文化**

### 4.5 Optional Output C: 🗂️ Suggestion Card in Whiteboard（v1.1 新增，採納 Gemini tactic）

對齊 Cyberbrain v3 P5 之「新增卡 = 不改既有結構 = 不需 human gate」原則：

**User flag `--suggestion-card`（或互動提問）啟用：**

Skill 會在 target whiteboard **自動 create 一張明確標記的 suggestion card**：

```markdown
# 🗂️ {whiteboard name} 組織建議 — {YYYY-MM-DD}

（由 /heptabrain-propose-links 於 {ISO timestamp} 自動產出，非 canonical 內容，僅供參考。移除本卡不影響 whiteboard 結構。）

## 建議 New Links（{count}）
- [ ] {Card A} → {Card B}: {relation_type} — {confidence}
  - Rationale: ...
...

## 建議 Groupings
- Group α: {theme} — [{Card 1}, {Card 2}, {Card 3}]
...

## Gap Signals
- Weak integration: {Card X, Card Y}
- Fragile bridge: {Group α ↔ β}

## 下次 re-run 前 checklist
- [ ] 已決定哪些 links 要拉
- [ ] 已決定哪些 cards 要圈 section
- [ ] 可以刪除本卡，或讓其自然過期（建議 14 天）
```

**Card 治理：**
- Title 必以 `🗂️` 開頭（UI 上容易辨識為 AI 產出）
- 內含 created_at + skill version + whiteboard snapshot metadata
- 相同 whiteboard 再跑 propose-links → 新卡不覆寫舊卡；舊卡留 14 天 tag `stale`（未來 GC 流程）
- User 隨時手動刪除不影響系統

**為什麼不違反 Cyberbrain v3 P5 ephemeral-vs-canonical rule：**
- 🗂️ 前綴明示非 canonical（user 不會誤認為 authoritative 主題卡）
- 不改既有 cards / connections / sections
- 14 天 stale + auto-GC 確保不污染長期 graph
- User 可刪，零 lock-in

**默認行為：** `--suggestion-card` 是 opt-in（不是預設）。首次用戶需明示要產 card；後續可在 `~/.claude/config/heptabrain.json` 設 default。

---

## 5. Registry Integration

### 5.1 `_discovered_links.json`（共用 zettel-walk）— v3 Schema v2

- 同 registry，`source_mode` 區分來源（`propose-links` vs `zettel-walk:wander` 等）
- **Registry initialization**：若檔案不存在，依 parent spec (`DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md` v3 §3.2–§3.3) 預設 v2 schema 初始化為 `[]`
- 重複偵測：寫入前查 `from_knowledge_id + to_knowledge_id + relation_type + scope_whiteboard_id` 是否已存在
  - 已存在 → update `last_verified_at` 最新、`acceptance_state` 不動
  - 不存在 → 新增，**預設 `acceptance_state: "proposed"`** + `link_class: "proposed"`
- Legacy v2.1 entries（無 v2 欄位）讀取時依 Cyberbrain v3 §3.3 migration rules fallback；寫入時必填 v2 欄位
- 用意：若 zettel-walk 和 propose-links 各自找到相同連結，只算一次；但 scope_whiteboard_id 不同（跨域 vs whiteboard-internal）視為不同 entry

### 5.1.1 Auto-accept Detection（v1.2 新增，Gemini G3 採納）

**問題 v1.1 未解：** `_discovered_links.json` 的 entries 若無人手動改 `acceptance_state`，會永遠停在 `proposed`，形成「proposed 死水」。人類不會去手改 JSON。

**v1.2 解法：** 每次跑 propose-links 時，Step 5 Existing Connection Diff 額外做：

```python
# 流程（pseudocode）
for link in registry.filter(
    scope_whiteboard_id == current_whiteboard_id,
    acceptance_state == "proposed"
):
    if link.from → link.to 這條 edge 已出現於 whiteboard 的 real connections:
        link.acceptance_state = "accepted"
        link.last_verified_at = now()
        link.verified_by = "mixed"  # AI 當初提議 + user GUI 拉線確認
        registry.update(link)
        implicit_accepts += 1
    else:
        # 該 link 仍 proposed；不動
        pass
```

**UX 流程（完全零摩擦）：**
1. Day N: `/heptabrain-propose-links "whiteboard X"` → 提議 10 條 new links，全部 `proposed` 寫入 registry
2. Day N: user 看 propose_links_{date}.md，在 HB GUI 手動拉其中 6 條
3. Day N+14: re-run propose-links → Step 5 diff 發現 6 條已在 whiteboard 實體 connections → **自動**升級這 6 條為 `accepted`（user 不需手動改 JSON）
4. 剩 4 條仍 proposed → 下次 audit 評估是否 stale / rejected

**為什麼不違反 Cyberbrain v3 P5（human-in-loop）：**
- AI 是 **observer**（觀察 GUI 拉線結果），不是 actor（沒有自動拉線）
- User 拉線本身就是 disposition 動作，registry 只是記錄結果
- 完全對齊 Cyberbrain v3 §5.4 Acceptance Workflow 的 `proposed → accepted` 轉換條件（user 明示或隱示確認）

**Log：** 每次 auto-accept 發生時記 audit log：`{link_id, whiteboard_id, detected_at, implicit: true}`，方便 later audit 辨識是 AI 推斷的 accepted（區別於 user 顯式改的）。

### 5.2 `_heptabrain_registry.json`（讀取，不寫入）

- Propose-links 會查 registry 看哪些卡片是 memory-synced canonical
- 若某卡是 canonical 且連到 candidate，可提示：「此 link 把 candidate 與 canonical 串起來，值得優先接受」
- 不寫入 registry（不是 sync 動作）

### 5.3 `_heptabase_refs.json`

不使用。此 skill 的工作單位是 whiteboard 而非 session topic。

---

## 6. 何時使用 Propose-Links

### 6.1 建議使用時機

- 累積新卡片到某 whiteboard 超過 10 張且已久沒整理
- 一場 zettel-walk 產出多個新連結，想回頭「收斂」進入某 whiteboard
- Strategic Review 後的 feature family whiteboard 要做 4D MDA 素描
- 新 whiteboard 剛起步，想讓 AI 幫看看有沒有 implicit structure
- 擔心 whiteboard 結構老化、孤島卡片累積

### 6.2 不建議使用時機

- **單 whiteboard 卡片 < 8 張** → 分群無意義，手動看一眼即可
- **PDF-heavy whiteboard** → 多數 object 被 filter 掉，分析結果稀薄
- **剛跑完（< 24h）** → 除非大量新增卡片，否則結構變化不大
- **想找跨域連結** → 用 zettel-walk，不用 propose-links

### 6.3 與 zettel-walk 的配合模式

**Divergent → Convergent cycle：**

```
1. /zettel-walk wander "{concept}" → 發現跨域連結寫入 Journal
2. User 在 HB 把 Journal 好段「Turn into card」建到 whiteboard A
3. 累積後 → /heptabrain-propose-links "whiteboard A"
4. Propose-links 提議 intra-whiteboard 組織
5. User 在 HB 手動拉線/分群
6. 結構穩定後 → 下次 zettel-walk 可再 wander 出去
```

---

## 7. Implementation Plan

| Step | 內容 | 預估 |
|------|------|------|
| **0** | **`pip install networkx scikit-learn` + 建立 `scripts/hb_clustering_helper.py`**（v1.2 新增）| 20 min |
| 1 | 建立 `~/.claude/commands/heptabrain-propose-links.md` skill | 30 min |
| 2 | 實作 Step 1-3（whiteboard discovery + card inventory + parallel MCP read） | 20 min |
| 3 | 實作 Step 4 **Two-Pass funnel**（TF-IDF Pass 1 + LLM Pass 2，v1.2 更新）+ relation taxonomy enforcement | 40 min |
| 4 | 實作 Step 5 existing connection diff **+ Auto-accept detection 邏輯（v1.2 新增）**| 25 min |
| 5 | 實作 Step 6 NetworkX offload（edge list → Python → JSON → LLM theme naming）+ Step 7 Gap Signal 5 類（v1.2 擴充）| 40 min |
| 6 | 實作 Step 8 output format（main doc + registry entries + optional journal + optional 🗂️ card） | 25 min |
| 7 | 實作 MDA sketch（optional，Feature Family Whiteboard 觸發） | 20 min |
| 8 | 測試：一個 real whiteboard（挑一個累積 10-20 張卡片且久未整理的 whiteboard 實跑）+ 次跑測 auto-accept 行為 | 30 min |
| 9 | 文件化 examples 到 examples/propose-links/ | 15 min |

**Total：~4 hours**（v1.2 因 NetworkX helper + Auto-accept + Two-Pass funnel 增 ~1 hour）

**路徑選擇（v1.2 重申）：** Data plane 全用 MCP（不用 CLI）— 大量 get_object 並行 MCP ~100ms × N vs CLI ~4s × N（N=20 即 2s vs 80s）。Gemini G1 建議的「CLI batch dump」基於「CLI is local」前提，但實測 CLI = `mcp-remote` wrapper 非 local（見 ADR PL6 更新）。

---

## 8. Design Decisions

### 8.1 為什麼 closed-set 而非 open？

Zettel-walk 已覆蓋 open exploration。若 propose-links 也 open，會變成 zettel-walk Mode 5。Closed-set 的獨特價值：**鞏固結構** vs **擴張視野**。

### 8.2 為什麼重用 11 種 edge types 而非新創？

Cyberbrain family 的 edge taxonomy 是 controlled vocabulary（見 Heptabrain Sync spec 和 Zettel-Walk spec）。新創 edge type = 方言、fragmentation。若 11 種不夠用，跑 audit queue 讓 user 決定升級 taxonomy。

### 8.3 為什麼 confidence 是 categorical（high/med/low）？

對應 MDA Rev 1.5 ADR MDA5（pull_strength 採 categorical）— 避免偽精確。建議 threshold：
- **high**: 3+ 個強證據（原則重疊 + keyword overlap + 同 actor 維度 + 時序吻合）
- **med**: 2 個證據
- **low**: 1 個證據或純 AI 推測

### 8.4 為什麼不自動拉線（即使未來 API 開放）？

Cyberbrain P5：空間佈局是 human cognition。即使 API 開放，本 skill 仍應保留 propose-only 模式，由 user 決定是否啟動 auto-wire（另一個 skill flag）。這是哲學決策，不是技術限制。

### 8.5 為什麼 MDA 整合是 optional 不是必選？

MDA 針對 feature family 的 4D 評估有意義；對概念型 whiteboard（例：「Safety-II 研究」）強行套 4D 會 noise。Auto-detect + 可強制 override 的二級設計。

### 8.6 為什麼不做跨 whiteboard 版本？

見 8.1。跨 whiteboard 是 zettel-walk 的 job。若 user 想收斂多個 whiteboard，先 merge whiteboards（HB UI），再 propose-links。

### 8.7 為什麼 N > 50 就 hard stop？

- Pair 數 N(N-1)/2 在 N=50 是 1225，即使 cap 到 top 50 仍需 user 驗證 50 條建議
- Whiteboard 超過 50 卡片通常意味著「該拆 section 了」— 本 skill 的 hard stop 是正向引導

### 8.8 為什麼 Gap Signal 不自動建卡？

Cyberbrain P5（Journal 中繼）+ AI 建卡 = 高風險亂種。Gap signal 只報告，不行動。若 user 覺得 gap 值得補 → 手動建卡或用其他 skill。

---

## 9. Edge Cases

| Case | 處理 |
|------|------|
| Whiteboard 只有 1 張 card | 回報 "whiteboard 卡片太少，不執行"，建議先累積 |
| Whiteboard 有 >50 cards | Hard stop + 建議 user 拆 section 再跑 |
| Whiteboard 全是 PDF | 只做 title/tag 分析，不讀 PDF 內容；標 "PDF-heavy" warning |
| 某張 card 無 title 或 empty | Skip，在 inventory 列出 "skipped due to empty content" |
| AI 想用的 relation type 不在 11 種 | Fallback `related_to` + `needs_taxonomy_review: true`；進 audit queue |
| Whiteboard name 匹配多個 | 列清單讓 user 選編號；若只給 1 結果，直接用 |
| 所有 pairs 都 low confidence | 警告「whiteboard cards 語意差異大，可能不是合理的 grouping」；建議拆 |
| MDA auto-detect 觸發但卡片無 MDA meta | 仍可跑但 Synergy / Proximity 可能 sparse；附 note |
| `_discovered_links.json` 有 conflict（已 accepted 但 AI 又提相同 pair 不同 type）| 標 CONFLICT 不覆蓋；user 決定 |
| 超過 10 min 仍未完成 | Timeout，輸出 partial 結果 + warning |

---

## 10. Out of Scope (v1.2)

- **自動拉線（auto-wire）** — API 不支援 + 哲學決策（§8.4）
- **自動定位（auto-position）** — 無 coordinate API
- **跨 whiteboard** — zettel-walk 的 job（§8.6）
- **Relation strength 數值評分** — 保持 categorical（§8.3）
- **MDA Layer B graph algorithms** — MDA spec §3.2，等累積 10+ reviews
- **Whiteboard 演化追蹤** — propose N 次後的 diff/growth chart，遠期
- **多語 rationale** — 預設中文；英文版等使用者明確要
- **CLI batch dump** — Gemini G1 建議，拒絕（ADR PL6 v1.2 note：CLI 是 mcp-remote wrapper 非 local）

**v1.1 原 out-of-scope 在 v1.2 改狀態：**

| 原 v1.1 out-of-scope | v1.2 狀態 | 原因 |
|------------------|---------|------|
| 自動 review_state 升降級 | **Moved to `§5.1.1 Auto-accept Detection`**（v1.2 Gemini G3 採納）| AI 是 observer，不是 actor；observing user 在 GUI 實際拉線結果合 P5 human-in-loop |

**v1.2 Rejected items：**

- **Spatial Anomaly gap signal**（Gemini G2）— **REJECTED** 2026-04-24。實測 `get_whiteboard_with_objects` 不回傳 x/y/position 任何形式座標，feature 技術不可行。等 Heptabase AI Agent API 開放「View mention links, sub-whiteboards, and more」後 revisit。（ADR PL21 詳情）

---

## 11. Architecture Decision Records

| ID | 決策 | 理由 |
|----|------|------|
| **PL1** | Closed-set input（單一 whiteboard）| 避免與 zettel-walk 功能重疊；確保 N² scope 可控 |
| **PL2** | 重用 11 種 edge types，不新創 | 防詞彙 fragmentation；若不夠用走 audit 升級，不私自擴充 |
| **PL3** | Write to `_discovered_links.json` 共用 registry | 與 zettel-walk 同一 source of truth；`discovered_by` 區分來源 |
| **PL4** | Confidence 採 categorical | 對齊 MDA5；避免偽精確 |
| **PL5** | 不自動建卡 / 不自動拉線 | 符合 Cyberbrain P5；Human dispose rule |
| **PL6** | 全用 MCP（不走 CLI）| N × get_object 平行讀取，MCP session 快 40×；CLI 每 call 4s 不可行 |
| **PL7** | N > 50 hard stop | 超過人類 working memory 可核對數；正向引導拆 section |
| **PL8** | MDA integration optional，非必選 | 對非 feature-family whiteboard 強套 4D = noise；auto-detect + override |
| **PL9** | 新欄位 `scope_whiteboard_id` 加入 `_discovered_links.json` schema | 讓未來 audit 可回溯「此連結是否仍在同 whiteboard scope」；向後相容（既有 entries 此欄位為 null）|
| **PL10** | Clustering 用 modularity optimization（不用 hierarchical/density）| 小 N（10-50）modularity 表現最穩；不需 threshold tuning |
| **PL11** | Gap signal 包含「fragile bridge」（不只孤島）| 單一 bridge 跨 community 是結構弱點；主動提示避免 user 忽略 |
| **PL12** | Journal append 是 optional 不是必選 | 對齊 zettel-walk 設計；user 決定哪些值得留入 Journal |
| **PL13** (v1.1) | `--suggestion-card` 是 opt-in 不是預設 | 對齊 Cyberbrain v3 P5；讓 user 有意識選「要在 whiteboard 留痕跡 vs 只要 markdown 檔」|
| **PL14** (v1.1) | 🗂️ 建議卡必有 emoji 前綴 + 14 天 stale + auto-GC | Cyberbrain v3 P5 ephemeral-vs-canonical 邊界；讓建議卡不污染 long-term graph |
| **PL15** (v1.1) | Whiteboard maturity gating — seed 拒絕、forming+ 核心、canonical 限制 | 不同 maturity 需要不同頻率；v3 §6 明示此原則 |
| **PL16** (v1.1) | Feature Family Whiteboard class 取代 v1.0 的鬆散 MDA trigger | v3 §7 正式化結構；需最低組成才自動 4D 素描 |
| **PL17** (v1.1) | 本 skill 產出的 links 一律 `link_class: proposed` | 對齊 v3 §5.1 三分法；canonical 升級需 human acceptance |
| **PL18** (v1.1) | Registry writes 必填 v2 schema 全欄位 | 向前 migrate；legacy entries 讀時 fallback，不寫回 |
| **PL19** (v1.2, Gemini G5) | Graph algo（modularity / betweenness / degree）**offload 到 Python `networkx`** | LLM 不可靠算圖論 numerical；NetworkX 成熟穩定；LLM 只做 theme naming + rationale |
| **PL20** (v1.2, Gemini G3) | **Auto-accept detection** — proposed link 若出現在 whiteboard real connections → 自動升 `accepted` | 解決「proposed 死水」問題；AI 是 observer 非 actor，不違反 Cyberbrain v3 P5；純 registry 邏輯無 HB write |
| **PL21** (v1.2, Gemini G2) | Spatial Anomaly gap signal **REJECTED** until Heptabase API evolves | **2026-04-24 實測**：對 18-card whiteboard 跑 `get_whiteboard_with_objects`，response XML 含 `<card id title totalChunks hasMore>` / `<connection beginId endId direction>` / `<section title objectIds>`，**全無 x/y/position 任何形式座標**。雖然 tool 說明提到 "position" 是可能 attribute，實際 API 不返回。等 Heptabase AI Agent API 釋出「View mention links, sub-whiteboards, and more」後（roadmap 進行中）再 revisit |
| **PL6 v1.2 note** | **MCP-first 結論不變**（拒絕 Gemini G1 CLI batch dump） | CLI 是 `mcp-remote` wrapper 非 local（實測 2026-04-23 證實）；batch dump 前提錯誤 |
| **PL22** (v1.2) | Two-Pass funnel 統一所有 N（不論 tier），pair 數 > 50 強制 TF-IDF 預篩 | LLM attention decay 在 190 pair 已顯著；Gemini G4 實驗證據充分 |
| **PL23** (v1.2) | Gap Signal 由 3 類擴為 5 類（+ Merge Candidate + Spaghetti Warning）| 分別對應「收斂」的兩極端：重疊太高（該合）vs 黑洞化（該拆）|

---

## 12. Success Metrics

| 指標 | 基線 | v1 目標 |
|------|-----|---------|
| 每次 propose-links 執行時間 | — | < 2 min（whiteboard ≤ 20 cards）|
| NEW links 建議中被 user accepted 比例 | — | > 40% |
| REDUNDANT 被正確偵測率 | — | > 80% |
| 單次執行後手動拉線的 GUI 時間 | 無工具時 ~30 min（20 cards）| < 10 min |
| 產生的 discovered_links entries | — | 每次 5-15 entries |
| **Implicit acceptance rate (v1.2)** | — | > 60% proposed 在 14 天內偵測到 real connection = user 有跟上建議 |
| **Merge Candidate precision (v1.2)** | — | > 70%（user 確認該對確實值得合併）|
| **Spaghetti Warning precision (v1.2)** | — | > 60%（避免把「自然 hub」誤判為黑洞）|
| **Two-Pass funnel preservation rate (v1.2)** | — | TF-IDF Pass 1 保留「最終 user accept」的 pair ≥ 80%（若 < 60% 表示 Pass 1 演算法有問題）|

**觸發 v2 審視的條件：**
- Accept rate < 20% 連續 3 次 → relation detection 邏輯需修正
- User 報「常用但 11 種 edge type 不夠」 → taxonomy 升級討論
- 10+ real runs 後，某些 ADR 的假設被推翻

---

## 13. 與其他 specs 的邊界

### 13.1 vs Heptabrain Sync

| | Heptabrain Sync | Propose Links |
|--|----------------|---------------|
| 方向 | memory ↔ HB | HB 內部 |
| 產出 | 新卡片（push）/ refs（pull）| 建議文件（不建卡）|
| 讀 registry | `_heptabrain_registry.json`（讀寫） | 讀取為 context，不寫入 |
| 觸發 | 知識結晶化 | whiteboard 盤整 |

### 13.2 vs Zettel Walk

| | Zettel Walk | Propose Links |
|--|------------|---------------|
| 範圍 | open（跨 whiteboards）| closed（單 whiteboard） |
| 方向 | 發散（升維出去） | 收斂（盤點回來） |
| 產出 | discovered_links + Journal | propose markdown + discovered_links + Journal |
| 典型觸發 | 「想找新連結」 | 「想整理 whiteboard」 |
| 搜尋依賴 | semantic search 跨 whiteboard | 只用 get_whiteboard_with_objects |

### 13.3 vs Strategic Review + MDA

| | Strategic Review + MDA | Propose Links |
|--|----------------------|---------------|
| 單位 | 1 個 feature | 1 個 whiteboard |
| 維度 | 4D（Synergy / Proximity / Temporal / Perspective） | inter-card relations（11 種 edges） |
| 產出 | 單 feature 分析 doc | whiteboard 組織提議 |
| 交集 | feature-family whiteboard 可以 propose-links 跑 MDA sketch | — |

### 13.4 不取代任何既有 skill

Propose-links 填入既有 stack 的空缺（closed-set organize），不重疊、不替換。

---

## 14. Sign-off Checklist

- [ ] Problem statement 清楚（§1）
- [ ] Closed-set discipline + 11 edge types 重用說明合理（§2）
- [ ] MDA integration 是 optional 不是必選（§2.4 + ADR PL8）
- [ ] Skill interface 的 flags 不過多（§3）
- [ ] Output format 三層（markdown doc + JSON registry + optional Journal）符合 Cyberbrain P3（§4）
- [ ] Registry integration 不破壞現有 registry schema（§5，僅新增 nullable 欄位）
- [ ] 與 Zettel Walk / Heptabrain Sync / MDA 的邊界明確（§13）
- [ ] Implementation 可在 3hr 完成（§7）
- [ ] 12 個 ADR 同意（§11）
- [ ] Edge cases 可操作（§9）

---

## 15. 命名與位置

- **Spec 檔名：** `memory/DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md`
- **Skill 檔名：** `~/.claude/commands/heptabrain-propose-links.md`
- **簡稱：** Propose Links
- **不會有 v2 除非：** 5+ real runs 後發現結構性問題或 §12 觸發條件出現

---

*DRAFT — 待簽收 + multi-AI review before implementation.*
