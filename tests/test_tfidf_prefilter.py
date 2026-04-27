import json
from pathlib import Path

import pytest

from scripts.propose_links.tfidf_prefilter import (
    EMPTY_DUMMY_TOKEN,
    TOP_PAIRS_HARD_CAP,
    _card_to_doc,
    assert_cjk_gate,
    build_tfidf_prefilter,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mock_whiteboard_en_zh.json"


def _all_cards() -> list[dict]:
    with FIXTURE.open(encoding="utf-8") as f:
        data = json.load(f)
    main_wb = data["whiteboards"][0]
    return [
        o for o in main_wb["objects"]
        if o["type"] in {"card", "pdfCard", "mediaCard", "highlightElement"}
    ]


def _en_only() -> list[dict]:
    return [c for c in _all_cards() if c["id"].startswith("card-en-")]


def _zh_only() -> list[dict]:
    return [c for c in _all_cards() if c["id"].startswith("card-zh-")]


# ---------- _card_to_doc ----------


def test_card_to_doc_combines_title_tags_content():
    card = {
        "title": "Hello",
        "tags": ["a", "b"],
        "content": "world",
    }
    doc = _card_to_doc(card)
    assert "Hello" in doc and "a" in doc and "b" in doc and "world" in doc


def test_card_to_doc_truncates_content():
    long = "x" * 1000
    doc = _card_to_doc({"title": "T", "tags": [], "content": long})
    assert "x" * 500 in doc and "x" * 501 not in doc


def test_card_to_doc_empty_card_returns_dummy():
    assert _card_to_doc({"title": "", "tags": [], "content": ""}) == EMPTY_DUMMY_TOKEN


def test_card_to_doc_handles_missing_fields():
    assert _card_to_doc({}) == EMPTY_DUMMY_TOKEN


def test_card_to_doc_handles_non_list_tags():
    doc = _card_to_doc({"title": "T", "tags": "single-string", "content": ""})
    assert "single-string" in doc


# ---------- build_tfidf_prefilter shape + edges ----------


def test_returns_empty_for_under_2_cards():
    pairs, diag = build_tfidf_prefilter([])
    assert pairs == []
    assert diag["card_count"] == 0
    assert diag["pair_count_total"] == 0


def test_returns_empty_for_single_card():
    pairs, diag = build_tfidf_prefilter([{"title": "T", "content": "x"}])
    assert pairs == []
    assert diag["card_count"] == 1


def test_pair_count_matches_n_choose_2():
    cards = _en_only()  # 5 EN cards → C(5,2) = 10 pairs
    pairs, diag = build_tfidf_prefilter(cards)
    assert diag["pair_count_total"] == 10
    assert len(pairs) <= TOP_PAIRS_HARD_CAP


def test_top_n_cap_enforced():
    # 11 cards → C(11,2) = 55 pairs; should cap at top_n
    cards = _all_cards()
    pairs, diag = build_tfidf_prefilter(cards, top_n=5)
    assert len(pairs) == 5
    # Ensure desc ordering
    scores = [p[2] for p in pairs]
    assert scores == sorted(scores, reverse=True)


def test_diagnostics_records_tokenizer_and_ngram():
    pairs, diag = build_tfidf_prefilter(_en_only())
    assert diag["tokenizer"] == "char_wb"
    assert diag["ngram_range"] == (2, 3)
    assert "vocab_size" in diag


def test_empty_content_vs_dummy_token_distinction():
    cards = _all_cards()  # contains card-en-5-isolated, card-zh-5-isolated (both have title but empty content) + pdf-1 (no content field)
    pairs, diag = build_tfidf_prefilter(cards)
    # Both isolated cards have empty content, plus pdf-1 has no content field
    assert diag["empty_content_count"] >= 3
    # But none of them are FULLY empty (titles + tags carry signal)
    # so dummy substitution didn't fire on the fixture data
    assert diag["dummy_token_count"] == 0


def test_dummy_token_fires_only_when_truly_empty():
    cards = [
        {"title": "Has Title", "tags": [], "content": ""},
        {"title": "", "tags": [], "content": ""},
        {"title": "Other", "tags": [], "content": "x"},
    ]
    _, diag = build_tfidf_prefilter(cards)
    assert diag["empty_content_count"] == 2
    assert diag["dummy_token_count"] == 1  # only the fully-empty one


# ---------- CJK gate — the critical Phase 1 acceptance criterion ----------


def test_en_only_has_score_gradient():
    pairs, diag = build_tfidf_prefilter(_en_only())
    spread = diag["top10_score_spread"]
    # 5 cards = 10 pairs, fits exactly in top-10
    assert spread > 0.05, (
        f"EN top-10 spread {spread} too narrow; check tokenizer. "
        f"Distribution: {diag['top10_score_distribution']}"
    )


def test_zh_only_has_score_gradient_critical_cjk_gate():
    """The make-or-break test for char_wb on CJK content. If this fails,
    the prefilter is unfit for Chinese whiteboards and Phase 2 LLM
    pre-funnel cannot proceed."""
    pairs, diag = build_tfidf_prefilter(_zh_only())
    spread = diag["top10_score_spread"]
    assert spread > 0.05, (
        f"CJK GATE FAIL: ZH top-10 spread {spread} too narrow; "
        f"char_wb tokenizer likely mis-applied. Distribution: "
        f"{diag['top10_score_distribution']}"
    )


def test_mixed_en_zh_does_not_crash():
    cards = _all_cards()
    pairs, diag = build_tfidf_prefilter(cards)
    assert len(pairs) > 0
    assert diag["vocab_size"] > 0


def test_obvious_zh_pair_ranks_high():
    """card-zh-1 and card-zh-2 are designed near-duplicates. They
    should appear in the top-3 pair list of the ZH-only set."""
    cards = _zh_only()
    pairs, diag = build_tfidf_prefilter(cards)
    top3_idx_pairs = {(i, j) for i, j, _ in pairs[:3]}
    # Find indices of card-zh-1 and card-zh-2 in the input
    zh1_idx = next(i for i, c in enumerate(cards) if c["id"] == "card-zh-1")
    zh2_idx = next(i for i, c in enumerate(cards) if c["id"] == "card-zh-2")
    designed_pair = (min(zh1_idx, zh2_idx), max(zh1_idx, zh2_idx))
    assert designed_pair in top3_idx_pairs, (
        f"designed near-duplicate pair {designed_pair} not in top-3: {pairs[:3]}"
    )


def test_obvious_en_pair_ranks_high():
    """card-en-1 (Feedback Loop Theory) and card-en-2 (Retrospectives
    as Feedback) share lots of feedback-loop vocabulary and should
    rank in the top-3 of EN-only."""
    cards = _en_only()
    pairs, diag = build_tfidf_prefilter(cards)
    top3_idx_pairs = {(i, j) for i, j, _ in pairs[:3]}
    en1_idx = next(i for i, c in enumerate(cards) if c["id"] == "card-en-1")
    en2_idx = next(i for i, c in enumerate(cards) if c["id"] == "card-en-2")
    designed_pair = (min(en1_idx, en2_idx), max(en1_idx, en2_idx))
    assert designed_pair in top3_idx_pairs


# ---------- assert_cjk_gate function ----------


def test_assert_cjk_gate_passes_with_real_zh_diagnostics():
    _, diag = build_tfidf_prefilter(_zh_only())
    assert_cjk_gate(diag)  # must not raise


def test_assert_cjk_gate_raises_on_too_narrow_spread():
    bad_diag = {
        "top10_score_distribution": [0.5, 0.51, 0.49, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        "top10_score_spread": 0.02,
    }
    with pytest.raises(RuntimeError, match="CJK gate FAIL"):
        assert_cjk_gate(bad_diag)


def test_assert_cjk_gate_skips_when_too_few_pairs():
    diag = {"top10_score_distribution": [0.5, 0.5], "top10_score_spread": 0.0}
    # fewer than 10 pairs → caller's responsibility, gate does not fire
    assert_cjk_gate(diag)
