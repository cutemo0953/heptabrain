# Cyberbrain v3.0.1 — Phase 0 + Phase 1 Implementation Plan

**Version:** v1.0
**Date:** 2026-04-25
**Author:** Architect (Claude Code)
**Authority:** Derived from ChatGPT + Gemini sign-off reviews of Cyberbrain v3.0.1 / Propose-Links v1.2.2
**Scope:** 只覆蓋 Phase 0（schema + constants）+ Phase 1（propose-links dry-run）
**Status:** Ready to implement — next session（clean context 建議）或 current session 續做皆可

---

## 0. 背景

Cyberbrain v3.0.1 + Propose-Links v1.2.2 已由 Gemini + ChatGPT 雙簽收。ChatGPT 明確規定分階段實作順序：

| Phase | Scope | 本文件覆蓋 |
|-------|-------|----------|
| 0 | schema + constants + validator | ✅ |
| 1 | propose-links dry-run | ✅ |
| 2 | markdown + registry write | （下一份 plan）|
| 3 | audit tools + stale + false-positive tracking | （下一份 plan）|
| 4 | Heptabase writes (suggestion cards, journal, meta-card sync) | （最後一份 plan）|

**硬規則（sign-off 條件）：**
1. Phase 1 **不可** 寫 registry entry
2. Phase 1 **不可** 建 suggestion cards
3. Phase 1 **不可** auto-accept
4. Implementation 必須先跑 fixture-based test set（ChatGPT caveat 2）
5. CJK Pass 1 prefilter 要過驗證 gate（v1.2.2 §2.3）

---

## 1. File Tree（Phase 0 + 1 結束後）

```
heptabrain/
├── pyproject.toml                         # NEW, Phase 0
├── scripts/
│   ├── __init__.py
│   ├── constants/
│   │   ├── __init__.py
│   │   └── relation_types.py              # Phase 0
│   ├── registry/
│   │   ├── __init__.py
│   │   ├── schema.py                      # Phase 0 — v2 validator
│   │   ├── lifecycle.py                   # Phase 0 — transition matrix
│   │   ├── migration.py                   # Phase 0 — legacy fallback + report
│   │   ├── atomic_write.py                # Phase 0 — Gemini caveat 1
│   │   └── whiteboard_maturity.py         # Phase 0 — read/write
│   ├── propose_links/
│   │   ├── __init__.py
│   │   ├── cli.py                         # Phase 1 — --dry-run only
│   │   ├── discovery.py                   # Phase 1
│   │   ├── inventory.py                   # Phase 1
│   │   ├── maturity_detect.py             # Phase 0/1 — precedence resolver
│   │   ├── tfidf_prefilter.py             # Phase 1 — CJK-safe
│   │   └── output.py                      # Phase 1 — markdown only, no registry
│   └── lib/
│       ├── __init__.py
│       └── mcp_client.py                  # Phase 1 — Heptabase MCP wrapper
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   └── mock_whiteboard_en_zh.json     # Phase 1 — ChatGPT fixture
│   ├── test_relation_types.py             # Phase 0
│   ├── test_registry_schema.py            # Phase 0
│   ├── test_lifecycle.py                  # Phase 0
│   ├── test_migration.py                  # Phase 0
│   ├── test_atomic_write.py               # Phase 0
│   ├── test_whiteboard_maturity.py        # Phase 0
│   └── test_tfidf_prefilter.py            # Phase 1 — CJK gate
├── registry-schemas/
│   ├── discovered_links.schema.json       # EXISTING, kept as v1 archive
│   ├── discovered_links.v2.schema.json    # NEW, Phase 0
│   ├── heptabrain_registry.schema.json    # EXISTING, v2.1 untouched
│   └── whiteboard_maturity.schema.json    # NEW, Phase 0
└── docs/
    ├── 01-cyberbrain-architecture.md      # sign-off, DO NOT EDIT
    ├── 02-heptabrain-sync.md              # sign-off, DO NOT EDIT
    ├── 03-zettel-walk.md                  # sign-off, DO NOT EDIT
    ├── 04-heptabrain-propose-links.md     # sign-off, DO NOT EDIT
    └── IMPLEMENTATION_PLAN_PHASE_0_1.md   # THIS DOC
```

**不該動：** `/Users/QmoMBA/.claude/commands/heptabrain-sync.md` 等 `.claude/commands/*.md` — 這些是現有的 skill 描述，Phase 1 還不到換綁的階段。

---

## 2. Phase 0 — Schema & Constants（6 modules + 6 tests）

### 2.1 `scripts/constants/relation_types.py`

```python
# 11 relation types — FROZEN per Cyberbrain v3 §2.2
# Mixed underscore/hyphen is intentional; do not normalize without ADR

RELATION_TYPES = (
    "supports", "contradicts", "derives_from", "applies_to",
    "example_of", "bridge_to", "tensions_with",
    "synergizes-with", "attracts", "precedes",
    "shares_principle",
)

FALLBACK_RELATION = "related_to"  # triggers needs_taxonomy_review

def is_valid_relation(r: str) -> bool: ...
```

**Acceptance：** 12-row test — 11 valid + 1 invalid string.

### 2.2 `scripts/registry/schema.py`

從 `01-cyberbrain-architecture.md §3.2` 實作 JSON schema validator（`jsonschema` lib）。

```python
def load_v2_schema() -> dict: ...  # 讀 registry-schemas/discovered_links.v2.schema.json
def validate_entry(entry: dict) -> list[str]:  # 回 error list，空 = valid
def is_v2_complete(entry: dict) -> bool:  # 判斷是否已填滿 v2 欄位（用於 migration report）
```

**v2 必填欄位清單：** link_class, acceptance_state, scope_type, source_mode, evidence_kind, last_verified_at, verified_by, implicit_connection_detected, auto_accept_reason, auto_accept_confidence, promoted_from.

**Acceptance：**
- 現有 `discovered_links.schema.json` v1 entry → `is_v2_complete() == False`, `validate_entry` 回空（v1 仍合法）
- 完整 v2 entry → `is_v2_complete() == True`, `validate_entry` 回空
- 壞 entry（missing link_id）→ `validate_entry` 回 non-empty

### 2.3 `scripts/registry/lifecycle.py`

Transition matrix per spec 04 §5.2.1 + promotion rule §5.2.2：

```python
# 3 classes × 3 states 合法轉換
VALID_TRANSITIONS = {
    ("proposed", "proposed"):     {"accepted", "rejected", "stale"},
    ("proposed", "accepted"):     {"canonical_accepted"},  # promotion
    ("exploratory", "proposed"):  {"accepted", "rejected"},
    ("exploratory", "accepted"):  {"canonical_accepted"},  # promotion
    ("canonical", "accepted"):    {"stale"},
    # ... spec §5.2.1 full matrix
}

def validate_transition(before, after) -> bool: ...
def promote_if_accepted(entry: dict) -> dict:
    """當 acceptance_state 轉 accepted 時：
    - 若 link_class in (proposed, exploratory) → 升為 canonical
    - 保留 promoted_from = 原 class
    """
```

**Acceptance：** 測每種合法轉換 + 3 種非法轉換 raise error。

### 2.4 `scripts/registry/migration.py`

```python
def fallback_legacy_entry(entry: dict) -> dict:
    """Per §3.3 migration rules — 補齊 v2 欄位（in-memory，不寫回）"""
    # link_class: discovered_by "manual" → canonical, else proposed
    # acceptance_state: 由 review_state 提升
    # scope_type: "propose-links" in discovered_by → whiteboard, else cross_whiteboard
    # ... full rules from §3.3

def generate_migration_report(registry_path: Path) -> str:
    """產 markdown report：多少 legacy、fallback 分布、ambiguity 案例。不寫回主檔。"""

def commit_lazy_writeback(registry_path: Path, backup_suffix: str) -> None:
    """審計後真正 write-back；先備份 _discovered_links.json.v2.1-backup-<ts>.json"""
```

**Acceptance：** fixture `examples/memory/_discovered_links_legacy.json`（若不存在則建 3 entries fixture）→ 報告列出所有 legacy，commit 後主檔含 v2 欄位，備份檔仍是原樣。

### 2.5 `scripts/registry/atomic_write.py`

Gemini caveat 1 直接對應：

```python
def atomic_write_json(path: Path, data) -> None:
    """
    1. Write to {path}.tmp
    2. json.dumps validate
    3. os.replace(tmp, path)  # POSIX atomic
    """
```

**Acceptance：** 在寫 tmp 後模擬 crash（raise 於 json.dumps 前）→ 原檔不變；成功 case → 原檔被覆蓋。

### 2.6 `scripts/registry/whiteboard_maturity.py`

Spec §3.5：

```python
Maturity = Literal["seed", "forming", "structured", "canonical"]
MaturitySource = Literal["manual", "heuristic", "meta_card", "title"]

def load_maturity_registry(path: Path) -> dict: ...

def get_maturity(wb_id: str, registry: dict) -> tuple[Maturity, MaturitySource] | None:
    """回 (maturity, source) 若找到；None 表示 registry 沒有，由 caller fallback"""

def set_maturity(wb_id: str, maturity: Maturity, source: MaturitySource,
                 note: str = "", registry_path: Path = ...) -> None:
    """atomic_write_json 寫回；last_maturity_reviewed_at = now"""
```

**Schema file：** `registry-schemas/whiteboard_maturity.schema.json`（對齊 §3.5 JSON example）。

**Acceptance：** 空 registry → get 回 None；set 後 get 回對應值；source 欄位 enum 限制。

---

## 3. Phase 1 — Propose-Links Dry-Run（6 modules + 1 test）

### 3.1 `scripts/lib/mcp_client.py`

```python
# 薄 wrapper，方便 unit test 時 mock

class HeptabaseMCPClient:
    def search_whiteboards(self, keyword: str) -> list[dict]: ...
    def get_whiteboard_with_objects(self, wb_id: str) -> dict: ...
    def get_object(self, object_id: str) -> dict: ...
```

**Acceptance：** Phase 1 dry-run 時可 inject `FakeHeptabaseMCPClient` 給 fixture 用。

### 3.2 `scripts/propose_links/discovery.py`

```python
def discover_whiteboard(keyword_or_id: str, client) -> dict:
    """
    若 keyword → search_whiteboards → 0 個 raise, 1 個 auto-pick, >1 個回 list 給 user 挑
    若 UUID → 直接 get_whiteboard_with_objects(id)
    回 {id, name, object_count}
    """
```

### 3.3 `scripts/propose_links/inventory.py`

```python
ANALYZABLE_TYPES = {"card", "pdfCard", "mediaCard", "highlightElement"}

def build_inventory(wb_id: str, client) -> dict:
    """
    1. get_whiteboard_with_objects(wb_id)
    2. 過濾 objects → 只留 ANALYZABLE_TYPES
    3. 抽取 existing_connections
    4. 決定 scale tier（N < 8 / 8-50 / > 50）
    回：
    {
        "whiteboard_id": ...,
        "whiteboard_name": ...,
        "cards": [...],        # list of card metadata
        "card_count": N,
        "skipped": {"pdf": ..., "section": ..., "image": ...},
        "existing_connections": [...],
        "scale_tier": "small_no_cluster" | "normal_funnel" | "hard_stop"
    }
    """
```

**Acceptance：** fixture `mock_whiteboard_en_zh.json` 8 cards → scale_tier = normal_funnel；51 cards fixture → hard_stop.

### 3.4 `scripts/propose_links/maturity_detect.py`

Spec §6 fallback precedence: registry → meta_card → title → density heuristic。

```python
def detect_maturity(wb_id: str, inventory: dict, registry_path: Path) -> tuple[Maturity, MaturitySource]:
    """
    1. 查 whiteboard_maturity.json registry
    2. 若缺 → 掃 inventory cards 找 ⚙️ Meta card（YAML block） — regex 粗篩 per Gemini caveat 4
    3. 若缺 → 查 whiteboard title 是否含 [maturity:X]
    4. 若缺 → 依 card_count 推 density heuristic
    """
```

**Gemini caveat 4：** Meta card YAML 用 regex `r"maturity:\s*([a-zA-Z_]+)"` 粗篩，不上 PyYAML 嚴格解析。失敗 fallback 到下一層 + log WARNING，絕不 crash。

**Acceptance：** fixture 4 種 case（registry hit / meta card / title / density）全驗 precedence 正確。

### 3.5 `scripts/propose_links/tfidf_prefilter.py`

Spec §2.3 v1.2.2 — CJK-safe：

```python
def build_tfidf_prefilter(cards: list[dict]) -> tuple[list[tuple[int, int, float]], dict]:
    """
    1. 對每 card: title + tags + first 500 chars → concat string
    2. ChatGPT caveat 2: 過濾空字串，空卡塞 "[EMPTY_CARD_NO_TEXT]" dummy
    3. TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3))
    4. cosine_similarity → 排序 → top 50 pair
    回: (pair_list_with_scores, diagnostics)
    diagnostics 含：
      - tokenizer 用的是 char_wb
      - N 張 card 產生 N*(N-1)/2 pair
      - 前 10 pair 的 score 分布（驗 CJK baseline 不全部趨近同值）
    """
```

**Acceptance（CJK validation gate per spec §2.3）：**
- 純英文 8 cards → top 10 pair score 非均勻（有明顯 gradient）
- 純中文 8 cards → 同上 — 若 score 全在 ±0.05 內則 FAIL，提示 char_wb 未套對
- 混合 8 cards → 不 crash，score 區分度可接受

### 3.6 `scripts/propose_links/output.py`

**Phase 1 限定：** 只輸出 `propose_links/YYYY-MM-DD_<slug>_dryrun.md`，**不建 suggestion card、不寫 registry**。

```python
def render_dryrun_markdown(inventory: dict, maturity: tuple, prefilter_result: tuple,
                           diagnostics: dict) -> str:
    """
    Sections:
    - Inventory summary
    - Maturity detection result + source
    - Top 50 candidate pairs（還沒跑 Pass 2 LLM，所以只有 TF-IDF score，rationale 留 TODO）
    - Skipped cards（pdf/section/image）
    - Tokenizer / similarity diagnostics（debugging 用）
    - 尾段明示 "Phase 1 dry-run — no registry write, no LLM pair analysis"
    """
```

### 3.7 `scripts/propose_links/cli.py`

```python
# Phase 1 的 CLI entry — 只實作 --dry-run flag

# Usage: python -m scripts.propose_links.cli <whiteboard> --dry-run

def main(args):
    """
    1. discovery → wb_id
    2. inventory → cards + scale_tier
    3. if scale_tier == "hard_stop": print 友善錯誤 + exit
    4. maturity_detect
    5. if maturity == "seed": print 拒絕 + exit
    6. if maturity == "canonical" and not --audit-only: print warning 詢問
    7. tfidf_prefilter
    8. render_dryrun_markdown → stdout + write to propose_links/
    9. 不做 Pass 2 LLM、不寫 registry、不建卡
    """
```

**Acceptance：** 真實 Heptabase whiteboard 跑過一次（小規模，5-15 cards），輸出檔讀得懂，CJK pair score 合理。

---

## 4. Phase 0+1 Test Fixture

`tests/fixtures/mock_whiteboard_en_zh.json` — 對齊 ChatGPT caveat 2：

- 10 mock cards（5 英文 + 5 中文）
- 2 組明顯 link pair（pre-marked）
- 1 contradiction
- 1 isolated card（degree 0）
- 1 pair duplicate candidate
- existing_connections 3 條

這個 fixture 同時給 Phase 0 test（maturity precedence fallback）+ Phase 1 test（inventory / prefilter）用。

---

## 5. Dependencies（pyproject.toml）

```toml
[project]
name = "heptabrain"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "jsonschema>=4.20",
    "scikit-learn>=1.4",
    "networkx>=3.2",          # Phase 2 用，但 Phase 0 test 也會 import
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=4.1"]
```

**不放：** jieba、MeCab、KoNLPy、langdetect — Gemini 建議 char_wb 取代，避免 dependency hell。若 Phase 1 CJK gate FAIL 再 revisit。

---

## 6. Implementation Order（建議 session 切分）

### Session A（Phase 0，約 3-4 小時）

1. pyproject.toml + 目錄結構
2. `relation_types.py` + test
3. `atomic_write.py` + test
4. `schema.py` + v2.schema.json + test
5. `lifecycle.py` + test
6. `migration.py` + test
7. `whiteboard_maturity.py` + schema + test
8. 全部 pytest green → commit `phase0: schema + constants + validators`

### Session B（Phase 1，約 4-6 小時）

1. `mcp_client.py` wrapper + FakeClient for test
2. `discovery.py`
3. `inventory.py` + fixture
4. `maturity_detect.py` + precedence tests
5. `tfidf_prefilter.py` + CJK gate test（關鍵 — 若 FAIL 回頭修 analyzer）
6. `output.py` dry-run markdown
7. `cli.py` 組起來
8. 真 HB whiteboard 實測 1 次 → 合理 → commit `phase1: propose-links dry-run`

**兩段之間的 sign-off：** Session A commit push 後跑一次 `/review-code HEAD~1` 或 `/codex:review`（code 改動大、跨 registry 治理層），確認沒 drift 再進 Session B。

---

## 7. Deferrals（Phase 2+ 才做，本 plan 不含）

- Pair Pass 2 LLM analysis（萃取 core principles / relation_type 決定 / rationale）
- Clustering via NetworkX Louvain + theme naming
- Gap signal 5 類判定
- MDA 4D sketch
- `_discovered_links.json` write
- Auto-accept detection
- Lazy write-back commit flow
- 🗂️ Suggestion card 建到 HB
- Journal append
- Meta card YAML sync
- Re-propose cooldown（rejected 90 天）
- False-positive rejection_reason tracking

---

## 8. Acceptance 總表

| 項目 | Pass 標準 |
|------|----------|
| Phase 0 tests | 全部 pytest green，coverage > 80% |
| Phase 0 schema validation | v1 entry 不報錯但不算 v2 complete；v2 entry 合法 |
| Phase 0 migration report | 3-entry legacy fixture 產出 markdown，不污染主檔 |
| Phase 0 atomic write | 模擬 crash 不破壞原檔 |
| Phase 1 CJK gate | 中文 fixture Pass 1 top 10 score 有 gradient（非均值 ±0.05 內）|
| Phase 1 real-HB test | 對 1 個真 whiteboard 跑 --dry-run 產出檔，人工讀得懂 |
| Phase 1 no side effects | 不寫 registry、不建卡、不改 HB（grep log 驗證）|

---

## 9. 不要做的事（sign-off 條件）

- ❌ 不要跳過 dry-run 直接寫 registry
- ❌ 不要啟用 suggestion card creation（--suggestion-card flag 在 Phase 1 cli 不實作）
- ❌ 不要跑 Pass 2 LLM（即使 user 要求也回「Phase 1 scope，不實作」）
- ❌ 不要改動 4 份 sign-off spec markdown
- ❌ 不要擴充 11 種 relation type
- ❌ Meta card YAML 不要上 PyYAML 嚴格 parse（用 regex 粗篩 + fallback）
- ❌ CLI 不要預設開 journal append

---

## 10. Session handoff 備忘

- 本 plan 為獨立文件；下個 session 只讀：(a) 本 plan, (b) 4 份 sign-off spec, (c) `memory/project_session_20260423_24.md`
- 不要再啟動另一輪 architecture review — spec 已 sign-off，現在是 implementation
- 實作遇到 NetworkX / MCP 邊角 issue 可單獨開 debug session
- 每 module 完成後跑該 module 的 pytest，不要累積再跑

---

**核心斷言：** Phase 0 + 1 合起來是一個乾淨的 minimum viable implementation — registry schema 就緒、能讀 whiteboard 跑出合理 candidate pair，但完全不觸碰 HB、不寫 registry。這給後續 Phase 2+ 留足空間，也給 user 第一個可見的 dry-run artifact。
