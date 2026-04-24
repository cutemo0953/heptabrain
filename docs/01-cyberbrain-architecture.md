# Dev Spec: Cyberbrain Architecture (電馭大腦基礎設施)

**Version:** v3.0.1 DRAFT (sign-off revisions 2026-04-24 evening)
**Date:** 2026-04-24
**Author:** Architect (Claude Code)
**Status:** DRAFT — 待簽收 before cascading to child spec updates
**Previous Approved:** v2.1 FINAL (2026-04-06)
**Review:** v3.0 triggered by 2026-04-22 Heptabase CLI 公開 + 兩 AI review（ChatGPT + Gemini）收斂共識

**Changelog:**
- v1.0: Initial draft
- v2.0: State/Knowledge 解耦、per-type authority、升維搜尋、link evidence
- v2.1: GC 機制、discovered_links registry、elevation anchors、bridge dialectic、canonicality metadata-first
- **v3.0.1 (2026-04-24 evening):** Sign-off round revisions — Gemini + ChatGPT convergence on 5 Critical items + 3 P2s:
  - §5.2 Lifecycle: 新增 **Link Class × Lifecycle Transition Matrix**（ChatGPT Critical 1）+ **Class Promotion Rule** on accept（Gemini Major 3）
  - §6 Whiteboard Maturity: 從純 title convention 改為 **local registry + title-as-fallback**（兩 AI 同步 Critical 3 / P2 #6）
  - §7 Feature Family: 拆為 **MVFF vs Canonical 兩層**（兩 AI 同步 Critical 4 / P1 #5）
  - §3.3 Registry Migration: 新增 **Audit-Triggered Lazy Write-back**（兩 AI 同步 Critical 5 / P1 #4）
  - §3.2 Registry Schema v2 擴充 Auto-accept 相關欄位
- **v3.0 (2026-04-24):** Major revision triggered by Heptabase CLI release. Upgrade from "collection of tools" to "knowledge operating system":
  - §4 Four-Loop Operating Model（取代 Five Improvement Areas）
  - §5 Three Link Classes + 5-state Lifecycle
  - §6 Registry Schema v2（6 new provenance fields，向後相容）
  - §7 Whiteboard Maturity Classes（seed / forming / structured / canonical）
  - §8 Feature Family Whiteboard Class（first-class 結構定義）
  - §9 Three-plane Architecture（CLI = control / MCP = data / GUI = confirmation）
  - §2 新增 P6 Three-Plane Separation 設計原則
  - §10/§11 Technical Constraints + Success Metrics 更新（反映 CLI release 的系統升級）

---

## §1 Problem Statement

### 1.1 原始問題（v1.0–v2.1 已解決）

v1.0–v2.1 已把五個孤島系統連成一個有連結機制的知識體：

```
Heptabase  ←[sync]→  Claude Memory
     ↑                     ↓
  Journal               Wiki KBs
                            ↓
                         Blog
```

五個系統透過 `/heptabrain-sync`、`/zettel-walk`、discovered_links.json、Journal 中繼站開始串起。

### 1.2 v2.1 的剩餘缺口（2026-04-24 揭露）

2026-04-22 Heptabase 公開 CLI + AI Agent roadmap（edit card / whiteboard content 進行中），兩 AI review（ChatGPT + Gemini）收斂共識點出：

**現況是 5 個工具並列，還不是一個 operating system：**

1. 缺少**四迴圈 operating model** — capture → converge → diverge → abstract 的閉環沒正式化
2. 缺少**intra-whiteboard convergent organization** 這塊（discovery + transfer + review 都有，就沒「整理」）
3. 缺少**link lifecycle** — proposed / accepted / rejected / superseded / stale 無正式狀態機，全積在 registry 裡
4. 缺少**三種 link class 區分** — canonical / proposed / exploratory 混用會讓 graph epistemically muddy
5. 缺少**whiteboard maturity signal** — 不知哪個 whiteboard 該跑 propose-links、哪個該 freeze
6. 缺少**Feature Family Whiteboard 正式 class** — MDA + Strategic Review 的 graph 容器沒標準結構
7. **CLI / MCP / GUI 三層架構未明示** — v2.1 沒指出三層各司其職

### 1.3 為什麼是現在升級

CLI 公開 + AI Agent roadmap 不是「多一條通路」，是**系統運作面正式開通**：
- v2.1 時代 Heptabase 是 storage layer（pull canonical）
- v3.0 時代 Heptabase 是 operations layer（cards / links / gaps / clusters 都在這裡被 propose / audit / evolve）
- 若不在 proposal volume 爆炸前升級 registry / lifecycle，未來會 graph-muddy

---

## §2 Design Principles

### P1: 解耦「狀態」與「知識」(State vs Knowledge) — 不變

- **State：** 天/週級別過期。例：bug lists、session logs、待辦。
- **Knowledge：** 經結晶化的洞見，不隨時間貶值。例：策略決策、架構原則、研究發現。

只有 Knowledge 才能進入 Heptabase。State 留在 Memory。

**Canonicality 判定：metadata-first, heuristic-fallback**（v2.1 規則保留）。

### P2: 各系統有各自的 Canonical Authority — 不變

| Entity Type | Canonical Source | Authority Status |
|-------------|-----------------|-----------------|
| Task context / WIP state | **Claude Memory** | ephemeral |
| Curated concept notes | **Heptabase** | canonical |
| Structured research evidence | **Wiki KBs** | canonical |
| Public synthesis | **Blog** | derived |
| Reflective raw material | **Heptabase Journal** | candidate |
| Operational feedback/prefs | **Claude Memory** | reference |

### P3: 連結必須帶 Evidence（可追溯性）— v3.0 擴充

每條 AI 建議的連結至少包含：
- `relation_type`：controlled vocabulary（11 種，見 §5.3）
- `rationale`：為什麼相關（一句話）
- `evidence`：來源參照
- **`acceptance_state`**：proposed → accepted / rejected / superseded / stale（v3.0 新增 5-state lifecycle，見 §5.4）
- **`source_mode`**: sync / walk / propose_links / strategic_review / manual（v3.0 新增 provenance）
- **`evidence_kind`**: text_overlap / shared_actor / temporal / mda_synergy（v3.0 新增 evidence 分類）

### P4: 升維時有錨點 (Elevation Anchors) — 不變

```
1. 系統韌性 (System Resilience)
2. 經濟誘因與邊界條件 (Economic Incentives & Boundary Conditions)
3. 臨床回饋迴圈 (Clinical Feedback Loops)
4. 規模化與治理 (Scaling & Governance)
5. 人機協作 (Human-AI Collaboration)
```

Anchors 可隨時修改（不是 ontology，是 prompt 方向性引導）。

### P5: Journal 中繼，不直接建卡片 — v3.0 精煉

**核心規則：空間佈局保留給 human cognition。** v2.1 的 Journal 中繼設計 + v3.0 新增的 **AI write 邊界規則**：

| Action 類型 | 是否需 human gate | 理由 |
|------------|-----------------|------|
| 寫 **Journal**（ephemeral surface）| ❌ 不需（zero-friction）| Journal 本質是草稿；user 瀏覽時就是 review |
| 在 whiteboard **create 明確標記的建議卡**（例：`🗂️` 前綴）| ❌ 不需 | 加卡不改既有語義 |
| **edit 既有 canonical 卡片** | ✅ 需要 | 難回復；影響既有信任 |
| **拉線 / 分群 / 空間定位** | ✅ 需要 | 空間語義是 human cognition 核心 |
| **Tag 操作**（CLI 新通路）| ⚠️ 視 target 卡片而定 | Canonical 卡 tag 改動需 gate；candidate 卡不需 |

這個「ephemeral-vs-canonical write boundary」是 Cyberbrain v3.0 的核心 discipline。

### P6: Three-Plane Separation — v3.0 新增

CLI release 後，各 client 有各自該做的事，不該 overlap：

| Plane | 介面 | 職責 | 典型 use case |
|-------|------|------|--------------|
| **Control** | CLI (`heptabase ...`) | Trigger surface、auth bootstrap、automation entry、cron jobs | 每日 `heptabase get-journal-range` + append 摘要回 Memory |
| **Data** | MCP (`mcp__heptabase-mcp__*`) + API | Bulk object access、parallel read、in-session analysis | Propose Links 讀 N 張 card 並行分析 |
| **Confirmation** | GUI (Heptabase app) | Spatial disposition、semantic meaning、final accept/reject | 拉線、移位、圈 section |

**不混用：**
- ❌ 用 CLI 跑 20 張 card 逐張讀（慢 40×，應該用 MCP）
- ❌ 用 MCP 做 cron job（MCP 需 Claude Code 主 session，應該用 CLI）
- ❌ 用 AI 做 spatial layout（即使未來 API 開放；哲學決策，見 P5）

完整架構見 §9。

---

## §3 System Registries

### 3.1 Sync Registry (`_heptabrain_registry.json`) — v2.1 不變

追蹤 knowledge objects 的同步狀態。

```json
{
  "knowledge_id": "kb-irehab-scaling",
  "source_system": "memory",
  "source_file": "project_irehab_scaling_strategy.md",
  "canonicality": "knowledge",
  "authority_status": "canonical",
  "content_hash": "sha256:abc123...",
  "supersedes": null,
  "superseded_by": null,
  "aliases": ["<primary alias>", "<secondary alias>"],
  "heptabase_card_title": "...",
  "synced_at": "2026-04-06T14:30:00+08:00"
}
```

### 3.2 Link Registry (`_discovered_links.json`) — v3.0 Schema v2

**v2.1 Schema（legacy，仍 parse）:**
```json
{
  "link_id", "from_knowledge_id", "to_knowledge_id",
  "relation_type", "rationale", "evidence_refs",
  "novelty_score", "evidence_score", "review_state",
  "discovered_at", "discovered_by"
}
```

**v3.0 Schema v2（完整，向後相容）:**

```json
{
  "link_id": "lk-001",
  "from_knowledge_id": "kb-eper-loop",
  "to_knowledge_id": "kb-safety-ii",
  "relation_type": "shares_principle",
  "rationale": "Both optimize through observation-feedback loops",
  "evidence_refs": ["Heptabase card: E-P-E-R §2", "Safety-II KB: page 3"],
  "novelty_score": 0.8,
  "evidence_score": 0.7,

  "// v3.0 provenance fields (all optional, nullable)": "",
  "link_class": "proposed",
  "acceptance_state": "proposed",
  "scope_type": "cross_whiteboard",
  "scope_whiteboard_id": null,
  "source_mode": "zettel-walk:wander",
  "evidence_kind": ["text_overlap", "shared_actor"],
  "last_verified_at": "2026-04-24T11:00:00+08:00",
  "verified_by": "ai",

  "// v3.0.1 Auto-accept fields (Propose Links §5.1.1 + §5.2.2 references)": "",
  "implicit_connection_detected": null,
  "auto_accept_reason": null,
  "auto_accept_confidence": null,
  "promoted_from": null,

  "// legacy v2.1 preserved": "",
  "review_state": "proposed",  // deprecated, mirror of acceptance_state
  "discovered_at": "2026-04-06T15:00:00+08:00",
  "discovered_by": "zettel-walk wander"
}
```

### 3.3 Migration Rules（legacy entries → v2）

對既有 entries 讀取時套用 fallback：

| v2 Field | 若缺失，fallback |
|----------|--------------|
| `link_class` | 查 `discovered_by`：manual → canonical；其他 → proposed |
| `acceptance_state` | 查 `review_state`（v2.1 欄位）：提升為 v2 lifecycle |
| `scope_type` | 若 `discovered_by` 含 "propose-links" → `whiteboard`；其他 → `cross_whiteboard` |
| `scope_whiteboard_id` | null（legacy） |
| `source_mode` | 從 `discovered_by` 推斷（"zettel-walk wander" → "zettel-walk:wander")|
| `evidence_kind` | 若 `evidence_refs` 含 "KB" → `["text_overlap"]`；其他 → `[]` |
| `last_verified_at` | `discovered_at` |
| `verified_by` | "ai"（AI-discovered 預設）|

**Write 時：** 新 entries 必須填 v2 欄位。Legacy entries 讀時動態補 fallback，正常讀寫不寫回（避免破壞 audit trail）。

**Audit-Triggered Lazy Write-back（v3.0.1 新增，兩 AI Critical 5 / P1 #4）：**

純 fallback 長期會讓 JSON 混雜 legacy + v2 格式，下游工具（jq / scripts）解析困難。`/heptabrain-sync audit registry-v2` 提供治理路徑：

```
1. 讀整份 _discovered_links.json
2. 對每 entry：
   a. 套 fallback 補齊 v2 欄位（in-memory）
   b. 比對原始 entry — 若缺任何 v2 欄位 → 標為 "needs normalization"
3. 產 migration_report.md：
   - 共 N 條 legacy entries
   - 分布：多少靠 discovered_by heuristic / 多少靠 review_state 推斷 / 多少無法可靠推斷
   - fallback ambiguity 案例（例：discovered_by="manual" 但 review_state 未定）
4. User 確認後，執行 `--commit` 子指令：
   - 備份原檔 `_discovered_links.json.v2.1-backup-<timestamp>.json`
   - 把 normalized entries 寫回主檔
5. 不靜默 mutate：整個操作留 audit log，備份文件可回溯
```

**執行頻率：** 每 30 天至少跑一次，或 `_discovered_links.json` 累積 > 100 entries 時。純讀場景無影響；只有 audit 顯式執行時才 write-back。

### 3.4 Heptabase Reference (`_heptabase_refs.json`) — v2.1 不變

Session-scoped，每次 pull 覆寫。

### 3.5 Whiteboard Maturity Registry (`_whiteboard_maturity.json`) — v3.0.1 新增

Canonical source for whiteboard maturity states, paired with `§6.1` dual-fallback 機制。

```json
{
  "version": "1.0",
  "whiteboards": [
    {
      "whiteboard_id": "5540d525-008d-...",
      "maturity": "forming",
      "maturity_source": "manual|heuristic|meta_card|title",
      "last_maturity_reviewed_at": "2026-04-24T11:00:00+08:00",
      "note": "optional free-form"
    }
  ]
}
```

**讀寫模式：**
- **Read：** 所有 skills 在檢查 maturity 前先讀此 registry；若 `whiteboard_id` 不存在 → 走 §6.1 fallback precedence（meta_card → title → density heuristic）
- **Write 時機：** (1) heuristic 偵測完成後寫回（source=heuristic）；(2) user 手動設定（source=manual）；(3) skill 讀到 `⚙️ Meta` card 時 sync 到 registry（source=meta_card）
- **Audit：** `last_maturity_reviewed_at` 超過 90 天未更新 → `/heptabrain-sync audit` 建議重跑 density heuristic

---

## §4 Four-Loop Operating Model

v2.1 的 `Five Improvement Areas` 是「五個好用工具」的 additive 列表。v3.0 重新組織為**四個迴圈**，每個 skill 對應一個 loop：

### 4.1 Loop 1 — Crystallize（結晶化）

**方向：** Memory / Spec / Review → Heptabase cards
**Skill：** `/heptabrain-sync push`
**Input：** 要變 canonical 的 knowledge（from Memory / Reviews）
**Output：** 結晶化 card（distilled, not copied）
**Frequency：** 週/月級別

### 4.2 Loop 2 — Converge（收斂組織）

**方向：** Whiteboard 內 cards → proposed links + groupings
**Skill：** `/heptabrain-propose-links`（v3.0 新增的迴圈；child spec `DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md`）
**Input：** 單一 whiteboard
**Output：** 建議 links + groupings + gap signal + bridge debt
**Frequency：** whiteboard maturity 到 `forming` 階段起，每 2-4 週

### 4.3 Loop 3 — Diverge（跨域發散）

**方向：** Cross-whiteboard exploration → bridge links
**Skill：** `/zettel-walk wander/shuffle/bridge/journal`
**Input：** 起始 concept / card / date range
**Output：** cross-domain link evidence + Journal entry
**Frequency：** 週級別 / 靈感觸發

### 4.4 Loop 4 — Abstract（抽象化）

**方向：** 1 feature → principle cards + typed edges + 4D analysis
**Skill：** `/strategic-review` + MDA extension
**Input：** 1 個 shipped feature
**Output：** Case card + Principle card + Design Rules + Transfer Rule + 4D MDA（選配）
**Frequency：** 每個 SLS ≥ 3 的 feature ship 後

### 4.5 迴圈互動

```
┌────────────────┐
│   Crystallize  │←──────────────────────┐
│  (Sync push)   │                       │
└────────┬───────┘                       │
         │                               │
         ↓ cards                    abstract
         ↓                         principles
    ┌────────────────┐             ┌────────────────┐
    │    Converge    │             │    Abstract    │
    │ (Propose Links)│────edges───→│ (Strategic Rev)│
    └────────┬───────┘             └────────────────┘
             │                             ↑
             ↓ clusters                    │
             ↓                         principles
    ┌────────────────┐                     │
    │    Diverge     │──── bridge links ───┘
    │  (Zettel Walk) │
    └────────────────┘

Registry + Acceptance Workflow = 四迴圈的 governance layer
```

每迴圈都讀寫 `_discovered_links.json`（share registry），讓 cross-loop insight 不 silo。

---

## §5 Link Classes + Lifecycle

### 5.1 Three Link Classes

| Class | 定義 | 典型來源 | Graph 中的角色 |
|-------|------|---------|--------------|
| **Canonical** | 穩定、accepted、語意明確 | Manual / long-lived accepted | 長期 graph skeleton |
| **Proposed** | AI 提議、尚未 accept | propose-links / strategic-review | 候選 skeleton（經 accept 後升 canonical）|
| **Exploratory** | 假設型、低信心、可能被淘汰 | zettel-walk 高 novelty 產出 | 短期探索軌跡 |

**為什麼要分：** 混用會讓 graph **epistemically muddy** — reader 看一條 link 無法分辨是「共識真理」還是「某次漫遊靈光」。

### 5.2 Acceptance Lifecycle (5 states)

```
       proposed
      /        \
accepted     rejected
    ↓
 superseded（by newer better link）
    ↓
   stale（last_verified_at too old → audit re-verify）
```

| State | 意義 | 進入條件 |
|-------|------|---------|
| `proposed` | AI 剛發現 | 預設值於所有 AI-generated links |
| `accepted` | User 確認保留 | User 在 registry 改 state，或在 HB GUI 拉線確認 |
| `rejected` | User 確認否決 | User 明確否定；不再 re-propose 同 pair |
| `superseded` | 被更好的 link 取代 | 新 proposed link 覆蓋同 pair，原 link 降級 |
| `stale` | 久未驗證可能過時 | `last_verified_at` > 180 天 + audit 觸發時標記 |

### 5.2.1 Link Class × Lifecycle Transition Matrix（v3.0.1 新增，ChatGPT Critical 1）

**允許的組合：**

| link_class | allowed acceptance_state |
|-----------|-------------------------|
| `canonical` | `accepted`, `stale`, `superseded` |
| `proposed` | `proposed`, `accepted`, `rejected`, `superseded`, `stale` |
| `exploratory` | `proposed`, `rejected`, `superseded`, `stale` |

**規則：**
- `canonical` 不應處於 `proposed` 或 `rejected` 狀態（canonical 意味著已經被驗證）
- `exploratory` 不直接 accept — 先升為 `proposed`，再進 accepted；**但 class promotion rule（§5.2.2）允許一步完成**
- Registry 層讀寫時，不符此矩陣的組合 → audit 標 `invalid_combination: true` 進待修 queue

### 5.2.2 Class Promotion Rule on Accept（v3.0.1 新增，Gemini Major 3）

當 link 轉入 `accepted` 時，link_class 自動升級：

| 原 class | 原 state | → accept action 後 class | → accept action 後 state |
|---------|---------|------------------------|----------------------|
| `canonical` | any | `canonical`（不變）| `accepted` |
| `proposed` | `proposed` | `canonical`（升）| `accepted` |
| `exploratory` | `proposed` | `canonical`（升）| `accepted` |

**Audit trail 保留：** accept 時若發生 class 晉升，必寫 `promoted_from: "<原 class>"` 欄位（registry schema v2 已含，見 §3.2）。讓未來 audit 能追蹤「某個 canonical link 原本是哪種 class」。

**設計意圖：** 人類在 GUI 拉線確認某條 exploratory 假設時，它已經從「AI 推測的 novel 連結」變成「被驗證的 canonical 知識」。一步完成符合直覺，保留 `promoted_from` 給學術追溯用。

**下游 skill 實作：** Propose Links `/heptabrain-propose-links` 的 Auto-accept detection（`DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md` §5.1.1）是此 promotion rule 的第一個自動化實作 — 偵測到 whiteboard 實體 connection 匹配時套用此規則。未來其他 skill（如 strategic-review、heptabrain-sync audit）也應共用此規則，不可自建 promotion 邏輯。

### 5.3 Controlled Edge Vocabulary（11 types — 不變）

**Zettel-Walk 定義的 7 種：** `supports` / `contradicts` / `derives_from` / `applies_to` / `example_of` / `bridge_to` / `tensions_with`

**MDA 新增的 3 種：** `synergizes-with` / `attracts` / `precedes`

**Zettel-Walk output 慣用 1 種：** `shares_principle`

新 relation type 須走正式升級流程（見 P3），不可 ad-hoc 擴充。若 AI 想用的 type 不在清單 → fallback `related_to` + `needs_taxonomy_review: true`，進 audit queue。

### 5.4 Acceptance Workflow

**自動轉換（system-triggered）:**
- `proposed` → `superseded`：同 (from, to, relation_type) 有更新 entry 提交，confidence 較高
- `accepted` → `stale`：`last_verified_at` 超過 180 天未觸碰

**手動轉換（human-triggered）:**
- `proposed` → `accepted`：user 編輯 registry 或 `/heptabrain-sync audit` 提示時確認
- `proposed` → `rejected`：同上否定
- `stale` → `accepted`：重新 verify 通過
- `stale` → `rejected`：過時且不再適用

**Acceptance rate 是健康指標：** 若某 source_mode 的 accept rate < 20%（連續 3 次 audit）→ 該 skill 的 detection 邏輯需 rev。

---

## §6 Whiteboard Maturity Classes

不是每個 whiteboard 都該用同樣方式對待。v3.0 定義 4 個 maturity：

| State | 定義 | Card count 典型 | 建議操作 |
|-------|------|--------------|---------|
| `seed` | 剛建立、少量 cards、結構未明 | < 5 cards | 累積卡片；**不**跑 propose-links（資料太少）|
| `forming` | 有足夠密度可整理 | 5-15 cards | 可跑 propose-links；zettel-walk 找 bridge 進來 |
| `structured` | 已建立主題結構 | 15-40 cards | 定期 audit convergence；可 extract principle card 出去 |
| `canonical` | 穩定、高語意價值、低頻更動 | 任意 N | 主要用作 reference；少 write；freeze candidate |

### 6.1 Maturity 標記方式（v3.0.1 改為 Local Registry + Dual Fallback，兩 AI Critical 3 / P2 #6）

Whiteboard 自身沒有 metadata 欄位（Heptabase API 限制）。v3.0 原方案「純 title convention」兩 AI review 皆指出問題（title 污染、user 會改名、無 audit trail）。v3.0.1 改為**三層機制**，按優先順序：

**Source precedence（由高至低）：**

1. **Local registry `_whiteboard_maturity.json`**（canonical source）：

   ```json
   {
     "whiteboards": [
       {
         "whiteboard_id": "5540d525-008d-...",
         "maturity": "forming",
         "maturity_source": "manual|heuristic|meta_card|title",
         "last_maturity_reviewed_at": "2026-04-24T11:00:00+08:00",
         "note": "optional free-form"
       }
     ]
   }
   ```

2. **`⚙️ Meta` card inside whiteboard**（PKM-native pattern）：

   使用者在 whiteboard 內建一張 title 為 `⚙️ Meta` 或 `#meta` 的卡片，內含 YAML：
   ```yaml
   maturity: canonical
   reviewed_by: user
   reviewed_at: 2026-04-24
   note: 已驗證完整 graph，低頻更動
   ```

   Skill 掃 whiteboard 物件時偵測此 card → 讀 YAML → 寫回 local registry（`maturity_source: meta_card`）。

3. **Title convention**（human-visible fallback only）：

   ```
   🌱 My Project Alpha [maturity:forming]
   🌳 Canonical Research Corpus [maturity:canonical]
   ```

   這是視覺提示方便 user 瀏覽識別；**不是 authoritative**。若 registry 與 title 衝突，以 registry 為準。

4. **Density heuristic（自動推斷，auto-detect fallback）**：

   若 registry + meta_card + title 皆無 → skill 用 `N < 5: seed`、`5 ≤ N ≤ 15: forming`、`15 < N ≤ 40 且 edges ≥ N/3: structured`、`otherwise: structured` 推斷。推斷結果寫入 registry（`maturity_source: heuristic`）供下次直接讀。

**為什麼 Local Registry 為 canonical：**
- Audit trail：`last_maturity_reviewed_at` 可追蹤 maturity 何時更新
- User 可改 whiteboard 名稱不破 maturity 狀態（title 是 display，registry 是 state）
- 可 version controlled / backup 獨立於 Heptabase
- 未來支援 per-user / per-tenant maturity（若 Heptabase 演進多人協作）

### 6.2 Maturity-based skill activation

| Skill | 允許在哪些 maturity |
|-------|-------------------|
| `/heptabrain-propose-links` | `forming` / `structured`（seed 資料不足、canonical 結構穩不需 re-organize）|
| `/zettel-walk wander` | 任何 maturity（任何 whiteboard 都可作起點）|
| `/heptabrain-sync push` 推薦 placement | 優先推薦 `forming`（知識會落地到正在建構的 whiteboard）|

---

## §7 Feature Family Whiteboard Class

Product-development 用的特殊 whiteboard class。**正式升為 first-class。**

### 7.1 Two-Level Feature Family（v3.0.1 改為兩層，兩 AI Critical 4 / P1 #5）

兩 AI review 共識：原 v3.0 的「5 個強制元素」門檻對早期 FF whiteboard 太陡峭。MDA 素描**正是**要幫助發掘 principle / lens，卻要等齊全才觸發，邏輯悖反。v3.0.1 改為**兩層 maturity**：

#### 7.1.1 Minimum Viable Feature Family (MVFF)

足以觸發 propose-links MDA 素描 + 被歸類為 feature family：

| Element | 最低要求 |
|---------|---------|
| **1 Case Card** | 必要 — 一個具體事件或 shipped feature 快照 |
| **1 Open Question Card** 或 **1 Principle Card**（任一即可）| 必要 — 表明「這是在思考中」 |
| **1 Lens Card 或 MDA Anchor** | 必要 — 用什麼角度看 |
| **≥ 1 Proposed Edge** | 必要 — 至少一條 AI 或 human 提議的連結，證明已開始收斂思考 |

符合 MVFF → `maturity: forming`，可跑 propose-links + MDA 素描；素描輸出的 Gap Signal 會明示「尚缺 Principle Card / Open Question」等，指引 user 補齊。

#### 7.1.2 Canonical Feature Family

有完整結構，經過時間 validated：

| Element | 要求 |
|---------|------|
| **1 Case Card** | 必要 |
| **1 Principle Card** | 必要（MVFF 可沒 principle，canonical 必有）|
| **1 Open Question Card** | 必要 |
| **1 Lens Card 或 MDA Anchor** | 必要 |
| **≥ 3 Accepted Edges** | 必要（對齊 §5.2 lifecycle） |

符合 canonical → `maturity: canonical`，進入低頻更動、可當教材 / blog 素材源。

**進程：** MVFF → 累積 → Canonical。不可直接在 empty whiteboard 標 `canonical`。

### 7.2 Feature Family ≠ Concept Whiteboard

| | Feature Family | Concept Whiteboard |
|--|---------------|-------------------|
| 對象 | 1 個產品功能 / 初創倡議 | 1 個領域概念 / 研究主題 |
| 內容 | specs / reviews / ADRs / retrospectives | papers / notes / fragments |
| 用 MDA？| ✅（Synergy / Proximity / Temporal / Perspective 都有意義）| ❌（4D 對概念 whiteboard 過度）|
| Propose-Links MDA sketch trigger | ✅ 自動 prompt | ❌ 不觸發 |

### 7.3 Feature Family 的 graph-native workflow

```
1. Strategic Review + MDA 產 raw material
   ↓
2. heptabrain-sync push 把 cards 推入 Heptabase
   ↓
3. User 在 feature family whiteboard 手動放卡片
   ↓
4. /heptabrain-propose-links 建議 intra-family 結構
   ↓
5. /zettel-walk 找 cross-family bridges
   ↓
6. 累積到 canonical maturity → 可產 blog / 演講素材
```

---

## §8 Three-Plane Architecture

對應 P6，把各 plane 該做的事結構化：

### 8.1 CLI Plane — Control Surface

**用途：** Trigger、automation、out-of-session entry

**典型操作：**
- Cron job：每日 `heptabase get-journal-range` 抓昨日 journal append 回 Memory
- Scripting：`heptabase search-whiteboards | jq | ...` 組 shell pipeline
- Ad-hoc 查詢：不開 Claude Code 也能查卡
- Auth bootstrap：OAuth flow（Chrome shim + refresh_token）

**不該用 CLI 做的：**
- N × get_object 並行讀取（慢 40×）
- Session-intensive analysis（每 call 重 spawn 4s）

**配合 skill：** `/heptabase-status` 用 CLI verification

### 8.2 MCP Plane — Data Plane

**用途：** Claude Code session 內的 bulk read + analysis

**典型操作：**
- Propose-Links 讀 20 張 card 並行分析
- Zettel-walk 的 semantic search + get_object 管線
- Heptabrain-sync push 的 whiteboard discovery

**配合 skill：** 大多 heptabrain-related skills

### 8.3 GUI Plane — Confirmation Plane

**用途：** Human dispose（空間語義、最終 accept）

**典型操作：**
- 拉線（相對 AI propose）
- 移位 / 圈 section
- 把 Journal 「Turn into card」
- 對 AI 建議卡片的接受/拒絕判斷

**哲學層面：** 即使未來 AI Agent API 開放，GUI plane 仍保留 human-only 部分（Cyberbrain P5 永久規則）。

### 8.4 Cross-plane handoff 原則

```
CLI trigger ─────> MCP analysis ────> GUI confirmation
   (entry)          (bulk work)         (final call)

範例：Propose-Links
1. User 下 /heptabrain-propose-links "whiteboard X"   ← CLI trigger style
2. Skill 用 MCP 讀 N 張 card 並行分析                  ← Data plane
3. Output markdown 讓 user 在 GUI 對照手動拉線          ← Confirmation plane
```

---

## §9 Priority & Dependencies

```
Phase 1 (已完成 v1.0–v2.1):
  #1 heptabrain-sync ✅ ship
  #2 zettel-walk     ✅ ship

Phase 2 (v3.0 新增):
  #3 heptabrain-propose-links ← NEW；等 v1.1 spec 簽收後實作
  #4 registry v2 migration 邏輯實作於所有 skills

Phase 3 (後續):
  #5 bridge debt audit（cross-skill）
  #6 acceptance-rate analytics by relation_type / source_mode
  #7 whiteboard convergence history tracking

Phase 4 (累積 10+ reviews 後，延續 MDA spec §3.2):
  #8 synergy graph
  #9 proximity trajectory
  #10 temporal decay chart
```

---

## §10 Technical Constraints

### 10.1 v2.1 宣告的限制 — v3.0 CLI release 後的更新

| v2.1 限制 | 2026-04 狀態 | v3.0 因應 |
|-----------|------------|----------|
| Heptabase MCP 不支援 edit/delete | **CLI release 2026-04-22；edit API roadmap 進行中** | 短期仍用 supersede + GC；中期可用 CLI `save` 自動 tag「[ARCHIVED]」但仍需 human gate（P5）|
| Heptabase MCP 不支援 tag API | CLI 支援（`card tag`）| Skills 可程式化 tag candidate 卡；canonical 卡仍 human gate |
| Vector search 只找同域鄰居 | 不變 | 繼續升維搜尋 + Elevation Anchors |
| Memory 200 行 index 限制 | 不變 | Heptabase 內容不進 MEMORY.md |

### 10.2 v3.0 新宣告的限制

| 限制 | 影響 | 因應 |
|------|------|------|
| CLI cold-start ~4s | Bulk read 不實用 | Three-plane 分工：bulk → MCP |
| Heptabase API 無 coordinate / connection / section 寫入 | Spatial layout GUI-only | P5：AI propose, human dispose |
| AI Agent API（edit card / whiteboard content）roadmap 未穩定 | 直接依賴會 break | spec 層引用「未來 API」不當 hard dependency |

---

## §11 Success Metrics

### 11.1 v3.0 目標（相對 v2.1 基線）

| 指標 | v2.1 基線 | v3.0 目標 |
|------|----------|---------|
| Heptabase 有 knowledge_id 的 cards 佔比 | ~20% | > 50% |
| `_discovered_links.json` v2 provenance 完整欄位覆蓋 | 0%（legacy 欄位）| > 80% new entries |
| Proposed links 的 accept rate（3 次 audit 後）| — | > 40% |
| Feature Family Whiteboard 累積 | 0（class 未定義）| ≥ 3 |
| Propose-Links runs per month | 0（skill 未存在）| 2-4 |
| Whiteboard maturity 明示標記覆蓋率 | 0% | > 50%（at least `forming+`）|
| Bridge debt（isolated cards）| 未追蹤 | Audit 可見，< 20% |

### 11.2 失敗訊號（觸發 v3.1 review）

- Accept rate < 20% 連續 3 次 → detection 邏輯有問題
- User 回報 edge taxonomy 不夠用 → 準備 v3.1 vocabulary extension
- Link class 分類 user 覺得混亂 → revisit canonical/proposed/exploratory 分界

---

## §12 Review Feedback Disposition (v3.0 round)

v3.0 draft 產出過程的外部 review 意見處置：

| 來源 | 建議 | 處置 |
|------|------|------|
| ChatGPT (2026-04-24) | 升級為四迴圈 operating model | **已採納** §4 |
| ChatGPT | 三種 link class 明確分開 | **已採納** §5.1 |
| ChatGPT | Link acceptance workflow 5 states | **已採納** §5.2 |
| ChatGPT | Registry schema v2 6 欄位 | **已採納** §3.2 + §3.3（含向後相容）|
| ChatGPT | Whiteboard maturity 4 levels | **已採納** §6 |
| ChatGPT | Feature Family Whiteboard first-class | **已採納** §7 |
| ChatGPT | Three-plane architecture | **已採納** §8 + P6 |
| ChatGPT | Bridge debt audit | **推延 Phase 3** §9 |
| ChatGPT | Per-whiteboard convergence history | **推延 Phase 3** §9 |
| Gemini (2026-04-24) | Zettel-walk 自動 journal append（zero-friction）| **已採納** — 將寫入 Zettel-Walk v2.2（§4.2 Crystallize 原則允許，因 Journal = ephemeral）|
| Gemini | GC 自動 tag「[ARCHIVED]」舊卡 | **部分採納** — edit canonical 內容需 human gate（P5）；改為「propose rename，user confirm」而非自動 |
| Gemini | Propose-Links 自動 create「🗂️ 建議」卡塞進 whiteboard | **已採納** — 新卡、明確標記、不改既有語義，符合 P5 |
| Gemini + ChatGPT 共識 | 不要 auto-wire / 不爆炸 taxonomy / 不急跳圖算法 | **保留 discipline** — P5 + §5.3 + §9 Phase 4 gate |

---

## §13 Implementation Cascade

v3.0 簽收後，child specs 依序升：

| # | Spec | Rev | 變動 |
|---|------|-----|------|
| 1 | **此 spec** | v2.1 → v3.0 | 本次 |
| 2 | `DEV_SPEC_HEPTABRAIN_SYNC.md` | v2.1 → v2.2 | 引用 v3 Registry schema、three-plane、link class |
| 3 | `DEV_SPEC_ZETTEL_WALK.md` | v2.1 → v2.2 | 引用 v3；Gemini 的自動 journal append 採納 |
| 4 | `DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md` | v1.0 → v1.1 | 引用 v3；Gemini 的 create-suggestion-card 採納；Feature Family class link |

MDA extension + Strategic Review System 本次 review 未直接涉及，不動。

---

*DRAFT — 待簽收 before implementation cascade.*
