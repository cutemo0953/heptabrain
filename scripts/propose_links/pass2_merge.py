"""Phase 2A — merge Pass 2 LLM analyses into TF-IDF/connection-diff pairs.

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §2.3 Step 4 and
IMPLEMENTATION_PLAN_PHASE_2.md §2A.3.

Input:
- classified pairs from `connection_diff.classify_pairs` —
  `(i, j, score, status)` tuples
- pass2 results — list of dicts keyed by pair_id (and additionally
  required fields from_id + to_id, used to detect snapshot drift)
- cards — inventory list, used to cross-check from_id/to_id against
  the actual pair endpoints (Codex review P1.1: index-only matching
  silently mis-attaches analyses if inventory order changes between
  --emit-pairs and --with-pass2 invocations)

Output:
- list of EnrichedPair dicts merging both, with `pair_id` recoverable
  from `(i, j)` via the same scheme used by `emit_pair_contexts`.

Skip rule (Codex P2.4 — forward-compatible whitelist): only status=='NEW'
pairs are eligible for enrichment. EXISTS / REDUNDANT / future CONFLICT
all flow through with `pass2_skipped=True`.

Pairs without a matching analysis get `pass2_missing=True` and confidence
is forced to 'low' so the writer/output stages can downgrade them.

Per-analysis validation (Codex P1.2):
- non-dict items → warn + ignore
- pair_id must match ``^p-\\d+-\\d+$`` → warn + ignore
- from_id / to_id required; if absent or not matching the classified
  pair's actual endpoints → warn + treat as missing (Codex P1.1)
- relation_type: 11 frozen relations or `related_to` (else fallback +
  needs_review)
- rationale: string only (else coerced to "")
- confidence: 'high' / 'med' / 'low' (else 'low')
- evidence_kind: list of strings (else [])
"""
from __future__ import annotations

import re
from typing import Any

from scripts.constants.relation_types import (
    FALLBACK_RELATION,
    RELATION_TYPES,
)

VALID_CONFIDENCE = frozenset({"high", "med", "low"})
_PAIR_ID_RE = re.compile(r"^p-\d+-\d+$")
_RATIONALE_MAX_CHARS = 1000  # render layer truncates further; hard cap on input


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


def _normalize_rationale(rat: Any) -> str:
    if not isinstance(rat, str):
        return ""
    rat = rat.strip()
    if len(rat) > _RATIONALE_MAX_CHARS:
        rat = rat[:_RATIONALE_MAX_CHARS]
    return rat


def _validate_analysis(
    r: Any, warnings: list[str]
) -> dict[str, Any] | None:
    """Per-analysis structural validation (Codex P1.2).

    Returns the dict (unchanged) on pass; appends to ``warnings`` and
    returns None on any structural failure. Field-level coercion happens
    later in the merge loop; this gate is for "is this even an analysis
    record" checks.
    """
    if not isinstance(r, dict):
        warnings.append(f"pass2 result is not a dict (got {type(r).__name__}): skipped")
        return None
    pid = r.get("pair_id")
    if not isinstance(pid, str):
        warnings.append(f"pass2 result missing pair_id: {r!r}")
        return None
    if not _PAIR_ID_RE.match(pid):
        warnings.append(
            f"pass2 result has malformed pair_id {pid!r} "
            f"(expected p-<i>-<j>): skipped"
        )
        return None
    return r


def merge_pass2(
    classified_pairs: list[tuple[int, int, float, str]],
    pass2_results: list[dict[str, Any]],
    cards: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Match classified pairs against pass2 analyses by pair_id +
    cross-check against from_id/to_id.

    Returns (enriched_pairs, warnings).
    Warning shape: human-readable strings; caller can log/print them.

    Duplicate pair_ids in pass2_results: keep the LAST occurrence and emit
    a warning. (LLM should not produce duplicates; if it does, last-wins
    matches str.dict semantics.)

    Endpoint cross-check (Codex P1.1): when ``cards`` is provided, each
    matched analysis must carry ``from_id`` and ``to_id`` AND those must
    equal ``cards[i]['id']`` / ``cards[j]['id']`` as an unordered pair.
    Mismatch → analysis is rejected (pair flagged ``pass2_missing``) and
    a warning surfaced; this is the snapshot-drift guard. When ``cards``
    is None (legacy / pure unit-test mode) the cross-check is skipped.
    """
    warnings: list[str] = []

    by_id: dict[str, dict[str, Any]] = {}
    for r in pass2_results:
        validated = _validate_analysis(r, warnings)
        if validated is None:
            continue
        pid = validated["pair_id"]  # already known str + matches regex
        if pid in by_id:
            warnings.append(f"duplicate pair_id in pass2 results: {pid} (last wins)")
        by_id[pid] = validated

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

        # Codex P2.4 — only NEW pairs are eligible for Pass 2 enrichment.
        # EXISTS / REDUNDANT / future CONFLICT all flow through skipped.
        if status != "NEW":
            base["pass2_skipped"] = True
            enriched.append(base)
            continue

        result = by_id.get(pid)
        if result is None:
            base["pass2_missing"] = True
            base["confidence"] = "low"
            enriched.append(base)
            continue

        # Codex P1.1 endpoint cross-check (only when cards provided).
        # Result MUST carry from_id + to_id; we compare as an unordered
        # pair against cards[i].id / cards[j].id. Mismatch ⇒ reject.
        if cards is not None:
            r_from = result.get("from_id")
            r_to = result.get("to_id")
            if not isinstance(r_from, str) or not isinstance(r_to, str):
                warnings.append(
                    f"pass2 result for {pid} is missing from_id/to_id "
                    f"(snapshot-drift guard): treated as missing"
                )
                base["pass2_missing"] = True
                base["confidence"] = "low"
                enriched.append(base)
                continue
            try:
                expected = frozenset({cards[i]["id"], cards[j]["id"]})
            except (IndexError, KeyError):
                # Index out of range or card lacks 'id': treat as snapshot
                # drift; the classified pair points at something that no
                # longer exists in the inventory we were handed.
                warnings.append(
                    f"pass2 result for {pid}: cards[{i}] or cards[{j}] "
                    f"has no 'id' (snapshot-drift): treated as missing"
                )
                base["pass2_missing"] = True
                base["confidence"] = "low"
                enriched.append(base)
                continue
            actual = frozenset({r_from, r_to})
            if actual != expected:
                warnings.append(
                    f"pass2 result for {pid} endpoints {sorted(actual)} "
                    f"don't match inventory pair {sorted(expected)} "
                    f"(snapshot-drift): treated as missing"
                )
                base["pass2_missing"] = True
                base["confidence"] = "low"
                enriched.append(base)
                continue

        rel, needs_review = _normalize_relation(result.get("relation_type"))
        base["relation_type"] = rel
        base["needs_review"] = needs_review
        base["rationale"] = _normalize_rationale(result.get("rationale"))
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
