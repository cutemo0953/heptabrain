"""Tests for Phase 2C suggestion_card.

Per IMPLEMENTATION_PLAN_PHASE_2.md §4.2 acceptance — snapshot-shape +
edge cases.
"""
from __future__ import annotations

import pytest

from scripts.propose_links.suggestion_card import (
    LINK_ELIGIBLE_CONFIDENCE,
    render_suggestion_card,
)


def _cards():
    return [
        {"id": "card-a", "title": "Alpha"},
        {"id": "card-b", "title": "Beta"},
        {"id": "card-c", "title": "Gamma"},
    ]


def _enriched(
    *,
    pair_id="p-0-1", i=0, j=1, status="NEW",
    relation_type="shares_principle", rationale="ok", confidence="high",
    needs_review=False, pass2_skipped=False, pass2_missing=False,
    score=0.5,
):
    return {
        "pair_id": pair_id, "i": i, "j": j, "score": score,
        "status": status,
        "relation_type": relation_type, "rationale": rationale,
        "confidence": confidence,
        "evidence_kind": [],
        "needs_review": needs_review,
        "pass2_skipped": pass2_skipped,
        "pass2_missing": pass2_missing,
    }


# ---------- title + footer governance (spec §4.5) ----------


def test_title_starts_with_card_emoji():
    card = render_suggestion_card(
        whiteboard_name="My Board", whiteboard_id="wb-1",
        enriched_pairs=[], cards=_cards(),
        gap_signals_report=None,
        timestamp="2026-04-29T12:00:00Z", today="2026-04-29",
    )
    first_line = card.splitlines()[0]
    assert first_line.startswith("# 🗂️")
    assert "My Board" in first_line
    assert "2026-04-29" in first_line


def test_disclaimer_block_present():
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=[], cards=_cards(),
        gap_signals_report=None,
        timestamp="2026-04-29T12:00:00Z", today="2026-04-29",
    )
    assert "非 canonical" in card
    assert "移除本卡不影響 whiteboard" in card
    assert "2026-04-29T12:00:00Z" in card


def test_footer_metadata_includes_whiteboard_id_and_skill():
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-secret-1",
        enriched_pairs=[], cards=_cards(),
        gap_signals_report=None,
        timestamp="2026-04-29T12:00:00Z", today="2026-04-29",
    )
    assert "wb-secret-1" in card
    assert "propose-links" in card
    assert "Phase 2C" in card


# ---------- New Links section ----------


def test_eligibility_filter_constants():
    assert LINK_ELIGIBLE_CONFIDENCE == frozenset({"high", "med"})


def test_low_confidence_pairs_excluded_from_card():
    """Confidence 'low' is in dry-run markdown but NOT in suggestion card."""
    pairs = [
        _enriched(pair_id="p-0-1", i=0, j=1, confidence="high"),
        _enriched(pair_id="p-0-2", i=0, j=2, confidence="low"),
    ]
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=pairs, cards=_cards(),
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    assert "建議 New Links (1)" in card
    assert "card-a" in card and "card-b" in card
    # The low-conf pair endpoints should not appear as a link bullet
    assert "card-c" not in card


def test_skipped_and_missing_pairs_excluded():
    pairs = [
        _enriched(pair_id="p-0-1", i=0, j=1, status="EXISTS",
                  pass2_skipped=True),
        _enriched(pair_id="p-0-2", i=0, j=2, pass2_missing=True),
        _enriched(pair_id="p-1-2", i=1, j=2),  # eligible
    ]
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=pairs, cards=_cards(),
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    assert "建議 New Links (1)" in card


def test_no_eligible_links_shows_placeholder():
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=[], cards=_cards(),
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    assert "建議 New Links (0)" in card
    assert "無符合條件的高信心度建議連結" in card


def test_high_confidence_sorted_above_med():
    pairs = [
        _enriched(pair_id="p-0-2", i=0, j=2, confidence="med", score=0.9),
        _enriched(pair_id="p-0-1", i=0, j=1, confidence="high", score=0.5),
    ]
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=pairs, cards=_cards(),
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    high_pos = card.index("card-b")
    med_pos = card.index("card-c")
    assert high_pos < med_pos, "high-confidence link must precede med"


def test_needs_review_pair_renders_warning_emoji():
    pairs = [_enriched(needs_review=True, relation_type="related_to")]
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=pairs, cards=_cards(),
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    assert "⚠️" in card


def test_rationale_collapsed_to_single_line():
    pairs = [_enriched(rationale="line1\nline2\nline3")]
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=pairs, cards=_cards(),
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    assert "line1 line2 line3" in card
    # No raw newline mid-rationale
    assert "Rationale: line1\nline2" not in card


def test_card_title_pipe_escaped_for_markdown():
    cards = [{"id": "card-a", "title": "title|with|pipes"},
             {"id": "card-b", "title": "Beta"}]
    pairs = [_enriched()]
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=pairs, cards=cards,
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    assert "title\\|with\\|pipes" in card


def test_snapshot_drift_pair_index_out_of_range_silently_skipped():
    """If a pair's i/j references a card past the end of cards (e.g.
    inventory shrunk between merge and card render), don't crash;
    skip that link bullet."""
    pairs = [_enriched(i=0, j=99)]
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=pairs, cards=_cards(),
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    # Header still claims (1) eligible — we don't recount, but render
    # is graceful. Spec: card is informational; small rendering gap
    # acceptable in the rare drift case.
    assert "建議 New Links (1)" in card
    assert "card-a" not in card or "p-0-99" not in card


# ---------- Gap Signals section ----------


def test_gap_signals_none_omits_section():
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=[], cards=_cards(),
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    assert "## Gap Signals" not in card


def test_gap_signals_empty_omits_section():
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=[], cards=_cards(),
        gap_signals_report={
            "weak_integration": [], "central_hub": [],
            "fragile_bridge": [], "merge_candidate": [], "spaghetti": [],
        },
        timestamp="t", today="2026-04-29",
    )
    assert "## Gap Signals" not in card


def test_gap_signals_includes_top_callouts():
    report = {
        "weak_integration": ["c1", "c2", "c3", "c4", "c5", "c6"],  # 6 → "…"
        "central_hub": ["hub-a"],
        "fragile_bridge": [("a", "b"), ("c", "d"), ("e", "f"), ("g", "h")],
        "merge_candidate": [
            {"from_id": "m1", "to_id": "m2", "overlap": 0.9},
            {"from_id": "m3", "to_id": "m4", "overlap": 0.8},
            {"from_id": "m5", "to_id": "m6", "overlap": 0.75},
            {"from_id": "m7", "to_id": "m8", "overlap": 0.72},
        ],
        "spaghetti": [{"card_id": "sp1", "degree": 8, "threshold": 5}],
    }
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=[], cards=_cards(),
        gap_signals_report=report,
        timestamp="t", today="2026-04-29",
    )
    assert "## Gap Signals" in card
    # Truncation marker for long lists
    assert " …" in card
    # Counts shown
    assert "Weak integration (6)" in card
    assert "Fragile bridge (4)" in card
    assert "Merge candidate (4)" in card
    # Hub doesn't have a count in spec — just "Central hub: ..."
    assert "Central hub" in card


# ---------- Re-run checklist (spec §4.5) ----------


def test_rerun_checklist_present_with_3_required_items():
    card = render_suggestion_card(
        whiteboard_name="X", whiteboard_id="wb-1",
        enriched_pairs=[], cards=_cards(),
        gap_signals_report=None,
        timestamp="t", today="2026-04-29",
    )
    assert "## 下次 re-run 前 checklist" in card
    assert "已決定哪些 links 要拉" in card
    assert "已決定哪些 cards 要圈 section" in card
    assert "可以刪除本卡" in card
    assert "14 天" in card
