"""Phase 2.1 — connection diff: classify proposed pairs against
existing whiteboard connections.

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §2.3 Step 5. Without LLM
Pass 2 we cannot yet detect CONFLICT (which requires comparing
relation_type), so Phase 2.1 emits three statuses:

  NEW       — AI proposed, whiteboard has no connection between this pair
  EXISTS    — whiteboard already has a connection between this pair
  REDUNDANT — same as EXISTS at this stage; reserved for future use when
              LLM Pass 2 also produces matching relation_type and we want
              to distinguish "verified" from "noise"

Phase 2.2 will introduce CONFLICT once relation_type is available.

Match policy: connections are treated as **undirected** for diff purposes
because TF-IDF Pass 1 produces undirected pairs (similarity is symmetric).
A whiteboard connection from A→B counts as the same pair as B→A.
"""
from __future__ import annotations

from typing import Any, Literal

PairStatus = Literal["NEW", "EXISTS", "REDUNDANT"]


def _frozen_pair(card_a_id: str, card_b_id: str) -> frozenset[str]:
    return frozenset({card_a_id, card_b_id})


def build_existing_pair_set(
    existing_connections: list[dict[str, Any]]
) -> set[frozenset[str]]:
    """Collapse directed connections into an undirected pair set."""
    pairs: set[frozenset[str]] = set()
    for c in existing_connections:
        from_id = c.get("from") or c.get("beginId")
        to_id = c.get("to") or c.get("endId")
        if from_id and to_id and from_id != to_id:
            pairs.add(_frozen_pair(from_id, to_id))
    return pairs


def classify_pairs(
    pair_scores: list[tuple[int, int, float]],
    cards: list[dict[str, Any]],
    existing_connections: list[dict[str, Any]],
) -> list[tuple[int, int, float, PairStatus]]:
    """For each (i, j, score) tuple, append a status by checking if
    cards[i].id ↔ cards[j].id is in the existing connection set."""
    existing = build_existing_pair_set(existing_connections)
    out: list[tuple[int, int, float, PairStatus]] = []
    for i, j, score in pair_scores:
        a_id = cards[i].get("id")
        b_id = cards[j].get("id")
        if a_id and b_id and _frozen_pair(a_id, b_id) in existing:
            status: PairStatus = "EXISTS"
        else:
            status = "NEW"
        out.append((i, j, score, status))
    return out


def diff_summary(
    classified: list[tuple[int, int, float, PairStatus]]
) -> dict[str, int]:
    counts = {"NEW": 0, "EXISTS": 0, "REDUNDANT": 0}
    for _, _, _, status in classified:
        counts[status] = counts.get(status, 0) + 1
    return counts
