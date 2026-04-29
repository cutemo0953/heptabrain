"""Phase 2C — render the 🗂️ suggestion card markdown body.

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §4.5 and
IMPLEMENTATION_PLAN_PHASE_2.md §4.2.

Pure function: produces the card body string. The skill
(.claude/commands/propose-links.md) is responsible for actually
calling ``mcp__heptabase-mcp__save_to_note_card`` with this body —
this module never touches MCP.

Title MUST start with 🗂️ (spec §4.5 governance: makes AI-produced
cards visually identifiable in the HB UI). Footer MUST include
"移除本卡不影響 whiteboard" (zero lock-in promise).

Card content is informational only:
- Eligible NEW links (high/med confidence, has rationale, has
  relation_type) as a checklist
- Top gap signals as bullet callouts
- Stable footer with skill version + ISO timestamp + run hash

Confidence='low' pairs are EXCLUDED from the card body even though
they appear in the dry-run markdown — the card is meant to drive
user action, and "low" pairs are unreliable.
"""
from __future__ import annotations

from typing import Any

CARD_FOOTER_DISCLAIMER = (
    "（由 /heptabrain-propose-links 於 {timestamp} 自動產出，"
    "非 canonical 內容，僅供參考。移除本卡不影響 whiteboard 結構。）"
)

LINK_ELIGIBLE_CONFIDENCE: frozenset[str] = frozenset({"high", "med"})


def _eligible_for_card(pair: dict[str, Any]) -> bool:
    if pair.get("status") != "NEW":
        return False
    if pair.get("pass2_skipped") or pair.get("pass2_missing"):
        return False
    if pair.get("confidence") not in LINK_ELIGIBLE_CONFIDENCE:
        return False
    if not pair.get("relation_type"):
        return False
    return True


def _format_card_label(card: dict[str, Any]) -> str:
    """Inline-table-safe; same convention as output.py rendering."""
    title = (card.get("title") or "(untitled)").replace("|", "\\|")
    cid = card.get("id", "?")
    return f"`{cid}` — {title}"


def render_suggestion_card(
    *,
    whiteboard_name: str,
    whiteboard_id: str,
    enriched_pairs: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    gap_signals_report: dict[str, Any] | None,
    timestamp: str,
    today: str,
) -> str:
    """Build the suggestion-card body string.

    Required args (all keyword-only) so callers can't accidentally swap
    whiteboard_name / id positionally. ``timestamp`` is the full ISO
    string for the disclaimer footer; ``today`` is the YYYY-MM-DD
    used in the title.
    """
    lines: list[str] = []
    lines.append(f"# 🗂️ {whiteboard_name} 組織建議 — {today}")
    lines.append("")
    lines.append(CARD_FOOTER_DISCLAIMER.format(timestamp=timestamp))
    lines.append("")

    # ---- Section: 建議 New Links ----
    eligible = [p for p in enriched_pairs if _eligible_for_card(p)]
    # Sort by confidence (high first) then score (TF-IDF similarity)
    conf_rank = {"high": 0, "med": 1}
    eligible.sort(
        key=lambda p: (conf_rank.get(p.get("confidence", ""), 9),
                       -float(p.get("score", 0))),
    )

    lines.append(f"## 建議 New Links ({len(eligible)})")
    lines.append("")
    if not eligible:
        lines.append("_(無符合條件的高信心度建議連結)_")
        lines.append("")
    else:
        for p in eligible:
            i, j = p["i"], p["j"]
            if i >= len(cards) or j >= len(cards):
                continue  # snapshot drift defense
            a_label = _format_card_label(cards[i])
            b_label = _format_card_label(cards[j])
            rel = p.get("relation_type", "?")
            conf = p.get("confidence", "?")
            review = " ⚠️" if p.get("needs_review") else ""
            lines.append(
                f"- [ ] {a_label} → {b_label}: `{rel}`{review} — **{conf}**"
            )
            rationale = (p.get("rationale") or "").strip()
            if rationale:
                # Indent under the bullet; collapse newlines so HB renders
                # one flowing block per item.
                cleaned = rationale.replace("\n", " ")
                lines.append(f"  - Rationale: {cleaned}")
        lines.append("")

    # ---- Section: Gap Signals (top callouts) ----
    if gap_signals_report:
        weak = gap_signals_report.get("weak_integration") or []
        hub = gap_signals_report.get("central_hub") or []
        fragile = gap_signals_report.get("fragile_bridge") or []
        merge = gap_signals_report.get("merge_candidate") or []
        spag = gap_signals_report.get("spaghetti") or []
        if any((weak, hub, fragile, merge, spag)):
            lines.append("## Gap Signals")
            lines.append("")
            if weak:
                lines.append(
                    f"- **Weak integration ({len(weak)})**: "
                    + ", ".join(f"`{c}`" for c in weak[:5])
                    + (" …" if len(weak) > 5 else "")
                )
            if hub:
                lines.append(
                    "- **Central hub**: "
                    + ", ".join(f"`{c}`" for c in hub)
                )
            if fragile:
                lines.append(
                    f"- **Fragile bridge ({len(fragile)})**: "
                    + ", ".join(
                        f"`{a}` ↔ `{b}`" for a, b in fragile[:3]
                    )
                    + (" …" if len(fragile) > 3 else "")
                )
            if merge:
                lines.append(f"- **Merge candidate ({len(merge)})**:")
                for m in merge[:3]:
                    lines.append(
                        f"  - `{m['from_id']}` ⇄ `{m['to_id']}` "
                        f"(overlap {m['overlap']:.2f})"
                    )
                if len(merge) > 3:
                    lines.append(f"  - … 還有 {len(merge) - 3} 筆")
            if spag:
                lines.append(f"- **Spaghetti warning ({len(spag)})**:")
                for s in spag[:3]:
                    lines.append(
                        f"  - `{s['card_id']}` (degree {s['degree']})"
                    )
                if len(spag) > 3:
                    lines.append(f"  - … 還有 {len(spag) - 3} 筆")
            lines.append("")

    # ---- Section: re-run checklist (spec §4.5) ----
    lines.append("## 下次 re-run 前 checklist")
    lines.append("")
    lines.append("- [ ] 已決定哪些 links 要拉")
    lines.append("- [ ] 已決定哪些 cards 要圈 section")
    lines.append("- [ ] 可以刪除本卡，或讓其自然過期（建議 14 天）")
    lines.append("")

    # ---- Footer metadata (spec §4.5: created_at + skill version + wb id) ----
    lines.append("---")
    lines.append("")
    lines.append(
        f"<sub>created_at: `{timestamp}` · "
        f"whiteboard_id: `{whiteboard_id}` · "
        f"skill: `propose-links` (Phase 2C)</sub>"
    )
    return "\n".join(lines) + "\n"
