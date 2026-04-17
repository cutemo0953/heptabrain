# Dev Spec: HeptaBrain Sync (知識萃取式同步)

**Version:** v2.1 FINAL
**Date:** 2026-04-06
**Prepared with:** Claude Code (Opus, multi-round Gemini + ChatGPT review)
**Maintained by:** the Cyberbrain contributors
**Parent Spec:** `DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md` (#1)
**Status:** Ready for implementation
**Changelog:**
- v1.0: 雙向內容同步
- v2.0: State/Knowledge 解耦、URI 參照、knowledge_id registry
- v2.1: GC command、canonicality metadata-first、authority_status、session_id、collision audit

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
name: ExampleProject Scaling Strategy
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
  "topic": "ExampleProject strategy",
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

### 2.3 Garbage Collection — v2.1 新增

```
/heptabrain-sync gc
```

**Flow:**

```
1. 掃描 Registry，找所有 superseded_by 非 null 的 entries
2. 輸出 Markdown 清理待辦：

## HeptaBrain GC — 待清理卡片

| # | 舊卡片 | 被取代者 | Superseded at |
|---|--------|----------|---------------|
| 1 | "ExampleProject Scaling v1" | kb-exampleproject-scaling-v2 | 2026-04-10 |
| 2 | "PartnerDueDiligence v1" | kb-partner-dd-v2 | 2026-04-12 |

請在 Heptabase UI 中刪除以上卡片。
刪除後執行 `/heptabrain-sync gc confirm` 清除 registry 記錄。

3. User 在 Heptabase UI 手動刪除
4. `/heptabrain-sync gc confirm` → 從 registry 移除已清理的 entries
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
      "knowledge_id": "kb-exampleproject-scaling",
      "source_system": "memory",
      "source_file": "project_exampleproject_scaling.md",
      "canonicality": "knowledge",
      "authority_status": "canonical",
      "content_hash": "sha256:abc123...",
      "supersedes": null,
      "superseded_by": null,
      "aliases": ["ExampleProject scaling", "ExampleProject 擴展策略"],
      "heptabase_card_title": "ExampleProject Scaling Strategy — Core Principles",
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

## 6. Out of Scope (v2.1)

- 自動觸發 hooks
- Heptabase → Memory 反向寫入
- Whiteboard 組織
- Tag API
- 三層 entity-version-edge registry
- ontology.json
- Formal review state machine

---

*Approved for implementation.*
