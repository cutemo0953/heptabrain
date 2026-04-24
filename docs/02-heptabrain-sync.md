# Dev Spec: HeptaBrain Sync (知識萃取式同步)

**Version:** v2.2 DRAFT
**Date:** 2026-04-24
**Author:** Architect (Claude Code)
**Parent Spec:** `DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md` **v3.0** (2026-04-24)
**Cyberbrain Role:** Loop 1 — **Crystallize**（memory / spec → HB canonical cards）
**Status:** DRAFT — 待簽收 (v2.1 shipped behavior 不變，v2.2 新增 v3 alignment + CLI-enabled enhancements)

**Changelog:**
- v1.0: 雙向內容同步
- v2.0: State/Knowledge 解耦、URI 參照、knowledge_id registry
- v2.1 FINAL: GC command、canonicality metadata-first、authority_status、session_id、collision audit
- **v2.2 (2026-04-24):** Aligned to Cyberbrain v3.0:
  - §0 新增 Four-Loop Role 標示
  - §2.1 萃取出的 cards 標記 `link_class: canonical`（§2.7 新增）
  - §2.3 GC 引入 CLI-assisted 半自動（tag rename，仍 human-gated 對既有 canonical 卡）
  - §2.4 Audit 新增 stale detection（v3 §5.2 lifecycle state）
  - §2.5 Registry entries 寫入時對齊 v3 Schema v2 provenance fields（若為 link-type metadata）
  - §3 新增 `audit stale` 子指令
  - §6 Out of Scope 移除「Whiteboard 組織」與「Tag API」（CLI 已解鎖 tag；組織歸 Propose Links）

---

## 1. Problem

Claude Code memory 和 Heptabase 是兩個孤島。v1.0 的「雙向內容同步」和 v2.0 的「知識萃取」已解決主要問題，v2.1 補齊治理層：

- 被 supersede 的舊卡片需要清理機制（GC）
- canonicality 判定需要 metadata-first，heuristic 只做 fallback
- 同概念異名卡片需要定期偵測（collision audit）

## 2. Solution: `/heptabrain-sync` Skill

### 2.1 Outbound: Knowledge Distillation (Memory → Heptabase)

**Step 1: Canonicality 篩選 — metadata-first**

首先檢查 frontmatter 中是否有顯式標記：

```yaml
---
name: My Feature Strategy
type: project
canonicality: knowledge        # 顯式標記
authority_status: canonical    # 顯式標記
---
```

| 判定來源 | 邏輯 | 優先級 |
|----------|------|--------|
| frontmatter `canonicality: knowledge` | 直接通過 | 1st（最高）|
| frontmatter `canonicality: state` | 直接拒絕 | 1st |
| frontmatter `type: feedback` 或 `type: user` | 一律拒絕 | 2nd |
| 檔名含 `session_` / `bugs_` / `_YYYYMMDD` | 拒絕（State heuristic）| 3rd（fallback）|
| 內容含「策略」「結論」「原則」「架構」 | 可能是 knowledge | 3rd |
| 以上都無法判定 | 進 audit queue → 提示 user 確認 | 4th |

**Step 1.5: Whiteboard Discovery（v2.1 新增）**

在萃取前，先用 `search_whiteboards` 取得使用者現有的 whiteboard 清單（名稱 + ID）。這讓 Step 2 的萃取可以在 Placement 段落中推薦具體的 whiteboard。

```
搜尋 query：用 memory file 的核心關鍵字搜尋
快取：whiteboard 清單可快取整個 push session，不需每張卡片都重查
```

**Step 2: Knowledge Distillation**

AI 萃取（非複製）：

```
Card format:
  # {knowledge title}
  
  ## Core Insights
  {3-5 bullet points — distilled, not copied}
  
  ## Underlying Principle
  {1-2 sentences — the "so what" that won't expire}
  
  ## Relations
  - Relates to: [card X] — {relation_type}: {rationale}
  
  ## Whiteboard Placement (v2.1)
  - Suggested whiteboard: "{AI 根據內容推薦的 whiteboard 名稱}"
  - Suggested section: "{whiteboard 內的 section，若適用}"
  - Connect to: [{相關卡片 1}], [{相關卡片 2}]
  - Position hint: "{相對位置建議，如：放在 X 卡片右側}"
  
  ---
  **Knowledge ID:** {knowledge_id}
  **Authority:** {canonical|derived|candidate}
  **Source:** Claude Code Memory → `{filename}`
  **Distilled:** {ISO timestamp}
  **Tags:** #knowledge-sync #{topic}
```

**Step 3: Duplicate Check**

```
1. Registry lookup by knowledge_id
2. If found + content_hash matches → skip
3. If found + hash different → supersede flow:
   - 建新卡片，標注 [Supersedes: {old_knowledge_id}]
   - Registry: old entry 加 superseded_by 欄位
   - GC queue: old card 進入待清理清單
4. If not found → alias matching + semantic search
   - 若找到疑似重複 → 提示 user 確認
   - 若確認無重複 → 建新卡片
```

### 2.1.5 Link Class Policy — v2.2 新增（對齊 Cyberbrain v3 §5.1）

Sync 寫入 HB 的 card，其在 Registry 標記為：

| Artifact | link_class | 理由 |
|----------|-----------|------|
| Sync push 結晶化後的 Heptabase card | `canonical` | 經 user-sourced（memory/spec/review 有明確意圖）結晶化，穩定度高 |
| 若 sync 產生 card ↔ 現有 card 的 Whiteboard Placement 建議連結 | `proposed` | Placement 是 AI 推論，需 user 在 HB GUI accept |
| Sync 產 card 本身未跟其他 card 直接產連結 | 無 | 該 card entry 存於 `_heptabrain_registry.json`（knowledge registry），不是 `_discovered_links.json` |

Sync 不產 `exploratory` class 的 links（那是 zettel-walk 的領域）。

### 2.2 Inbound: URI Reference (Heptabase → Session Context)

```
/heptabrain-sync pull [topic]
```

**Flow:**

```
1. Semantic search Heptabase (topic + aliases from registry)
2. Top 5 relevant cards → 記錄 card_id + title + 2-line summary
3. 寫入 _heptabase_refs.json（含 session_id 防覆蓋）
4. 需要全文時 → getObject(card_id) 即時讀取
```

```json
{
  "session_id": "2026-04-06T16:30",
  "topic": "my project strategy",
  "pulled_at": "2026-04-06T16:30:00+08:00",
  "refs": [
    {
      "card_id": "0425a30d-...",
      "title": "電馭大腦",
      "summary": "三樓架構。核心：連結 > 節點。",
      "relevance": "knowledge infrastructure design"
    }
  ]
}
```

### 2.3 Garbage Collection — v2.1 + v2.2 CLI-assisted

```
/heptabrain-sync gc              — 列表 + 操作建議（v2.1 行為，預設）
/heptabrain-sync gc --assist     — v2.2 新增：CLI 半自動，建議 rename 舊卡加 [ARCHIVED] 前綴
/heptabrain-sync gc confirm      — v2.1：清 registry 記錄
```

**v2.1 Flow（預設，保守）:**

```
1. 掃 Registry，找所有 superseded_by 非 null 的 entries
2. 輸出 Markdown 清理待辦（user 手動在 HB UI 刪除）
3. `/heptabrain-sync gc confirm` → 從 registry 移除已清理的 entries
```

**v2.2 Flow（`--assist` 旗標，CLI 半自動）:**

Gemini 2026-04-24 建議：CLI 開放後可自動在舊卡 rename 加 `[ARCHIVED]` 前綴作為視覺標記，無需刪除即可讓 graph 看出演化軌跡。

但 Cyberbrain v3 P5 明示：**edit 既有 canonical 內容必須 human gate**。因此 v2.2 改為「propose + confirm」兩步：

```
Step 1: `/heptabrain-sync gc --assist`
  - 掃 Registry 找 superseded_by 非 null
  - 產出 proposed-renames.md：
      | 舊卡 id | 現 title | 建議新 title | supersedes_by | 預覽變動 |
      |--------|---------|------------|-------------|---------|
      | abc... | "My Feature v1" | "[ARCHIVED] My Feature v1" | kb-v2 | 僅改 title |
  - 每項產 HB deeplink 方便 user 查看原卡
  - **不**執行任何寫入

Step 2: User 檢查 proposed-renames.md，刪除他不想改的 rows

Step 3: `/heptabrain-sync gc --assist --commit`
  - 讀經 user 編輯過的 proposed-renames.md
  - 對每項走 CLI `heptabase save` + 新 title + 原內容（附一行 note 指向新卡）
  - 成功 → Registry 該 entry 設 `status: archived`（保留歷史軌跡，不移除）
  - 失敗 → 報錯，不改 registry

Step 4: `/heptabrain-sync gc confirm`（v2.1 behavior 保留）
  - 從 registry 真實移除 `status: archived` entries（若 user 想徹底清理）
```

**為什麼不完全自動：** 即使 CLI 技術上支援 edit，Cyberbrain v3 P5 的 ephemeral-vs-canonical 邊界要求：改動 canonical 卡需 human-confirm，因為：
- 寫錯了 rollback 困難
- Cards 可能被其他人（或你過去的自己）在 HB 筆記中引用
- 視覺 archive 標記會改變卡片在搜尋結果中的呈現

### 2.4 Collision Audit + Stale Detection — v2.2 擴充

```
/heptabrain-sync audit              — v2.1 collision + orphan（不變）
/heptabrain-sync audit stale        — v2.2 新增：偵測 stale lifecycle state
```

**v2.1 collision audit（保留）：**

```
1. 掃 registry aliases
2. Semantic search Heptabase 找：
   a. 多張卡片匹配同一概念？（疑似重複）
   b. Registry 有但 HB 卡被刪？（孤兒）
   c. HB 有但 registry 無？（未追蹤）
```

**v2.2 stale audit（新增，對齊 Cyberbrain v3 §5.2 lifecycle）：**

```
1. 掃 registry 所有 entries 的 last_verified_at
2. 超過 180 天未 touch 的 entries 標 stale 候選
3. 對每個 stale 候選：
   a. Semantic search HB 看對應 card 是否還存在 + 內容是否大改
   b. 若存在且內容未變 → 更新 last_verified_at 為今天（remain canonical）
   c. 若存在但內容大改 → 標 needs_reacceptance + 進 propose-rename queue
   d. 若不存在 → 標 orphan，進 cleanup queue
4. Registry 寫回新狀態 + audit report 給 user
```

### 2.4 Collision Audit — v2.1 新增

```
/heptabrain-sync audit
```

**Flow:**

```
1. 掃描 registry 中所有 aliases
2. 對每組 aliases，semantic search Heptabase 檢查：
   a. 是否有多張卡片匹配同一概念？（疑似重複）
   b. 是否有 registry entry 但 Heptabase 卡片已被手動刪除？（孤兒記錄）
   c. 是否有 Heptabase 卡片但 registry 中無記錄？（未追蹤卡片）
3. 輸出 audit report
```

### 2.5 Sync Registry (v2.1)

```json
{
  "version": "2.1",
  "lastSync": "2026-04-06T14:30:00+08:00",
  "entries": [
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
      "heptabase_card_title": "My Feature Strategy — Core Principles",
      "synced_at": "2026-04-06T14:30:00+08:00"
    }
  ]
}
```

## 3. Skill Interface

```
/heptabrain-sync push              — 萃取所有 knowledge-level memory → Heptabase
/heptabrain-sync push [filename]   — 萃取指定 memory file
/heptabrain-sync pull [topic]      — 搜尋相關 Heptabase 卡片，存 URI reference
/heptabrain-sync status            — Registry 狀態 + 統計
/heptabrain-sync audit             — 重複偵測 + 孤兒檢查 + 未追蹤卡片
/heptabrain-sync gc                — 列出待清理的 superseded 卡片
/heptabrain-sync gc confirm        — 清除已手動刪除的 registry 記錄
```

## 4. Implementation Plan

| Step | 內容 | 預估 |
|------|------|------|
| 1 | 建立 `~/.claude/commands/heptabrain-sync.md` skill | 30 min |
| 2 | 實作 canonicality 篩選（metadata-first + heuristic fallback）| 15 min |
| 3 | 實作 knowledge distillation（AI 萃取）| 30 min |
| 4 | 實作 registry v2.1（+ superseded_by + authority_status）| 20 min |
| 5 | 實作 pull flow（URI reference + session_id）| 20 min |
| 6 | 實作 gc + gc confirm | 15 min |
| 7 | 實作 audit（collision + orphan + untracked）| 20 min |
| 8 | 測試 | 15 min |

**Total:** ~3 hours

## 5. Edge Cases

| Case | 處理 |
|------|------|
| Memory file 無 frontmatter canonicality | Heuristic fallback → 若仍無法判定 → audit queue |
| Memory file 更新但同概念 | Supersede flow → GC queue |
| Memory file 概念分裂 | 提示 user：supersede or new knowledge？ |
| Heptabase 已有同概念卡片（非 sync） | Alias matching → 提示 user 是否關聯 |
| MCP 失敗 | 報錯，不更新 registry |
| Push 成功但 registry 寫入前 crash | 下次 audit 會發現不一致 |
| GC confirm 但卡片未真正刪除 | Registry 記錄移除 → 不影響功能，audit 會標為 untracked |

## 6. Out of Scope (v2.2)

- 自動觸發 hooks
- Heptabase → Memory 反向寫入
- 三層 entity-version-edge registry
- ontology.json

**以下 v2.1 Out of Scope 在 v2.2 改狀態：**

| 原 v2.1 out-of-scope | v2.2 狀態 | 原因 |
|------------------|---------|------|
| Whiteboard 組織 | **Moved to `/heptabrain-propose-links`**（見 Cyberbrain v3 §4.2 Converge loop） | v3 新增 Loop 2 = Converge 負責此塊 |
| Tag API | **Partially enabled**（v2.2 §2.3 `--assist` 可 rename title；full tag CRUD 仍待 Heptabase AI Agent API stable）| CLI release 解鎖 title edit，但全 tag API 尚未穩定 |
| Formal review state machine | **Moved to Cyberbrain v3 §5.2**（5-state lifecycle 已定義）| Parent spec 正式化 |

---

*Approved for implementation.*
