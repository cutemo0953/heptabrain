"""Phase 1 dry-run markdown rendering (with Phase 2A enrichment).

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §4. Phase 1 base: inventory +
maturity + TF-IDF top-N candidate pairs. Phase 2A adds optional
`enriched_pairs` parameter which carries LLM Pass 2 results
(relation_type / rationale / confidence) — when present, the candidate
table is replaced by the spec §4.1 attention-protected hierarchy
(⭐ Top 5 / 📌 Next 10 / 📎 Appendix). The Phase 1-boundary footer is
suppressed when Pass 2 is present so readers don't see contradictory
"no LLM Pass 2 happened" messaging on enriched output.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


def _slugify(name: str) -> str:
    out = []
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "whiteboard"


def dryrun_filename(
    whiteboard_name: str,
    today: datetime | None = None,
    *,
    output_dir: "Path | None" = None,
) -> str:
    """Build the dry-run filename with same-day re-run suffix per spec §4.1.

    If ``output_dir`` is given, scans for existing same-day files for this
    whiteboard and appends `_r2`, `_r3`, … to avoid overwriting prior output.
    Cross-day runs do not need a suffix — the date already disambiguates.

    Per Codex P1 #3 review 2026-04-27: matches are anchored via regex so
    a slug like `wb` does NOT collide with `wb-extra`. Race-condition
    note: this implementation reads-then-writes; concurrent CLI runs in
    the same second may both pick the same _rN. Acceptable for Phase 1
    single-user CLI; documented as P2 deferred.
    """
    today = today or datetime.now()
    date_str = f"{today:%Y-%m-%d}"
    slug = _slugify(whiteboard_name)
    base = f"{date_str}_{slug}"

    if output_dir is None or not output_dir.exists():
        return f"{base}_dryrun.md"

    pattern = re.compile(rf"^{re.escape(base)}(?:_r(\d+))?_dryrun\.md$")
    existing_ns: list[int] = []
    for p in output_dir.iterdir():
        if not p.is_file():
            continue
        m = pattern.match(p.name)
        if m is None:
            continue
        existing_ns.append(int(m.group(1)) if m.group(1) else 1)

    if not existing_ns:
        return f"{base}_dryrun.md"
    next_n = max(existing_ns) + 1
    return f"{base}_r{next_n}_dryrun.md"


_CONFIDENCE_ICON = {"high": "🟢", "med": "🟡", "low": "🔴"}


def _enriched_by_pair_id(
    enriched_pairs: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if not enriched_pairs:
        return {}
    return {e["pair_id"]: e for e in enriched_pairs if "pair_id" in e}


def _render_gap_signals_section(
    report: dict[str, Any], lines: list[str]
) -> None:
    """Append spec §4.1 gap-signal section. No-op for empty/None report."""
    if not report:
        return
    lines.append("## Gap Signals")
    lines.append("")
    lines.append(
        f"_(union graph: {report.get('node_count', 0)} nodes, "
        f"{report.get('edge_count', 0)} edges)_"
    )
    lines.append("")

    weak = report.get("weak_integration") or []
    if weak:
        lines.append(
            f"🔹 **Weak integration ({len(weak)})**: "
            + ", ".join(f"`{c}`" for c in weak)
        )
        lines.append("  → 拉多 1-2 條連結或 rethink 位置")
        lines.append("")

    hub = report.get("central_hub") or []
    if hub:
        lines.append(
            f"🔹 **Central hub**: " + ", ".join(f"`{c}`" for c in hub)
        )
        lines.append("  → 建議放 whiteboard 物理中央")
        lines.append("")

    fragile = report.get("fragile_bridge") or []
    if fragile:
        lines.append(f"🔹 **Fragile bridge ({len(fragile)})**:")
        for edge in fragile:
            a, b = edge[0], edge[1]
            lines.append(f"  - `{a}` ↔ `{b}`")
        lines.append("  → 加 redundant bridge 提升 community 連通韌性")
        lines.append("")

    merge = report.get("merge_candidate") or []
    if merge:
        lines.append(f"🔹 **Merge candidate ({len(merge)})**:")
        for m in merge:
            shared = ", ".join(f"`{n}`" for n in m.get("shared_neighbors", [])) or "—"
            lines.append(
                f"  - `{m['from_id']}` ⇄ `{m['to_id']}` "
                f"(overlap {m['overlap']:.2f}; shared: {shared})"
            )
        lines.append("  → 在 HB GUI 考慮合併為一張卡片")
        lines.append("")

    spag = report.get("spaghetti") or []
    if spag:
        lines.append(f"🔹 **Spaghetti warning ({len(spag)})**:")
        for s in spag:
            lines.append(
                f"  - `{s['card_id']}` (degree {s['degree']}, "
                f"threshold {s['threshold']})"
            )
        lines.append("  → 抽象為高維原則另建卡，或拆為 2-3 張子卡")
        lines.append("")

    if not (weak or hub or fragile or merge or spag):
        lines.append("_(無偵測到 gap signal — whiteboard 結構健康)_")
        lines.append("")

    for w in report.get("warnings") or []:
        lines.append(f"⚠️ {w}")
    if report.get("warnings"):
        lines.append("")


def render_dryrun_markdown(
    inventory: dict[str, Any],
    maturity: tuple[str, str],
    pair_scores: list[tuple],  # tuple-3 (i, j, score) or tuple-4 (i, j, score, status)
    diagnostics: dict[str, Any],
    *,
    status_summary: dict[str, int] | None = None,
    enriched_pairs: list[dict[str, Any]] | None = None,
    gap_signals_report: dict[str, Any] | None = None,
    registry_written: bool = False,
    suggestion_card_written: bool = False,
) -> str:
    lines: list[str] = []
    name = inventory.get("whiteboard_name", "(unnamed)")
    wb_id = inventory.get("whiteboard_id", "(no-id)")
    cards = inventory.get("cards", [])
    skipped = inventory.get("skipped", {})
    existing = inventory.get("existing_connections", [])
    scale = inventory.get("scale_tier", "unknown")
    mat, mat_src = maturity

    # Phase 2.1: detect classified-pair shape (4-tuple with status)
    has_status = bool(pair_scores) and len(pair_scores[0]) >= 4
    enriched_lookup = _enriched_by_pair_id(enriched_pairs)
    has_pass2 = bool(enriched_lookup)

    title_suffix = " (Pass 2 enriched)" if has_pass2 else ""
    lines.append(f"# Propose-Links Dry-Run — {name}{title_suffix}")
    lines.append("")
    lines.append(f"- **Whiteboard ID:** `{wb_id}`")
    lines.append(f"- **Card count (analyzable):** {len(cards)}")
    lines.append(f"- **Scale tier:** `{scale}`")
    lines.append(f"- **Maturity:** `{mat}` (source: `{mat_src}`)")

    if skipped:
        skip_str = ", ".join(f"{k}={v}" for k, v in sorted(skipped.items()))
        lines.append(f"- **Skipped object types:** {skip_str}")
    else:
        lines.append("- **Skipped object types:** (none)")

    lines.append(f"- **Existing connections:** {len(existing)}")
    if status_summary:
        summary_parts = [f"{v} {k}" for k, v in status_summary.items() if v]
        if summary_parts:
            lines.append(f"- **Pair diff:** {' · '.join(summary_parts)}")
    lines.append("")

    # Existing connections
    lines.append("## Existing connections")
    lines.append("")
    if not existing:
        lines.append("_(none)_")
    else:
        for c in existing:
            label = c.get("label", "—")
            lines.append(f"- `{c['from']}` → `{c['to']}` (label: `{label}`)")
    lines.append("")

    # Card inventory
    lines.append("## Card inventory")
    lines.append("")
    if not cards:
        lines.append("_(no analyzable cards)_")
    else:
        for c in cards:
            title = c.get("title") or "(untitled)"
            ctype = c.get("type", "?")
            lines.append(f"- [{ctype}] `{c.get('id', '?')}` — {title}")
    lines.append("")

    # Top-N candidate pairs (spec §4.1 attention-protected hierarchy)
    # Phase 1 has TF-IDF score only; Phase 2 will add rationale + relation_type
    if not pair_scores:
        lines.append("## Candidate pairs (TF-IDF Pass 1 only)")
        lines.append("")
        lines.append("_(no pairs — fewer than 2 analyzable cards)_")
        lines.append("")
    else:
        top5 = pair_scores[:5]
        next10 = pair_scores[5:15]
        appendix = pair_scores[15:]

        def _pid(i: int, j: int) -> str:
            a, b = (i, j) if i < j else (j, i)
            return f"p-{a}-{b}"

        def _format_rationale(rat: str | None) -> str:
            if not rat:
                return ""
            # Inline-table-safe: collapse newlines + escape pipes
            cleaned = rat.replace("\n", " ").replace("|", "\\|").strip()
            if len(cleaned) > 160:
                cleaned = cleaned[:157] + "…"
            return cleaned

        def _table_lines(section_pairs: list[tuple], start_rank: int) -> list[str]:
            if has_pass2:
                out = [
                    "| Rank | Card A | Card B | Score | Status | Relation | Conf | Rationale |",
                    "|------|--------|--------|-------|--------|----------|------|-----------|",
                ]
            elif has_status:
                out = [
                    "| Rank | Card A | Card B | Score | Status |",
                    "|------|--------|--------|-------|--------|",
                ]
            else:
                out = [
                    "| Rank | Card A | Card B | Score |",
                    "|------|--------|--------|-------|",
                ]
            for offset, pair in enumerate(section_pairs):
                rank = start_rank + offset
                i, j, score = pair[0], pair[1], pair[2]
                a = cards[i]
                b = cards[j]
                a_label = f"`{a.get('id', '?')}` — {a.get('title') or '(untitled)'}"
                b_label = f"`{b.get('id', '?')}` — {b.get('title') or '(untitled)'}"
                if has_pass2:
                    status = pair[3] if has_status else "?"
                    e = enriched_lookup.get(_pid(i, j), {})
                    rel = e.get("relation_type") or "—"
                    if e.get("needs_review"):
                        rel = f"{rel} ⚠️"
                    if e.get("pass2_skipped"):
                        rel = "(skipped)"
                    elif e.get("pass2_missing"):
                        rel = "(missing)"
                    conf = e.get("confidence") or "—"
                    conf_disp = f"{_CONFIDENCE_ICON.get(conf, '·')} {conf}" if conf != "—" else "—"
                    rationale = _format_rationale(e.get("rationale"))
                    out.append(
                        f"| {rank} | {a_label} | {b_label} | {score:.4f} | `{status}` | "
                        f"`{rel}` | {conf_disp} | {rationale} |"
                    )
                elif has_status:
                    status = pair[3]
                    out.append(
                        f"| {rank} | {a_label} | {b_label} | {score:.4f} | `{status}` |"
                    )
                else:
                    out.append(f"| {rank} | {a_label} | {b_label} | {score:.4f} |")
            return out

        lines.append("## ⭐ Top 5 — must-review high-signal pairs")
        lines.append("")
        lines.extend(_table_lines(top5, start_rank=1))
        lines.append("")

        if next10:
            lines.append("## 📌 Next 10 — optional medium-signal pairs")
            lines.append("")
            lines.extend(_table_lines(next10, start_rank=6))
            lines.append("")

        if appendix:
            lines.append("## 📎 Appendix — remaining low-signal pairs")
            lines.append("")
            lines.append(f"<details><summary>{len(appendix)} more pairs</summary>")
            lines.append("")
            lines.extend(_table_lines(appendix, start_rank=16))
            lines.append("")
            lines.append("</details>")
            lines.append("")

    # Phase 2B: Gap signals (above Diagnostics so they read first)
    _render_gap_signals_section(gap_signals_report or {}, lines)

    # Diagnostics
    lines.append("## Diagnostics")
    lines.append("")
    for k in (
        "tokenizer",
        "ngram_range",
        "vocab_size",
        "card_count",
        "pair_count_total",
        "pair_count_returned",
        "top10_score_distribution",
        "top10_score_spread",
        "empty_content_count",
        "dummy_token_count",
    ):
        if k in diagnostics:
            lines.append(f"- `{k}`: `{diagnostics[k]}`")
    lines.append("")

    # Boundary footer (Codex P1.3 + Phase 2D real-validation fix):
    # accurately reflects what THIS run did. Each phase that ran appears
    # in the label; each phase that didn't run appears in the deferred
    # list. Registry/card paths are passed through from CLI so the
    # footer can't lie about durable side effects.
    has_signals = bool(gap_signals_report)
    ran_layers: list[str] = []
    deferred: list[str] = []
    if has_pass2:
        ran_layers.append("2A")
    else:
        deferred.append("- ❌ No LLM Pass 2 analysis (Phase 2A)")
    if has_signals:
        ran_layers.append("2B")
    else:
        deferred.append("- ❌ No gap-signal detection (Phase 2B)")
    if registry_written:
        ran_layers.append("2C-registry")
    else:
        deferred.append(
            "- ❌ No write to `_discovered_links.json` registry (Phase 2C)"
        )
    if suggestion_card_written:
        ran_layers.append("2C-card")
    else:
        deferred.append(
            "- ❌ No suggestion card body rendered (Phase 2C)"
        )

    if ran_layers:
        label = "Phase " + " + ".join(ran_layers)
        scope = (
            "registry written" if registry_written else "registry unchanged"
        )
        lines.append(f"## {label} boundary ({scope})")
        lines.append("")
        ran_summary_parts = []
        if has_pass2:
            ran_summary_parts.append("LLM Pass 2 merged into the candidate table")
        if has_signals:
            ran_summary_parts.append("gap signals computed via NetworkX")
        if registry_written:
            ran_summary_parts.append("eligible entries appended to `_discovered_links.json`")
        if suggestion_card_written:
            ran_summary_parts.append("🗂️ suggestion card body rendered")
        lines.append("This run: " + "; ".join(ran_summary_parts) + ".")
        if deferred:
            lines.append("")
            lines.append("The following layers intentionally did NOT happen:")
            lines.append("")
            lines.extend(deferred)
        lines.append("")
        lines.append(
            "See `docs/IMPLEMENTATION_PLAN_PHASE_2.md` §3 / §4 for the "
            "remaining layers."
        )
    else:
        lines.append("## Phase 1 boundary (do not mistake this for Phase 2+ output)")
        lines.append("")
        lines.append("This is a **Phase 1 dry-run**. The following intentionally did NOT happen:")
        lines.append("")
        lines.append("- ❌ No LLM Pass 2 analysis (no rationale, no relation_type, no confidence)")
        lines.append("- ❌ No write to `_discovered_links.json` registry")
        lines.append("- ❌ No suggestion card created in the Heptabase whiteboard")
        lines.append("- ❌ No clustering / Louvain communities")
        lines.append("- ❌ No gap-signal detection (weak / hub / fragile bridge / merge / spaghetti)")
        lines.append("")
        lines.append(
            "Phase 2+ enables those layers. See "
            "`docs/IMPLEMENTATION_PLAN_PHASE_0_1.md` §7 for deferred scope."
        )
    return "\n".join(lines) + "\n"
