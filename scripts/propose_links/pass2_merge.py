"""Phase 2A — merge Pass 2 LLM analyses into TF-IDF/connection-diff pairs.

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §2.3 Step 4 and
IMPLEMENTATION_PLAN_PHASE_2.md §2A.3.

Input:
- classified pairs from `connection_diff.classify_pairs` —
  `(i, j, score, status)` tuples
- pass2 results — list of dicts keyed by pair_id

Output:
- list of EnrichedPair dicts merging both, with `pair_id` recoverable
  from `(i, j)` via the same scheme used by `emit_pairs`.

Skip rule: EXISTS / REDUNDANT pairs are not sent to the LLM (no need to
analyze a connection that already exists), so they pass through with
`relation_type=None` and a `pass2_skipped` flag. NEW pairs without a
matching analysis get `pass2_missing=True` and confidence is forced to
'low' so the writer/output stages can downgrade them.

Validation: relation_type must be one of the 11 frozen relations
(constants.relation_types) OR the fallback `related_to`. Anything else
falls back to `related_to` + `needs_review=True` (spec §2.2).
"""
from __future__ import annotations

from typing import Any

from scripts.constants.relation_types import (
    FALLBACK_RELATION,
    RELATION_TYPES,
)

VALID_CONFIDENCE = frozenset({"high", "med", "low"})


def pair_id(i: int, j: int) -> str:
    """Stable pair id derived from card indices in the inventory order.

    The skill-side LLM is expected to use the same scheme (`p-{i}-{j}`
    with i < j) when producing its analyses fixture.
    """
    a, b = (i, j) if i < j else (j, i)
    return f"p-{a}-{b}"


def _normalize_relation(rel: Any) -> tuple[str, bool]:
    """Returns (relation_type, needs_review).

    Unknown / missing → fallback + needs_review=True.
    """
    if not isinstance(rel, str):
        return FALLBACK_RELATION, True
    if rel in RELATION_TYPES:
        return rel, False
    if rel == FALLBACK_RELATION:
        return rel, True
    return FALLBACK_RELATION, True


def _normalize_confidence(c: Any) -> str:
    if isinstance(c, str) and c in VALID_CONFIDENCE:
        return c
    return "low"


def merge_pass2(
    classified_pairs: list[tuple[int, int, float, str]],
    pass2_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Match classified pairs against pass2 analyses by pair_id.

    Returns (enriched_pairs, warnings).
    Warning shape: human-readable strings; caller can log/print them.

    Duplicate pair_ids in pass2_results: keep the LAST occurrence and emit
    a warning. (LLM should not produce duplicates; if it does, last-wins
    matches str.dict semantics.)
    """
    warnings: list[str] = []

    by_id: dict[str, dict[str, Any]] = {}
    for r in pass2_results:
        pid = r.get("pair_id")
        if not isinstance(pid, str):
            warnings.append(f"pass2 result missing pair_id: {r!r}")
            continue
        if pid in by_id:
            warnings.append(f"duplicate pair_id in pass2 results: {pid} (last wins)")
        by_id[pid] = r

    seen_pair_ids: set[str] = set()
    enriched: list[dict[str, Any]] = []
    for tup in classified_pairs:
        if len(tup) != 4:
            raise ValueError(f"expected 4-tuple (i, j, score, status); got {tup!r}")
        i, j, score, status = tup
        pid = pair_id(i, j)
        seen_pair_ids.add(pid)

        base = {
            "pair_id": pid,
            "i": i,
            "j": j,
            "score": float(score),
            "status": status,
            "relation_type": None,
            "rationale": None,
            "confidence": None,
            "evidence_kind": [],
            "needs_review": False,
            "pass2_skipped": False,
            "pass2_missing": False,
        }

        if status in ("EXISTS", "REDUNDANT"):
            base["pass2_skipped"] = True
            enriched.append(base)
            continue

        result = by_id.get(pid)
        if result is None:
            base["pass2_missing"] = True
            base["confidence"] = "low"
            enriched.append(base)
            continue

        rel, needs_review = _normalize_relation(result.get("relation_type"))
        base["relation_type"] = rel
        base["needs_review"] = needs_review
        base["rationale"] = result.get("rationale") or ""
        base["confidence"] = _normalize_confidence(result.get("confidence"))

        ek = result.get("evidence_kind", [])
        if isinstance(ek, list):
            base["evidence_kind"] = [str(x) for x in ek if isinstance(x, str)]
        else:
            base["evidence_kind"] = []

        enriched.append(base)

    # Surface analyses that don't match any pair (LLM hallucinated a pair_id)
    for pid in by_id.keys() - seen_pair_ids:
        warnings.append(f"pass2 result for unknown pair_id: {pid} (no matching pair)")

    return enriched, warnings


def emit_pair_contexts(
    classified_pairs: list[tuple[int, int, float, str]],
    cards: list[dict[str, Any]],
    *,
    excerpt_chars: int = 500,
) -> list[dict[str, Any]]:
    """Build the LLM input list — one entry per NEW pair.

    EXISTS / REDUNDANT pairs are not emitted (no LLM call needed).
    Returned shape matches what `.claude/commands/propose-links.md` will
    feed to Claude; Phase 1 inventory shape is required (id, title,
    tags, content).
    """
    out: list[dict[str, Any]] = []
    for tup in classified_pairs:
        if len(tup) != 4:
            raise ValueError(f"expected 4-tuple (i, j, score, status); got {tup!r}")
        i, j, score, status = tup
        if status != "NEW":
            continue
        a = cards[i]
        b = cards[j]
        out.append(
            {
                "pair_id": pair_id(i, j),
                "score": float(score),
                "from_id": a.get("id"),
                "to_id": b.get("id"),
                "from_title": a.get("title") or "",
                "to_title": b.get("title") or "",
                "from_tags": list(a.get("tags") or []),
                "to_tags": list(b.get("tags") or []),
                "from_excerpt": (a.get("content") or "")[:excerpt_chars],
                "to_excerpt": (b.get("content") or "")[:excerpt_chars],
            }
        )
    return out
