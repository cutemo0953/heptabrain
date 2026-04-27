"""Phase 1 dry-run markdown rendering.

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §4. Phase 1 limitation:
inventory + maturity + TF-IDF top-N candidate pairs only. NO LLM Pass 2
analysis, NO registry write, NO suggestion-card creation. The footer
makes those exclusions explicit so a future reader cannot mistake the
output for a Phase 2+ artifact.
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


def render_dryrun_markdown(
    inventory: dict[str, Any],
    maturity: tuple[str, str],
    pair_scores: list[tuple[int, int, float]],
    diagnostics: dict[str, Any],
) -> str:
    lines: list[str] = []
    name = inventory.get("whiteboard_name", "(unnamed)")
    wb_id = inventory.get("whiteboard_id", "(no-id)")
    cards = inventory.get("cards", [])
    skipped = inventory.get("skipped", {})
    existing = inventory.get("existing_connections", [])
    scale = inventory.get("scale_tier", "unknown")
    mat, mat_src = maturity

    lines.append(f"# Propose-Links Dry-Run — {name}")
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

        def _table_lines(section_pairs: list[tuple[int, int, float]], start_rank: int) -> list[str]:
            out = [
                "| Rank | Card A | Card B | Score |",
                "|------|--------|--------|-------|",
            ]
            for offset, (i, j, score) in enumerate(section_pairs):
                rank = start_rank + offset
                a = cards[i]
                b = cards[j]
                a_label = f"`{a.get('id', '?')}` — {a.get('title') or '(untitled)'}"
                b_label = f"`{b.get('id', '?')}` — {b.get('title') or '(untitled)'}"
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

    # Phase 1 boundary
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
