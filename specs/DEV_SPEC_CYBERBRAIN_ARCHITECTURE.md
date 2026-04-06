# Dev Spec: Cyberbrain Architecture (電馭大腦基礎設施)

**Version:** v2.1 FINAL
**Date:** 2026-04-06
**Author:** Architect (Claude Code)
**Status:** Ready for implementation
**Review:** Gemini APPROVE, ChatGPT APPROVE (both with minor revisions, incorporated)
**Changelog:**
- v1.0: Initial draft
- v2.0: State/Knowledge 解耦、per-type authority、升維搜尋、link evidence
- v2.1: GC 機制、discovered_links registry、elevation anchors、bridge dialectic、canonicality metadata-first

---

## 1. Problem Statement

目前的知識連結基礎設施由五個獨立系統組成，彼此之間幾乎沒有連結：

```
Heptabase ──X── Claude Memory ──X── Wiki KBs ──X── Blog
  (視覺化)       (session 脈絡)     (結構化研究)    (公開輸出)
                                        │
                                   Heptabase Journal
                                     (未串接)
```

這違反了「電馭大腦」的核心哲學：**知識的價值不在節點本身，而在節點之間的連結。**

## 2. Design Principles

### P1: 解耦「狀態」與「知識」(State vs Knowledge)

- **State：** 天/週級別過期。例：bug lists、session logs、待辦。
- **Knowledge：** 經結晶化的洞見，不隨時間貶值。例：策略決策、架構原則、研究發現。

只有 Knowledge 才能進入 Heptabase。State 留在 Memory。

**Canonicality 判定：metadata-first, heuristic-fallback。**
Memory file 的 frontmatter 應顯式標記 canonicality。Heuristic（檔名規則、關鍵字）僅作為 fallback，未標記的進 audit queue。

### P2: 各系統有各自的 Canonical Authority

| Entity Type | Canonical Source | Authority Status |
|-------------|-----------------|-----------------|
| Task context / WIP state | **Claude Memory** | ephemeral |
| Curated concept notes | **Heptabase** | canonical |
| Structured research evidence | **Wiki KBs** | canonical |
| Public synthesis | **Blog** | derived |
| Reflective raw material | **Heptabase Journal** | candidate |
| Operational feedback/prefs | **Claude Memory** | reference |

Mixed-source entities 用 `authority_status` 追蹤生命週期：
- `candidate` → 未結晶，來自 journal/session，等待升格
- `canonical` → 已結晶，可被 supersede
- `derived` → 來自其他 canonical source 的衍生物
- `reference` → 不作為 authority，只指向外部

### P3: 連結必須帶 Evidence（可追溯性）

每條 AI 建議的連結至少包含：
- `relation_type`：supports / contradicts / derives_from / applies_to / example_of / bridge_to / **tensions_with**
- `rationale`：為什麼相關（一句話）
- `evidence`：來源參照
- `review_state`：proposed → accepted / rejected

**v2.1 新增：** 連結不只存在於 markdown output，也持久化到 `discovered_links.json`。

### P4: 升維時有錨點 (Elevation Anchors)

Zettel-walk 的升維抽象化需要方向性，否則每次抽象結果不穩定。定義一組「升維錨點」— 使用者目前最關注的核心維度：

```
Elevation Anchors (可隨時修改):
1. 系統韌性 (System Resilience)
2. 經濟誘因與邊界條件 (Economic Incentives & Boundary Conditions)
3. 臨床回饋迴圈 (Clinical Feedback Loops)
4. 規模化與治理 (Scaling & Governance)
5. 人機協作 (Human-AI Collaboration)
```

升維時 AI 優先映射到這些錨點上，像高速公路一樣提高跨域碰撞機率。錨點本身不是 ontology，只是 prompt-level 的方向引導。

### P5: Journal 中繼，不直接建卡片 (v2.1 UX 決策)

> Heptabase MCP 只能在主空間建卡片，無法放到 whiteboard 或定位。手動拖卡片 + 想位置 + 拉連線是使用者最大的摩擦來源。

**解法：Journal 作為中繼站。**

```
Zettel-walk 發現 → 寫入當天 Heptabase Journal（append_to_journal）
                     ↓
User 在 Heptabase 瀏覽 Journal
                     ↓
覺得好的段落 → 右鍵「Turn into card」→ 一鍵在當前 whiteboard 上建卡
```

- **Zettel-walk 發現：** 預設寫入 Journal，不直接建卡片
- **HeptaBrain sync 萃取：** 仍建卡片（因為是結晶知識），但附 Whiteboard Placement 建議（推薦 whiteboard + section + 連結對象 + 位置 hint），降低手動整理的認知負擔

這讓手動工作從「拖卡片 + 想位置 + 拉連線」降到「Turn into card（一鍵）」或「按照 placement hint 拖一次」。

## 3. System Registries

### 3.1 Sync Registry (`_heptabrain_registry.json`)

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
  "aliases": ["iRehab scaling", "愛復健擴展策略"],
  "heptabase_card_title": "...",
  "synced_at": "2026-04-06T14:30:00+08:00"
}
```

### 3.2 Link Registry (`_discovered_links.json`) — v2.1 新增

追蹤 AI 發現的知識連結。防止重複發現、支持回溯審計。

```json
{
  "link_id": "lk-001",
  "from_knowledge_id": "kb-eper-loop",
  "to_knowledge_id": "kb-safety-ii",
  "relation_type": "shares_principle",
  "rationale": "Both optimize through observation-feedback loops",
  "evidence_refs": ["Heptabase card: E-P-E-R §2", "Safety-II KB: page 3"],
  "review_state": "accepted",
  "discovered_at": "2026-04-06T15:00:00+08:00",
  "discovered_by": "zettel-walk wander"
}
```

### 3.3 Heptabase Reference (`_heptabase_refs.json`)

Session-scoped card references，即時讀取用。

```json
{
  "session_id": "2026-04-06T14:30",
  "topic": "iRehab strategy",
  "pulled_at": "2026-04-06T14:30:00+08:00",
  "refs": [
    {
      "card_id": "0425a30d-...",
      "title": "電馭大腦",
      "summary": "三樓架構：學習/工作/個人",
      "relevance": "knowledge infrastructure design"
    }
  ]
}
```

## 4. Five Improvement Areas

### 4.1 HeptaBrain Sync (#1 — highest ROI)
- 知識萃取式 push（非全文複製）
- URI 參照式 pull（非內容快取）
- GC command 產出清理待辦
- **Detailed spec:** `DEV_SPEC_HEPTABRAIN_SYNC.md`

### 4.2 Zettel Walk (#2 — highest fun)
- 升維搜尋 + elevation anchors
- Bridge 含辯證維度（張力 + 共通性）
- Link evidence → discovered_links.json
- **Detailed spec:** `DEV_SPEC_ZETTEL_WALK.md`

### 4.3 Cross-KB Connection Report (#3)
- Digest 內嵌 step 5.5
- 輸出 structured format
- 發現的 cross-KB links 寫入 discovered_links.json

### 4.4 Blog Audit Links (#4)
- 死連結掃描
- KB-Blog 不同步標記
- 缺交叉引用建議

### 4.5 Personal Context Layer (#5 — optional)
- Zettel-walk journal mode
- Journal → candidate → canonical 升格路徑

## 5. Priority & Dependencies

```
Phase 1 (本週):
  #1 heptabrain-sync ← 無依賴
  #2 zettel-walk     ← 無依賴

Phase 2 (下週):
  #3 cross-kb-connections ← 依賴 discovered_links.json (Phase 1)
  #4 blog-audit-links     ← 無依賴

Phase 3 (when ready):
  #5 personal-context     ← 依賴 #2 journal mode
```

## 6. Technical Constraints

| 限制 | 影響 | 因應 |
|------|------|------|
| Heptabase MCP 不支援 edit/delete | 無法更新/刪除卡片 | `supersedes` + GC cleanup list |
| Heptabase MCP 不支援 tag API | 無法程式化加 tag | Card 底部 `Tags:` 文字行 |
| Vector search 只找同域鄰居 | 跨域連結找不到 | 升維搜尋 + elevation anchors |
| Memory 200 行 index 限制 | 不能放太多東西進 MEMORY.md | Heptabase 內容不進 MEMORY.md |

## 7. Success Metrics

| 指標 | 基線 (2026-04-06) | Phase 1 目標 |
|------|-------------------|-------------|
| Heptabase 有 knowledge_id 的卡片佔比 | 0% | >50% |
| discovered_links.json 中的連結數 | 0 | >10（含 accepted + proposed） |
| 跨域連結發現 | 0（純手動） | 每週 1 次 zettel-walk |
| Superseded 卡片積壓 | 未追蹤 | GC 清單每週清理 |

## 8. Review Feedback Disposition (v1.0 + v2.0 → v2.1)

| 來源 | 批評 | 處置 |
|------|------|------|
| Gemini v1 | State/Knowledge 混淆 | **已修正 v2.0** |
| Gemini v1 | 升維搜尋 | **已修正 v2.0** |
| Gemini v1 | ontology.json | **已修正 v2.0** — aliases 取代 |
| Gemini v2 | GC 機制缺失 | **已修正 v2.1** — `/heptabrain-sync gc` |
| Gemini v2 | Bridge 缺辯證維度 | **已修正 v2.1** — `tensions_with` relation type |
| Gemini v2 | 升維錨點 | **已修正 v2.1** — P4 Elevation Anchors |
| ChatGPT v1 | Canonical entity registry | **已修正 v2.0** — 輕量 registry |
| ChatGPT v1 | Typed edges | **已修正 v2.0** — link evidence |
| ChatGPT v1 | Per-type authority | **已修正 v2.0** |
| ChatGPT v2 | discovered_links.json | **已修正 v2.1** — SS3.2 |
| ChatGPT v2 | canonicality metadata-first | **已修正 v2.1** — P1 updated |
| ChatGPT v2 | session_id in refs | **已修正 v2.1** — SS3.3 |
| ChatGPT v2 | collision audit | **已修正 v2.1** — 併入 audit command |
| ChatGPT v2 | internal novelty + evidence scores | **已修正 v2.1** — zettel-walk internal |
| ChatGPT v1 | Review workflow | **推回** — 一人系統不需 formal state machine |
| ChatGPT v1 | JSON alongside markdown | **推回** — 無 downstream automation（internal audit 用 registry JSON） |
| ChatGPT v1 | idempotency + lockfile | **推回** — 單人單機，content_hash 足夠 |

---

*Approved for implementation.*
