# Heptabrain — Phase 2 Implementation Plan

**Status：** Draft, ⛔ awaiting sign-off before implementation.
**Scope：** 三條路徑（Pass 2 LLM analysis / Gap signals / `_discovered_links.json` write + Suggestion card）。
**Prereqs：** Phase 0+1 + Phase 2.1 connection diff 已 merged（commits 569b930, b4594fc, da90930, 25deae8）。
**Specs governing this plan：**
- `docs/01-cyberbrain-architecture.md` v3.0.1 — registry schema v2 / Four-Loop / class promotion
- `docs/04-heptabrain-propose-links.md` v1.2.2 — §2.3 Step 4 / 6 / 7 / 8、§4.2、§4.5
- `docs/IMPLEMENTATION_PLAN_PHASE_0_1.md` — 上一份 plan，本 plan 風格沿用

---

## 0. 背景

Phase 0+1 + Phase 2.1 完成後，propose-links dry-run 能對 fixture / snapshot whiteboard 跑：
1. discover → inventory → maturity gate → TF-IDF 預篩 → top pair → connection diff (NEW/EXISTS/REDUNDANT/CONFLICT)
2. 寫一份 human-readable markdown 到 `propose_links/<date>_<slug>.md`
3. **不寫 registry、不建卡、不打 LLM**

Phase 2 把它從「dry-run 演習」升級為「實際輸出 link suggestion + 圖論診斷 + 持久化」。

**範圍三條（user 2026-04-28 sign-off "all"）：**

| Path | Spec ref | 體感 |
|------|----------|------|
| **2A. Pass 2 LLM analysis** | §2.3 Step 4 | 真的產出帶 `relation_type` + `rationale` + `confidence` 的 link |
| **2B. Gap signals 5 類** | §2.3 Step 7 | 圖論診斷（weak / hub / fragile bridge / merge candidate / spaghetti）|
| **2C. `_discovered_links.json` write + Suggestion card** | §2.3 Step 8、§4.2、§4.5 | 持久化 + opt-in 寫回 HB |

**不在 Phase 2 範圍（仍 deferred 至 Phase 3+）：**
- Auto-accept detection（topology + relation + confidence 三重閘）
- Lazy write-back commit flow（拉真連線進 HB）
- Clustering theme naming 的 LLM 步驟（Phase 2 的 Louvain 只算 community partition for fragile bridge signal；不命名 theme）
- MDA 4D sketch（§2.4）
- Journal append（§4.3）
- Re-propose cooldown / rejection_reason tracking
- Meta card YAML sync

---

## 1. File Tree（Phase 2 結束後）

```
scripts/
├── constants/
│   └── relation_types.py            (Phase 0)
├── lib/
│   ├── mcp_client.py                (Phase 1, unchanged)
│   └── llm_client.py                (Phase 2A — NEW; pass-through Protocol)
├── propose_links/
│   ├── cli.py                       (extend: --with-pass2 / --emit-pairs / --signals / --discovered-json / --suggestion-card)
│   ├── discovery.py                 (Phase 1, unchanged)
│   ├── inventory.py                 (Phase 1, unchanged)
│   ├── maturity_detect.py           (Phase 1, unchanged)
│   ├── tfidf_prefilter.py           (Phase 1, unchanged)
│   ├── connection_diff.py           (Phase 2.1, unchanged)
│   ├── output.py                    (extend: signals + pass2 sections)
│   ├── pass2_merge.py               (Phase 2A — NEW)
│   ├── gap_signals.py               (Phase 2B — NEW)
│   ├── discovered_links_writer.py   (Phase 2C — NEW)
│   ├── suggestion_card.py           (Phase 2C — NEW)
│   └── smoke_run.py                 (extend: end-to-end with simulated LLM output)
└── registry/                        (Phase 0, unchanged)

.claude/commands/
└── propose-links.md                 (Phase 2 — NEW skill, orchestrates MCP + Python + native LLM Pass 2)

tests/
├── test_pass2_merge.py              (Phase 2A — NEW)
├── test_gap_signals.py              (Phase 2B — NEW)
├── test_discovered_links_writer.py  (Phase 2C — NEW)
├── test_suggestion_card.py          (Phase 2C — NEW)
└── fixtures/
    ├── pass2_results.json           (NEW — simulated LLM output)
    └── whiteboard_with_clusters.json (NEW — fixture with 3 communities + bridges)
```

---

## 2. Phase 2A — Pass 2 LLM Analysis（3 modules + skill changes）

### 2A.1 Pattern：Python 不打 LLM

**核心決策：** Pass 2 LLM 分析由 **Skill (markdown) 用 Claude 原生跑**，不在 Python 內叫 anthropic SDK。理由：
- 對齊 zettel-walk skill 模式（既有 9.1K markdown skill 即此架構）
- 零 API key 依賴 / 零增量成本
- LLM output 用 fixture JSON 餵回 Python 做 deterministic merge → 可單元測試

Python 端責任：
- `--emit-pairs`: 從 inventory + TF-IDF 輸出 top 50 pair JSON（每 pair 含 cardA/cardB title + first 500 chars + tags）
- `--with-pass2 <results.json>`: 讀 LLM 回傳，merge 到 classified pair，render 進 markdown

Skill 端責任（`.claude/commands/propose-links.md`）：
- 呼叫 MCP 抓 whiteboard → fixture JSON
- 跑 Phase 1 CLI 拿 top 50 pair（`--emit-pairs > /tmp/pairs.json`）
- Claude 原生對每 pair 分析（spec §2.3 Step 4），結果寫 `/tmp/pass2.json`
- 跑 Phase 2 CLI `--with-pass2 /tmp/pass2.json --signals --discovered-json` 拿最終 markdown + JSON
- (opt) 呼叫 MCP 建 suggestion card

### 2A.2 `scripts/lib/llm_client.py`（NEW，30 行內）

純 Protocol + simulated client（fixture-backed）。**No real LLM call**。

```python
class LLMClient(Protocol):
    def analyze_pair(self, pair: PairContext) -> PairAnalysis: ...

class FixtureLLMClient:
    """Loads pre-recorded analyses from fixture JSON. Used by all unit tests."""
```

**Acceptance：** Protocol 定義清楚；FixtureLLMClient round-trip 無誤。

### 2A.3 `scripts/propose_links/pass2_merge.py`（NEW，~120 行）

純 function，無 I/O：
```python
def merge_pass2(
    classified_pairs: list[ClassifiedPair],   # from connection_diff
    pass2_results: list[PairAnalysis],        # from LLM
) -> list[EnrichedPair]:
    """Match by (from_id, to_id), attach relation_type/rationale/confidence.
    Skip EXISTS/REDUNDANT pairs (already linked → no need for new analysis).
    Pairs without a matching analysis: tag 'pass2_missing' + downgrade confidence='low'.
    """
```

Pair shape input:
```json
{"pair_id": "...", "from_id": "...", "to_id": "...",
 "from_title": "...", "to_title": "...",
 "from_tags": [...], "to_tags": [...],
 "from_excerpt": "first 500 chars", "to_excerpt": "..."}
```

LLM result shape:
```json
{"pair_id": "...",
 "relation_type": "shares_principle | extends | contrasts | ...",  // 11 types
 "rationale": "...",
 "confidence": "high | med | low",
 "evidence_kind": ["text_overlap", "shared_actor", ...]}
```

**Edge cases：**
- LLM returns `relation_type` not in 11-set → fallback `related_to` + flag `needs_review`（spec §2.2）
- Pair list 與 result list 不對齊（id 對不上）→ 不爆炸；keep pair 但 mark `pass2_missing`
- 同 pair_id 多筆 result → 取最後一筆並 warn

**Test：** 5 cases —
1. happy path（3 pair × 3 result）
2. unknown relation_type fallback
3. missing result for some pair
4. duplicate pair_id
5. EXISTS/REDUNDANT pair 被略過（不送 LLM、不期待 result）

### 2A.4 CLI extension

`cli.py` 加兩 flag：
- `--emit-pairs <file>`: 跳過 markdown render，把 top 50 pair（在 connection_diff 後過濾掉 EXISTS/REDUNDANT 的 NEW pairs）寫成 pair JSON
- `--with-pass2 <results.json>`: 讀 LLM 結果，呼叫 `merge_pass2`，render 加強版 markdown（含 relation_type / rationale / confidence per link）

兩 flag 互斥於 `--no-cjk-gate` 等舊 flag 邏輯不變。

**Acceptance：** Phase 2 smoke run 用 fixture LLM result 能跑出含 rationale 的完整 markdown。

---

## 3. Phase 2B — Gap Signals 5 類（1 module + output 擴充）

### 3.1 `scripts/propose_links/gap_signals.py`（NEW，~200 行）

NetworkX-backed pure function。Spec §2.3 Step 7。

```python
def compute_gap_signals(
    cards: list[CardInventoryEntry],
    proposed_links: list[EnrichedPair],     # NEW pairs only, post pass2_merge
    existing_connections: list[Connection], # from inventory
) -> GapSignalReport:
    """Returns dict with keys:
      - weak_integration: list[card_id]   # degree < 2
      - central_hub: list[card_id]        # top-3 betweenness
      - fragile_bridge: list[edge]        # bridges between Louvain communities
      - merge_candidate: list[pair]       # high conf + connection overlap > 70%
      - spaghetti: list[card_id]          # degree > max(5, N/3)
    """
```

**Implementation 策略：**
- Build undirected `nx.Graph` from `existing_connections + proposed_links`（degree 計算用合併圖）
- Degree dict → weak (< 2) / spaghetti (> max(5, N//3))
- `nx.betweenness_centrality` → top-3 by betweenness
- `nx.algorithms.community.louvain_communities`（best_partition fallback if older networkx）→ community map
- Bridge = edge whose endpoints sit in different communities AND removing it disconnects 2+ nodes from the smaller community（minimal cut check via `nx.connectivity.minimum_edge_cut` per pair）
- Merge candidate：iterate proposed_links where `confidence == 'high'`，計算 endpoints' existing-neighbor overlap（Jaccard > 0.7）

**v1.2.2 corner cases (spec §2.3 Step 6+7)：**
- Isolated nodes (degree 0) → 直接歸 `weak_integration`，不丟 Louvain
- Empty graph (no edges) → 全空 report，不爆炸
- N < 5 → skip clustering（fragile_bridge 永遠空）

**Test：** 6 cases —
1. happy path: 12-card fixture with 3 communities → expect 1 fragile bridge, 1 hub, 2 weak, 0 spaghetti
2. isolated nodes only
3. empty graph
4. spaghetti card (degree 8, N=20)
5. merge candidate (overlap = 0.85)
6. networkx unavailable → ImportError graceful fallback (emit empty report + warn)

### 3.2 Output extension

`output.py` 加 `## Gap Signals` 區塊，依 spec §4.1 格式：
```
## Gap Signals
🔹 Weak integration ({n}): card-x, card-y
🔹 Central hub: card-z
🔹 Fragile bridge ({n}): card-x ↔ card-y
🔹 Merge candidate ({n}): card-a ⇄ card-b (overlap 0.82)
🔹 Spaghetti warning ({n}): card-w (degree 7, N/3=6)
```

每類附 1 行建議（spec §2.3 Step 7 既有文案）。

**Acceptance：** 跑 12-card fixture → markdown 含預期 5 類 signal。

---

## 4. Phase 2C — `_discovered_links.json` Write + Suggestion Card（2 modules + skill）

### 4.1 `scripts/propose_links/discovered_links_writer.py`（NEW，~150 行）

寫 schema v2 entries（spec §4.2，Cyberbrain v3 §3.2）。**Append-only**，atomic write 用 `registry/atomic_write.py`。

```python
def append_discovered_links(
    registry_path: Path,
    enriched_pairs: list[EnrichedPair],
    whiteboard_id: str,
    run_timestamp: str,
) -> int:
    """Returns count of entries written.
    Skips: EXISTS, REDUNDANT, CONFLICT, pass2_missing pairs.
    Writes only NEW + has-pass2 + confidence in {high, med}.
    Schema: §4.2 v2 — link_class='proposed', acceptance_state='proposed',
             scope_type='whiteboard', scope_whiteboard_id=...,
             source_mode='propose-links', evidence_kind=[...],
             verified_by='ai', last_verified_at=ISO timestamp.
    Idempotency: link_id = lk-{run_ts}-{seq}; same run never duplicates;
                 cross-run dedup deferred to Phase 3 (re-propose cooldown).
    """
```

**Concurrency：** atomic_write read-modify-write 一次；多 process 同時跑 → last writer wins（小範圍 acceptable，跨 process 鎖 deferred）。

**Test：** 5 cases —
1. happy path: 5 pair, 3 high + 1 med + 1 low → 4 entries written
2. existing registry has 2 entries → append → final 6
3. atomic write crash mid-write → 原檔不破壞（mock os.replace failure）
4. low confidence pair excluded
5. EXISTS/REDUNDANT/pass2_missing excluded

### 4.2 `scripts/propose_links/suggestion_card.py`（NEW，~80 行）

純 function，產生 suggestion card markdown body（spec §4.5 格式）。
**不打 MCP** — Skill 端負責真正 create card。

```python
def render_suggestion_card(
    whiteboard_name: str,
    enriched_pairs: list[EnrichedPair],
    gap_signals: GapSignalReport,
    timestamp: str,
) -> str:
    """Returns markdown body matching §4.5 template.
    Includes: NEW links with checkboxes, top-3 gap signal callouts,
              footer reminding 'remove this card to roll back, no structure change'.
    """
```

**Acceptance：** Snapshot test against expected markdown（fixture-based）。

### 4.3 CLI extension

加 3 flag：
- `--signals`: 跑 gap_signals + 進 markdown
- `--discovered-json <path>`: 寫 entries 到指定 registry（預設不寫，沿 Phase 1 dry-run 紀律）
- `--suggestion-card <path>`: 寫 suggestion card markdown 到指定路徑（Skill 再讀回去 create HB card）

舊 Phase 2+ NotImplementedError trap：把 `--suggestion-card` 從 trap list 移除（現在實作了）。

### 4.4 Skill `.claude/commands/propose-links.md`（NEW）

完整 orchestration（mirrors zettel-walk pattern）。流程：

1. **Discover**：呼叫 `mcp__heptabase-mcp__search_whiteboards` 解析 user 輸入
2. **Snapshot**：`mcp__heptabase-mcp__get_whiteboard_with_objects` → 寫 `/tmp/wb_snapshot_{ts}.json` 為 fixture
3. **Phase 1 + 2.1 dry-run**：`python -m scripts.propose_links.cli <wb_id> --fixture <snapshot> --emit-pairs /tmp/pairs.json`
4. **Pass 2 native LLM**：Claude 對 `/tmp/pairs.json` 每 pair 跑 spec §2.3 Step 4 五項分析（principles / anchor / relation_type / rationale / confidence），寫 `/tmp/pass2.json`
5. **Merge + signals + write**：`python -m scripts.propose_links.cli <wb_id> --fixture <snapshot> --with-pass2 /tmp/pass2.json --signals --discovered-json memory/_discovered_links.json --suggestion-card /tmp/suggestion.md`
6. **(opt) Suggestion card create**：if user 同意 → `mcp__heptabase-mcp__save_to_note_card` with body from `/tmp/suggestion.md`
7. **Cleanup**：rm `/tmp/wb_snapshot_*` `/tmp/pairs.json` `/tmp/pass2.json`（保留 suggestion.md as audit trail）

**互動點：**
- Step 2 後：confirm whiteboard match
- Step 4：Claude 分析自 50 pair；no user prompt（除非 N>50 hard stop）
- Step 6：明問 user 「要不要建 🗂️ Suggestion Card？(y/n)」

---

## 5. 測試策略

### Unit tests（per module，Phase 0_1 慣例）
- `test_pass2_merge.py` — 5 cases (§2A.3)
- `test_gap_signals.py` — 6 cases (§3.1)
- `test_discovered_links_writer.py` — 5 cases (§4.1)
- `test_suggestion_card.py` — 2 cases (snapshot + edge: empty pair list)

### Integration test（end-to-end CLI）
擴充 `test_cli.py`：
- `--emit-pairs` 模式：fixture → JSON shape 對
- `--with-pass2 + --signals + --discovered-json`：fixture + simulated LLM result → markdown 含 signals 段 + registry file 寫入正確 entries

### Smoke run
`smoke_run.py` 加 `_simulate_pass2()` 用 hardcoded analyses 對 4-card snapshot whiteboard 跑完整 pipeline，**不打 MCP**（snapshot replay 模式）。

### Real-HB validation gate（人工）
- 對 1 個真 whiteboard 跑完整 Skill flow（含 native LLM Pass 2）
- 人工讀 markdown：rationale 是否合理 / signals 是否符合直覺 / suggestion card 是否能在 HB 看到
- 不通過 → 不算 Phase 2 done

---

## 6. Dependencies (`pyproject.toml`)

```toml
dependencies = [
    "scikit-learn>=1.4",   # Phase 1
    "numpy>=1.26",         # Phase 1
    "networkx>=3.2",       # Phase 2 啟用
]
```

NetworkX 在 Phase 0 plan 已預留宣告 — 此處正式啟用。**不新增** 任何 LLM SDK（anthropic / openai 都不引入）。

---

## 7. Implementation Order（建議 session 切分）

### Session A — Phase 2A（Pass 2 merge）約 2-3 小時
1. `lib/llm_client.py` Protocol + FixtureLLMClient → test
2. `propose_links/pass2_merge.py` → test (5 cases)
3. `cli.py` `--emit-pairs` flag → test_cli 擴充
4. `cli.py` `--with-pass2` flag → test_cli 擴充
5. `output.py` 加 rationale/relation_type 區塊 → test_output 擴充

每 module 完跑該 module pytest，全綠才下一步。

### Session B — Phase 2B（Gap signals）約 2-3 小時
1. `propose_links/gap_signals.py` → test (6 cases)
2. `output.py` Gap Signals 區塊 → test_output snapshot
3. `cli.py` `--signals` flag → test_cli

### Session C — Phase 2C（Persist + Card + Skill）約 2-3 小時
1. `propose_links/discovered_links_writer.py` → test (5 cases)
2. `propose_links/suggestion_card.py` → test (2 cases)
3. `cli.py` `--discovered-json --suggestion-card` flag → test_cli
4. `.claude/commands/propose-links.md` skill → 人工 smoke
5. `smoke_run.py` 擴充含 simulated pass2 + signals → 跑通

### Session D — Real-HB validation（half session）
- 跑 `/heptabase-status` 驗 MCP green
- 對 1 張真 whiteboard 跑完 Skill flow
- 人工 review markdown + suggestion card on HB
- 微調 prompt 細節（在 Skill markdown 中）

預估總時程 8-12 小時跨 4 sessions。

---

## 8. Acceptance 總表

| 項目 | Pass 標準 |
|------|----------|
| Phase 2A unit tests | pass2_merge / llm_client 全 green |
| Phase 2A integration | `--emit-pairs` + `--with-pass2` round-trip 正確 |
| Phase 2B unit tests | gap_signals 6 cases green |
| Phase 2B real-graph test | 12-card fixture 出 5 類 signal 預期值 |
| Phase 2C unit tests | discovered_links_writer / suggestion_card 全 green |
| Phase 2C atomic write | mock crash 不破壞既有 registry |
| Skill markdown | 對真 whiteboard 跑完不爆 + suggestion card 在 HB 可見 |
| Coverage | 新增 module > 80% |
| Codex review | P0 = 0；P1/P2 全修完才 push |

---

## 9. 不要做的事（sign-off 條件）

- ❌ 不要在 Python 內叫 anthropic / openai SDK（pass 2 由 Skill native 跑）
- ❌ 不要寫 auto-accept 邏輯（acceptance_state 永遠 'proposed'）
- ❌ 不要實作 lazy write-back commit flow（不真的 create HB connection edge）
- ❌ 不要實作 clustering theme naming 的 LLM 段（Louvain 只服務 fragile bridge signal）
- ❌ 不要實作 MDA 4D sketch（`--mda` 仍 Phase 3+ trap）
- ❌ 不要實作 journal append（`--journal` 仍 trap）
- ❌ 不要實作 re-propose cooldown / rejection_reason
- ❌ 不要修改 Phase 0/1/2.1 既有檔的核心邏輯（只能 extend output.py / cli.py）
- ❌ 不要動 sign-off 的 4 份 spec markdown
- ❌ 不要擴充 11 種 relation type
- ❌ Suggestion card content 永遠帶免責尾註「移除本卡不影響 whiteboard」

---

## 10. Session handoff 備忘

- 本 plan 為獨立文件；下個 session 只讀：(a) 本 plan, (b) `04-heptabrain-propose-links.md` v1.2.2, (c) `01-cyberbrain-architecture.md` v3.0.1 §3.2 / §6 / §7, (d) `IMPLEMENTATION_PLAN_PHASE_0_1.md`
- 不要再啟動另一輪 architecture review — spec 已 sign-off
- 跨 session 進度：每 session 結束 commit `phase2X: <module> + tests`，後者才接續
- LLM Pass 2 prompt 模板放 Skill markdown，不放 Python — 改 prompt 不需 re-deploy code
- 真 HB validation 失敗 → 第一檢查不是 code，是 prompt（spec §2.3 Step 4 五項是否 LLM 真有跑齊）

---

**核心斷言：** Phase 2 三條路徑收口時，propose-links 從「空殼 dry-run」升級為「能對真 whiteboard 跑出帶 rationale 的 link suggestion + 5 類圖論診斷 + 持久化到 registry + opt-in 寫回 HB suggestion card」。仍不真拉線、不 auto-accept、不打外部 LLM API。Phase 3+ 才碰 HB write-back 與自動化。
