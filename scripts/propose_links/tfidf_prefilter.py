"""TF-IDF Pass 1 prefilter — CJK-safe via char_wb (2,3)-gram.

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §2.3 v1.2.2. Reduces N*(N-1)/2
pair space to top-50 candidates that the (Phase 2) LLM Pass 2 will deeply
analyze. Never tokenizes by whitespace — that fails for CJK content
where a sentence is a single token.

Empty-text cards are not filtered out (we still want to know they exist
in diagnostics); they get a fixed dummy token so scikit-learn doesn't
raise empty-vocabulary errors (ChatGPT caveat 2).
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

EMPTY_DUMMY_TOKEN = "[EMPTY_CARD_NO_TEXT]"
TOP_PAIRS_HARD_CAP = 50  # spec §2.3 — funnel to LLM Pass 2 in Phase 2
CONTENT_PREFIX_CHARS = 500  # spec §2.3 — first 500 chars per card


def _card_to_doc(card: dict[str, Any]) -> str:
    title = (card.get("title") or "").strip()
    tags = card.get("tags") or []
    if isinstance(tags, list):
        tag_text = " ".join(str(t) for t in tags)
    else:
        tag_text = str(tags)
    content = (card.get("content") or "")[:CONTENT_PREFIX_CHARS]
    combined = " ".join(part for part in (title, tag_text, content) if part).strip()
    return combined or EMPTY_DUMMY_TOKEN


def _empty_content_count(cards: list[dict[str, Any]]) -> int:
    """Cards whose `content` field is missing or empty after strip.
    Title/tags may still carry signal; this is a pure quality metric."""
    return sum(1 for c in cards if not (c.get("content") or "").strip())


def build_tfidf_prefilter(
    cards: list[dict[str, Any]], top_n: int = TOP_PAIRS_HARD_CAP
) -> tuple[list[tuple[int, int, float]], dict[str, Any]]:
    n = len(cards)
    empty_content = _empty_content_count(cards)
    if n < 2:
        return [], {
            "tokenizer": "char_wb",
            "ngram_range": (2, 3),
            "card_count": n,
            "pair_count_total": 0,
            "pair_count_returned": 0,
            "top10_score_distribution": [],
            "top10_score_spread": 0.0,
            "empty_content_count": empty_content,
            "dummy_token_count": 0,
            "vocab_size": 0,
        }

    docs = [_card_to_doc(c) for c in cards]
    dummy_count = sum(1 for d in docs if d == EMPTY_DUMMY_TOKEN)

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3))
    matrix = vectorizer.fit_transform(docs)
    sim = cosine_similarity(matrix)

    # Upper triangle pair list, exclude diagonal
    pairs: list[tuple[int, int, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((i, j, float(sim[i, j])))

    pairs.sort(key=lambda p: p[2], reverse=True)
    returned = pairs[:top_n]

    top10_scores = [round(p[2], 4) for p in pairs[:10]]
    top10_spread = (
        round(max(top10_scores) - min(top10_scores), 4) if top10_scores else 0.0
    )

    diagnostics = {
        "tokenizer": "char_wb",
        "ngram_range": (2, 3),
        "card_count": n,
        "pair_count_total": len(pairs),
        "pair_count_returned": len(returned),
        "top10_score_distribution": top10_scores,
        "top10_score_spread": top10_spread,
        "empty_content_count": empty_content,
        "dummy_token_count": dummy_count,
        "vocab_size": len(vectorizer.vocabulary_),
    }
    return returned, diagnostics


def assert_cjk_gate(diagnostics: dict[str, Any], min_spread: float = 0.05) -> None:
    """Raise if top-10 pair scores cluster within ±min_spread (CJK
    tokenizer probably mis-set per spec §2.3 v1.2.2 implementation gate).
    """
    scores = diagnostics.get("top10_score_distribution", [])
    if len(scores) < 10:
        return  # too few pairs to evaluate gate; downstream caller handles
    spread = diagnostics.get("top10_score_spread", 0.0)
    if spread <= min_spread:
        raise RuntimeError(
            f"CJK gate FAIL: top-10 score spread {spread} ≤ {min_spread}; "
            f"char_wb tokenizer likely mis-applied. Scores: {scores}"
        )
