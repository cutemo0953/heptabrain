# Dev Spec: Zettel Walk (升維漫遊 — 跨域連結發現)

**Version:** v2.2 DRAFT
**Date:** 2026-04-24
**Author:** Architect (Claude Code)
**Parent Spec:** `DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md` **v3.0** (2026-04-24)
**Cyberbrain Role:** Loop 3 — **Diverge**（cross-whiteboard divergent discovery）
**Status:** DRAFT — 待簽收 (v2.1 shipped behavior 保留，v2.2 新增 v3 alignment + zero-friction journaling)

**Changelog:**
- v1.0: Flat vector search, prose-only output
- v2.0: 升維搜尋、link evidence、cycle guard
- v2.1 FINAL: Elevation anchors、bridge dialectic (tensions_with)、internal dual scoring、discovered_links.json 持久化
- **v2.2 (2026-04-24):** Aligned to Cyberbrain v3.0:
  - Header 新增 Four-Loop Role 標示（Diverge）
  - §4 修訂：wander/shuffle 輸出 `link_class: exploratory`；bridge accepted 為 `proposed`
  - §5 Registry entries 寫入時對齊 v3 Schema v2 provenance fields
  - §4.Output **Zero-friction Journal append**（採納 Gemini tactic，對齊 v3 P5：Journal 是 ephemeral surface，寫入不需 human gate）
  - `--explicit-confirm` 旗標保留給 user 想 opt-in 舊行為
  - 新 link 若 novelty_score > 0.8 → `link_class: exploratory`；若 ≤ 0.8 → `proposed`（更穩定的連結）

---

## 1. Problem

「電馭大腦」的核心哲學：知識的價值在於連結，不在於節點。

v2.0 已解決 flat vector search 的同域偏見問題。v2.1 補齊三個治理層面：
- 升維方向需要穩定性（elevation anchors）
- 橋接不只找共通性，也要找張力（dialectic）
- 發現的連結需要持久化（discovered_links.json）

## 2. Core Mechanism: 升維搜尋 + Elevation Anchors

```
卡片 A → AI 抽象化 → 底層原則 P
                       ↓
          映射到 Elevation Anchor（優先）
                       ↓
          用 P 搜尋 Heptabase → 跨域碰撞
```

**Elevation Anchors（升維錨點）：**

```
1. System Resilience（系統韌性）
2. Economic Incentives & Boundary Conditions（經濟誘因與邊界條件）
3. Clinical Feedback Loops（臨床回饋迴圈）
4. Scaling & Governance（規模化與治理）
5. Human-AI Collaboration（人機協作）
```

升維時 AI 的 prompt 指令：「將這張卡片的核心概念抽象化為底層原則。優先映射到以下五個維度之一，但如果不適合任何維度，可以自由抽象。」

這不是 ontology — 不限制分類，只提供方向。如同高速公路網：你可以走省道，但高速公路讓跨域碰撞更有效率。

**Anchors 可隨時修改。** 當使用者的關注點改變（例如新增「法規遵循」），直接更新 skill 檔案中的 anchors list。

## 3. Four Modes

### Mode 1: Wander（升維漫遊）

```
/zettel-walk wander "observation-feedback closed-loop"
```

**Flow:**

```
Step 1: Semantic search 找到起始卡片，讀取全文
Step 2: 提取核心概念 + 升維抽象化
        → 映射到 elevation anchor（若適用）
        → 例：E-P-E-R → Anchor 3 "Clinical Feedback Loops"
             → 底層原則："uncertainty reduction through observation loops"
Step 3: 用底層原則做 semantic search
        → 排除 visited_set
        → 排除同 whiteboard
        → 內部計算 dual score:
            novelty_score = 與起始卡片的領域距離
            evidence_score = 與底層原則的語義相關度
        → 選 novelty * 0.6 + evidence * 0.4 最高者
Step 4: 讀取新卡片 → 再次升維 → 再搜尋
Step 5: 重複 3-5 步
Step 6: 回顧路徑 → 輸出 structured result
        → 發現的 links 寫入 discovered_links.json
```

**Cycle Guard:**
- `visited_ids: Set<string>` — 每步排除
- 連續 2 步全在 visited → 結束漫遊
- 最多 5 步硬上限

### Mode 2: Shuffle（隨機抽牌）

```
/zettel-walk shuffle 3 "value-based bundled payment"
```

**Flow:**

```
Step 1: 用 3 個不同 elevation anchor 維度搜尋
        （如 anchor 1 "resilience", anchor 2 "economics", anchor 3 "feedback"）
Step 2: 從每個維度的結果中各隨機選 1 張（共 3 張）
        排除 PDF、空卡片、<100 字的卡片
Step 3: 加入使用者指定的 1 張錨點卡片
Step 4: 讀取所有 4 張完整內容
Step 5: 每張升維 → 找原則重疊和原則衝突
Step 6: 輸出 + user 確認 → discovered_links.json
```

### Mode 3: Bridge（辯證橋接）— v2.1 升級

```
/zettel-walk bridge "Orchestration Platform" "Safety-II"
```

**Flow:**

```
Step 1: 讀取兩張目標卡片
Step 2: 分別升維 → 底層原則 P_A 和 P_B
Step 3: 三層搜尋：
  a. 共通橋：P_A 和 P_B 有交集嗎？
  b. 一跳橋：有第三張卡片 C 同時和 P_A + P_B 相關？
  c. 升維橋：P_A 和 P_B 能再往上抽象到共同原則 P_meta？
Step 4: 辯證維度（v2.1 新增）：
  → AI 強制回答：「這兩個底層原則在哪種邊界條件下會互相衝突？」
  → 輸出 tensions_with relation
Step 5: 輸出：
  - 共通路徑 + 張力路徑
  - 橋接洞見
  - 辯證問題（例：「如何在承平時期維持精實，卻保有災難時的冗餘彈性？」）
```

**範例輸出：**

```
Bridge: Platform-A ↔ Platform-B

Shared Principle:
  Both are orchestration platforms (不擁有終端，提供平台)

Tension:
  Platform-A optimizes for redundancy under scarcity (disaster)
  Platform-B optimizes for lean efficiency under abundance (peace)
  → Conflict boundary: "at what resource level does lean become fragile?"

Dialectic Insight:
  一個好的醫療系統需要同時具備精實的日常運作和冗餘的危機彈性。
  某個固定 N-day episode 是否可以作為「模式切換」的觸發機制？
```

### Mode 4: Journal（日誌回顧）

```
/zettel-walk journal
```

讀取 Heptabase Journal 最近 7 天，找出：
- 重複出現的主題
- 與既有卡片可連結的洞見
- 值得升格的段落（`authority_status: candidate` → 提議 `canonical`）

## 4. Output Format

```markdown
## Zettel Walk — {mode} | {date}

### Path
1. **[起始卡片]**
   - Raw concept: "E-P-E-R closed-loop rehab"
   - Elevation anchor: Clinical Feedback Loops
   - Abstracted: "Uncertainty reduction through observation loops"

2. **[第二張卡片]**
   - Raw concept: "Safety-II learning from success"
   - Elevation anchor: System Resilience
   - Abstracted: "System improvement through observation, not blame"

### Hidden Pattern
{1-2 段敘述}

### Link Evidence
| From | To | Type | Rationale | Evidence | Novelty | Evidence Score |
|------|----|------|-----------|----------|---------|---------------|
| E-P-E-R | Safety-II | shares_principle | Both loop-based | E-P-E-R §cycle; S-II §WAD | 0.8 | 0.7 |
| Platform-A | Platform-B | tensions_with | Redundancy vs lean | Platform-A §disaster; Platform-B §shrink | 0.9 | 0.6 |

### Bottom-Line Logic
{一句話}

### Suggested Actions
- [ ] 建立橋接卡片："{title}"
- [ ] Blog angle: "{title}"
```

**Output Destination（v2.2 修訂：Zero-friction journaling）：**

所有 zettel-walk 結果**預設自動 append 到當天 Heptabase Journal**，**跳過** v2.1 的 y/n 確認（對齊 Cyberbrain v3 P5：Journal 是 ephemeral surface，寫入不需 human gate；user 瀏覽 Journal 時即是 review 過程）。

**v2.2 User flow（預設）：**
1. CLI 顯示漫遊結果（path + pattern + link evidence）
2. **自動** `append_to_journal` 寫入今天 journal + links 寫入 discovered_links.json
3. User 稍後在 Heptabase 瀏覽 Journal，覺得好的 → 右鍵「Turn into card」→ 自動在 whiteboard 上
4. User 覺得不好的 Journal 段落 → 刪除該段（Journal 是草稿區；不像主空間卡那麼 canonical）
5. 下次 `/heptabrain-sync audit` 可偵測哪些 journal 發現已被升格為卡片

**v2.2 opt-out：** `--explicit-confirm` 旗標恢復 v2.1 行為（y/n 確認），給想 old school 的 user 用。

**為什麼從 v2.1 的 prompt 模式改成 v2.2 的 auto 模式：**
- v2.1 的 y/n 是 UX friction；大多數 user 預設 y，問了只是多一步
- Journal 本質 = ephemeral surface；user 在 Journal 看到「不好的」想法是正常過程
- 對齊 Cyberbrain v3 P5「**寫 Journal 不需 human gate**」原則
- Gemini 2026-04-24 review 明確建議：CLI 開放後應讓 journal append 變 zero-friction

**並非**所有 write 都 auto：
- 在 whiteboard 主空間 create 卡仍手動（Cyberbrain P5）
- Edit 既有 canonical 卡仍需 human gate
- 只有 Journal append 是 zero-friction

## 5. Discovered Links Registry

每次 zettel-walk 結束時，所有發現的 links 寫入 `_discovered_links.json`（對齊 Cyberbrain v3 Registry Schema v2）：

```json
[
  {
    "link_id": "lk-001",
    "from_knowledge_id": "kb-eper-loop",
    "to_knowledge_id": "kb-safety-ii",
    "relation_type": "shares_principle",
    "rationale": "Both optimize through observation-feedback loops",
    "evidence_refs": ["E-P-E-R card §cycle", "Safety-II KB page 3"],
    "novelty_score": 0.8,
    "evidence_score": 0.7,

    "// v3 Schema v2 provenance fields": "",
    "link_class": "exploratory",
    "acceptance_state": "proposed",
    "scope_type": "cross_whiteboard",
    "scope_whiteboard_id": null,
    "source_mode": "zettel-walk:wander",
    "evidence_kind": ["text_overlap", "shared_actor"],
    "last_verified_at": "2026-04-06T15:00:00+08:00",
    "verified_by": "ai",

    "// legacy compat": "",
    "review_state": "proposed",
    "discovered_at": "2026-04-06T15:00:00+08:00",
    "discovered_by": "zettel-walk wander"
  }
]
```

**v2.2 link_class 決策規則（對齊 Cyberbrain v3 §5.1 三分法）：**

| Walk mode | Novelty score | 預設 link_class |
|-----------|--------------|----------------|
| wander | > 0.8（高 novelty）| `exploratory`（假設型，可能被淘汰）|
| wander | ≤ 0.8 | `proposed`（較穩定）|
| shuffle | 任何 | `exploratory`（本質隨機 + 發散）|
| bridge | `shares_principle` 的 | `proposed`（辯證共通性較穩）|
| bridge | `tensions_with` 的 | `exploratory`（張力假設）|
| journal | 任何 | `proposed`（回顧型更穩）|

**用途：**
- 防止重複發現（下次 walk 前先查 registry）
- 追蹤哪些 links 被接受/拒絕 / 升 canonical / 變 stale
- Audit 時找孤兒 links 或 exploratory 久未升為 proposed/canonical 的（可能是無效連結）

## 6. Skill Interface

```
/zettel-walk wander "{concept}"         — 升維漫遊
/zettel-walk shuffle N "{anchor}"       — 隨機抽 N 張 + 1 張錨點
/zettel-walk bridge "{A}" "{B}"         — 辯證橋接（共通性 + 張力）
/zettel-walk journal                    — 7 天日誌回顧
```

## 7. Implementation Plan

| Step | 內容 | 預估 |
|------|------|------|
| 1 | 建立 `~/.claude/commands/zettel-walk.md` skill | 30 min |
| 2 | 實作升維引擎 + elevation anchors prompt | 30 min |
| 3 | 實作 wander mode + dual scoring + cycle guard | 25 min |
| 4 | 實作 shuffle mode + anchor-based random selection | 20 min |
| 5 | 實作 bridge mode + dialectic dimension | 25 min |
| 6 | 實作 journal mode | 15 min |
| 7 | 實作 discovered_links.json persistence | 15 min |
| 8 | 實作 output format + link evidence table | 10 min |
| 9 | 測試：wander from "電馭大腦" | 10 min |

**Total:** ~3 hours

## 8. Design Decisions

### Dual Scoring（內部計算，不暴露 UI）

| Score | 目的 | 權重 |
|-------|------|------|
| `novelty_score` | 與起始卡片的領域距離（越遠越好） | 0.6 |
| `evidence_score` | 與底層原則的語義相關度（越高越好） | 0.4 |

權重偏向 novelty 因為 zettel-walk 的核心價值是跨域碰撞。如果需要 evidence-heavy 搜尋，直接用 Heptabase semantic search 即可。

### 為什麼 Bridge 需要 Dialectic？

只找共通性的橋接會得到「兩者都在優化資源配置」這種表面結論。加入張力維度（tensions_with）才能產出真正有批判深度的洞見，例如「redundancy vs lean 的邊界條件」。

### 為什麼 user 確認才建卡片？

人類的領悟 > AI 的整理。AI 發現連結，人決定保留。

## 9. Edge Cases

| Case | 處理 |
|------|------|
| 升維太泛（"systems thinking"） | AI 自檢：若 >3 字且過於通用 → 降一級 |
| 所有結果都在 visited set | 結束漫遊，報告「已窮盡可達路徑」 |
| Shuffle 無法從某 anchor 維度抽到卡片 | 換另一個 anchor 重試 |
| Bridge 找不到路徑 | 報告 + 建議更高層抽象 |
| discovered_links.json 已有相同 from+to | 更新而非新增（可能 relation_type 不同 → 新增） |
| Journal 過去 7 天為空 | 報告無內容 |

## 10. Out of Scope (v2.1)

- 自動排程漫遊
- Obsidian 聯合漫遊
- 視覺化路徑
- exploration / analysis 雙 UI 模式（內部用 dual score 即可）
- graph database
- 漫遊歷史長期統計

---

*Approved for implementation.*
