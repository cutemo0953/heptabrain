"""Tests for Phase 2A pass2_merge.

Per IMPLEMENTATION_PLAN_PHASE_2.md §2A.3 acceptance — 5 cases plus
emit_pair_contexts coverage.
"""
from __future__ import annotations

import pytest

from scripts.propose_links.pass2_merge import (
    emit_pair_contexts,
    merge_pass2,
    pair_id,
)


# ---------- pair_id ----------


def test_pair_id_orders_indices_low_high():
    assert pair_id(2, 5) == "p-2-5"
    assert pair_id(5, 2) == "p-2-5"


def test_pair_id_self_loop_still_produces_id():
    # Caller is responsible for excluding self-loops; function is total.
    assert pair_id(3, 3) == "p-3-3"


# ---------- merge_pass2 ----------


def _classified_three_new():
    return [
        (0, 1, 0.5, "NEW"),
        (1, 2, 0.4, "NEW"),
        (2, 3, 0.3, "NEW"),
    ]


def test_happy_path_three_new_with_three_results():
    classified = _classified_three_new()
    results = [
        {
            "pair_id": "p-0-1",
            "relation_type": "shares_principle",
            "rationale": "both invoke recursion",
            "confidence": "high",
            "evidence_kind": ["text_overlap"],
        },
        {
            "pair_id": "p-1-2",
            "relation_type": "extends",  # NOT in 11 set → fallback
            "rationale": "B extends A",
            "confidence": "med",
            "evidence_kind": [],
        },
        {
            "pair_id": "p-2-3",
            "relation_type": "supports",
            "rationale": "C supports D",
            "confidence": "low",
            "evidence_kind": ["shared_actor"],
        },
    ]
    enriched, warnings = merge_pass2(classified, results)
    assert warnings == []
    assert len(enriched) == 3

    e0 = enriched[0]
    assert e0["pair_id"] == "p-0-1"
    assert e0["relation_type"] == "shares_principle"
    assert e0["confidence"] == "high"
    assert e0["needs_review"] is False
    assert e0["evidence_kind"] == ["text_overlap"]
    assert e0["pass2_missing"] is False
    assert e0["pass2_skipped"] is False

    # extends is not in the 11-set → fallback + needs_review
    e1 = enriched[1]
    assert e1["relation_type"] == "related_to"
    assert e1["needs_review"] is True

    # confidence='low' is valid (not coerced)
    e2 = enriched[2]
    assert e2["confidence"] == "low"
    assert e2["relation_type"] == "supports"


def test_unknown_relation_type_falls_back_and_flags_review():
    classified = [(0, 1, 0.5, "NEW")]
    results = [
        {
            "pair_id": "p-0-1",
            "relation_type": "vibes_with",  # invented
            "rationale": "no good reason",
            "confidence": "med",
        }
    ]
    enriched, warnings = merge_pass2(classified, results)
    assert enriched[0]["relation_type"] == "related_to"
    assert enriched[0]["needs_review"] is True
    assert warnings == []


def test_missing_result_for_some_pair_flags_pass2_missing_and_downgrades():
    classified = _classified_three_new()
    results = [
        {
            "pair_id": "p-0-1",
            "relation_type": "supports",
            "rationale": "x",
            "confidence": "high",
        },
    ]
    enriched, _ = merge_pass2(classified, results)
    assert enriched[0]["pass2_missing"] is False
    assert enriched[0]["confidence"] == "high"
    assert enriched[1]["pass2_missing"] is True
    assert enriched[1]["confidence"] == "low"
    assert enriched[1]["relation_type"] is None
    assert enriched[2]["pass2_missing"] is True


def test_duplicate_pair_id_keeps_last_and_warns():
    classified = [(0, 1, 0.5, "NEW")]
    results = [
        {
            "pair_id": "p-0-1",
            "relation_type": "supports",
            "rationale": "first",
            "confidence": "high",
        },
        {
            "pair_id": "p-0-1",
            "relation_type": "contradicts",
            "rationale": "second wins",
            "confidence": "med",
        },
    ]
    enriched, warnings = merge_pass2(classified, results)
    assert enriched[0]["relation_type"] == "contradicts"
    assert enriched[0]["rationale"] == "second wins"
    assert any("duplicate pair_id" in w for w in warnings)


def test_exists_and_redundant_pairs_skip_pass2():
    classified = [
        (0, 1, 0.5, "NEW"),
        (1, 2, 0.4, "EXISTS"),
        (2, 3, 0.3, "REDUNDANT"),
    ]
    results = [
        {
            "pair_id": "p-0-1",
            "relation_type": "supports",
            "rationale": "x",
            "confidence": "high",
        },
        # No analyses for the EXISTS / REDUNDANT pairs
    ]
    enriched, warnings = merge_pass2(classified, results)
    assert warnings == []
    assert enriched[0]["pass2_skipped"] is False
    assert enriched[1]["pass2_skipped"] is True
    assert enriched[2]["pass2_skipped"] is True
    # Skipped pairs should not be flagged as missing
    assert enriched[1]["pass2_missing"] is False
    assert enriched[2]["pass2_missing"] is False
    # And they should carry no relation_type
    assert enriched[1]["relation_type"] is None
    assert enriched[2]["relation_type"] is None


# ---------- secondary safety ----------


def test_invalid_confidence_falls_back_to_low():
    classified = [(0, 1, 0.5, "NEW")]
    results = [
        {
            "pair_id": "p-0-1",
            "relation_type": "supports",
            "rationale": "x",
            "confidence": "extremely-high",  # invalid
        }
    ]
    enriched, _ = merge_pass2(classified, results)
    assert enriched[0]["confidence"] == "low"


def test_pass2_result_for_unknown_pair_id_warns():
    classified = [(0, 1, 0.5, "NEW")]
    results = [
        {
            "pair_id": "p-0-1",
            "relation_type": "supports",
            "rationale": "x",
            "confidence": "high",
        },
        {
            "pair_id": "p-99-100",  # no matching pair in classified
            "relation_type": "supports",
            "rationale": "ghost",
            "confidence": "high",
        },
    ]
    _, warnings = merge_pass2(classified, results)
    assert any("p-99-100" in w for w in warnings)


def test_missing_pair_id_in_result_warns():
    classified = [(0, 1, 0.5, "NEW")]
    results = [
        {
            # no pair_id
            "relation_type": "supports",
            "rationale": "x",
            "confidence": "high",
        }
    ]
    _, warnings = merge_pass2(classified, results)
    assert any("missing pair_id" in w for w in warnings)


def test_classified_must_be_4_tuple():
    with pytest.raises(ValueError):
        merge_pass2([(0, 1, 0.5)], [])  # type: ignore[arg-type]


def test_evidence_kind_non_list_falls_back_to_empty():
    classified = [(0, 1, 0.5, "NEW")]
    results = [
        {
            "pair_id": "p-0-1",
            "relation_type": "supports",
            "rationale": "x",
            "confidence": "high",
            "evidence_kind": "text_overlap",  # str, not list
        }
    ]
    enriched, _ = merge_pass2(classified, results)
    assert enriched[0]["evidence_kind"] == []


# ---------- emit_pair_contexts ----------


def _cards4():
    return [
        {"id": "c1", "title": "Title A", "tags": ["t1"], "content": "alpha " * 200},
        {"id": "c2", "title": "Title B", "tags": ["t2"], "content": "bravo"},
        {"id": "c3", "title": "Title C", "tags": [], "content": ""},
        {"id": "c4", "title": "Title D", "tags": ["t4"], "content": "delta"},
    ]


def test_emit_only_new_pairs():
    classified = [
        (0, 1, 0.7, "NEW"),
        (1, 2, 0.6, "EXISTS"),
        (2, 3, 0.4, "REDUNDANT"),
        (0, 3, 0.3, "NEW"),
    ]
    out = emit_pair_contexts(classified, _cards4())
    assert len(out) == 2
    assert {p["pair_id"] for p in out} == {"p-0-1", "p-0-3"}


def test_emit_truncates_excerpt_to_500_chars():
    cards = _cards4()
    classified = [(0, 1, 0.5, "NEW")]
    out = emit_pair_contexts(classified, cards)
    assert len(out[0]["from_excerpt"]) == 500
    # 'bravo' is short — preserved as-is
    assert out[0]["to_excerpt"] == "bravo"


def test_emit_handles_missing_fields_gracefully():
    cards = [{"id": "c1"}, {"id": "c2"}]
    classified = [(0, 1, 0.5, "NEW")]
    out = emit_pair_contexts(classified, cards)
    assert out[0]["from_title"] == ""
    assert out[0]["from_tags"] == []
    assert out[0]["from_excerpt"] == ""


def test_emit_rejects_3_tuple_without_status():
    with pytest.raises(ValueError):
        emit_pair_contexts([(0, 1, 0.5)], _cards4())  # type: ignore[arg-type]


def test_emit_custom_excerpt_chars():
    cards = [
        {"id": "c1", "title": "A", "content": "x" * 1000},
        {"id": "c2", "title": "B", "content": "y" * 50},
    ]
    classified = [(0, 1, 0.5, "NEW")]
    out = emit_pair_contexts(classified, cards, excerpt_chars=100)
    assert len(out[0]["from_excerpt"]) == 100
    assert out[0]["to_excerpt"] == "y" * 50
