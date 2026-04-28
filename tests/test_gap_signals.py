"""Tests for Phase 2B gap_signals.

Per IMPLEMENTATION_PLAN_PHASE_2.md §3.1 acceptance — 6 cases plus
forward-compat / boundary coverage.
"""
from __future__ import annotations

import pytest

from scripts.propose_links import gap_signals
from scripts.propose_links.gap_signals import (
    FRAGILE_BRIDGE_MAX,
    MERGE_OVERLAP_THRESHOLD,
    WEAK_DEGREE_THRESHOLD,
    _spaghetti_threshold,
    compute_gap_signals,
    empty_report,
)


# ---------- spaghetti threshold helper ----------


def test_spaghetti_threshold_floors_at_5():
    assert _spaghetti_threshold(0) == 5
    assert _spaghetti_threshold(12) == 5  # 12//3=4, floor wins
    assert _spaghetti_threshold(15) == 5  # 15//3=5, equal
    assert _spaghetti_threshold(18) == 6  # 18//3=6 wins
    assert _spaghetti_threshold(60) == 20


# ---------- empty / degenerate graphs ----------


def test_empty_inputs_returns_empty_report():
    report = compute_gap_signals(cards=[], proposed_links=[], existing_connections=[])
    assert report["weak_integration"] == []
    assert report["central_hub"] == []
    assert report["fragile_bridge"] == []
    assert report["merge_candidate"] == []
    assert report["spaghetti"] == []
    assert report["node_count"] == 0
    assert report["edge_count"] == 0
    assert report["warnings"] == []


def test_isolated_nodes_only_all_weak():
    cards = [{"id": f"c{i}"} for i in range(4)]
    report = compute_gap_signals(cards=cards, proposed_links=[], existing_connections=[])
    assert sorted(report["weak_integration"]) == ["c0", "c1", "c2", "c3"]
    assert report["central_hub"] == []
    assert report["fragile_bridge"] == []
    assert report["edge_count"] == 0


def test_n_below_clustering_threshold_no_fragile_bridge():
    """N < 5: never compute Louvain, fragile_bridge always []."""
    cards = [{"id": f"c{i}"} for i in range(4)]
    proposed = [
        {"from_id": "c0", "to_id": "c1", "confidence": "med"},
        {"from_id": "c2", "to_id": "c3", "confidence": "med"},
    ]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    assert report["fragile_bridge"] == []


# ---------- weak / hub / spaghetti basic detection ----------


def test_weak_integration_excludes_well_connected_cards():
    cards = [{"id": f"c{i}"} for i in range(5)]
    # c0 connects to c1, c2, c3 (degree 3) — not weak
    # c1, c2, c3 each have degree 1 — all weak
    # c4 isolated — weak
    proposed = [
        {"from_id": "c0", "to_id": "c1", "confidence": "med"},
        {"from_id": "c0", "to_id": "c2", "confidence": "med"},
        {"from_id": "c0", "to_id": "c3", "confidence": "med"},
    ]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    assert "c0" not in report["weak_integration"]
    assert set(report["weak_integration"]) == {"c1", "c2", "c3", "c4"}


def test_central_hub_picks_top_3_betweenness():
    """Star graph: center has highest betweenness; leaves have 0."""
    cards = [{"id": f"c{i}"} for i in range(8)]
    # c0 is center; c1-c7 are leaves
    proposed = [
        {"from_id": "c0", "to_id": f"c{i}", "confidence": "med"}
        for i in range(1, 8)
    ]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    assert "c0" in report["central_hub"]
    # Leaves have betweenness=0, must NOT be picked even though they
    # would otherwise fill the top-3 quota
    for leaf in (f"c{i}" for i in range(1, 8)):
        assert leaf not in report["central_hub"]


def test_central_hub_empty_when_no_edges():
    cards = [{"id": f"c{i}"} for i in range(8)]
    report = compute_gap_signals(cards=cards, proposed_links=[], existing_connections=[])
    assert report["central_hub"] == []


def test_spaghetti_warning_uses_max_5_n_third():
    """N=20 → threshold = max(5, 20//3=6) = 6. degree 7 fires; degree 6 doesn't."""
    cards = [{"id": f"c{i}"} for i in range(20)]
    # c0 has degree 7 (connect to c1..c7) — spaghetti
    # c1 has degree 1 (connected only to c0) — not spaghetti
    proposed = [
        {"from_id": "c0", "to_id": f"c{i}", "confidence": "med"}
        for i in range(1, 8)
    ]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    spaghetti_ids = {s["card_id"] for s in report["spaghetti"]}
    assert "c0" in spaghetti_ids
    assert "c1" not in spaghetti_ids
    assert any(s["card_id"] == "c0" and s["degree"] == 7 and s["threshold"] == 6
               for s in report["spaghetti"])


def test_spaghetti_floor_5_protects_small_whiteboards():
    """N=12 → threshold = max(5, 12//3=4) = 5. Degree 4 must not fire."""
    cards = [{"id": f"c{i}"} for i in range(12)]
    # c0 has degree 4 — would be spaghetti if threshold=4, but floor 5 saves it
    proposed = [
        {"from_id": "c0", "to_id": f"c{i}", "confidence": "med"}
        for i in range(1, 5)
    ]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    assert report["spaghetti"] == []


# ---------- fragile bridge detection ----------


def test_fragile_bridge_detects_single_inter_community_edge():
    """Two clusters of 4 nodes joined by 1 edge → that edge is fragile."""
    cards = [{"id": f"c{i}"} for i in range(8)]
    proposed = [
        # cluster A: c0-c1-c2-c3 fully connected
        {"from_id": "c0", "to_id": "c1", "confidence": "med"},
        {"from_id": "c0", "to_id": "c2", "confidence": "med"},
        {"from_id": "c0", "to_id": "c3", "confidence": "med"},
        {"from_id": "c1", "to_id": "c2", "confidence": "med"},
        {"from_id": "c1", "to_id": "c3", "confidence": "med"},
        {"from_id": "c2", "to_id": "c3", "confidence": "med"},
        # cluster B: c4-c5-c6-c7 fully connected
        {"from_id": "c4", "to_id": "c5", "confidence": "med"},
        {"from_id": "c4", "to_id": "c6", "confidence": "med"},
        {"from_id": "c4", "to_id": "c7", "confidence": "med"},
        {"from_id": "c5", "to_id": "c6", "confidence": "med"},
        {"from_id": "c5", "to_id": "c7", "confidence": "med"},
        {"from_id": "c6", "to_id": "c7", "confidence": "med"},
        # bridge: c3-c4 (single edge between communities)
        {"from_id": "c3", "to_id": "c4", "confidence": "med"},
    ]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    bridges = report["fragile_bridge"]
    assert ("c3", "c4") in bridges or ("c4", "c3") in bridges
    assert len(bridges) == 1


def test_fragile_bridge_empty_for_single_dense_cluster():
    """K5 (5 nodes fully connected) is a single Louvain community →
    zero inter-community edges → empty fragile_bridge."""
    cards = [{"id": f"c{i}"} for i in range(5)]
    proposed = []
    for i in range(5):
        for j in range(i + 1, 5):
            proposed.append(
                {"from_id": f"c{i}", "to_id": f"c{j}", "confidence": "med"}
            )
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    assert report["fragile_bridge"] == []


def test_fragile_bridge_skips_well_connected_community_pair():
    """Two K5 clusters joined by 5 inter-community edges → above
    FRAGILE_BRIDGE_MAX=2 → that community pair contributes no fragile
    bridges. (Other community pairs Louvain might emit are independent
    subdivisions; we don't constrain them, so we only assert the
    cross-K5 edges are absent.)"""
    cards = [{"id": f"c{i}"} for i in range(10)]
    proposed = []
    # K5 on c0..c4
    for i in range(5):
        for j in range(i + 1, 5):
            proposed.append({"from_id": f"c{i}", "to_id": f"c{j}",
                             "confidence": "med"})
    # K5 on c5..c9
    for i in range(5, 10):
        for j in range(i + 1, 10):
            proposed.append({"from_id": f"c{i}", "to_id": f"c{j}",
                             "confidence": "med"})
    # 5 inter-K5 bridges
    for i in range(5):
        proposed.append({"from_id": f"c{i}", "to_id": f"c{i+5}",
                         "confidence": "med"})
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    bridges = report["fragile_bridge"]
    cross_k5 = {(f"c{i}", f"c{i+5}") for i in range(5)}
    cross_k5 |= {(f"c{i+5}", f"c{i}") for i in range(5)}
    # Whatever Louvain decides at finer granularity, none of the 5
    # explicit cross-K5 edges should be flagged fragile
    for edge in bridges:
        assert edge not in cross_k5, (
            f"Cross-K5 edge {edge} flagged fragile despite 5 of them existing"
        )


# ---------- merge candidate detection ----------


def test_merge_candidate_high_overlap_with_high_confidence():
    """A and B both connected to {x, y, z} via existing — Jaccard 1.0,
    high confidence → merge candidate."""
    cards = [{"id": "A"}, {"id": "B"}, {"id": "x"}, {"id": "y"}, {"id": "z"}]
    existing = [
        {"from": "A", "to": "x"}, {"from": "A", "to": "y"}, {"from": "A", "to": "z"},
        {"from": "B", "to": "x"}, {"from": "B", "to": "y"}, {"from": "B", "to": "z"},
    ]
    proposed = [{"from_id": "A", "to_id": "B", "confidence": "high"}]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=existing)
    assert len(report["merge_candidate"]) == 1
    mc = report["merge_candidate"][0]
    assert {mc["from_id"], mc["to_id"]} == {"A", "B"}
    assert mc["overlap"] == 1.0
    assert mc["shared_neighbors"] == ["x", "y", "z"]


def test_merge_candidate_requires_high_confidence():
    """Same overlap topology but med confidence → not flagged."""
    cards = [{"id": "A"}, {"id": "B"}, {"id": "x"}, {"id": "y"}, {"id": "z"}]
    existing = [
        {"from": "A", "to": "x"}, {"from": "A", "to": "y"}, {"from": "A", "to": "z"},
        {"from": "B", "to": "x"}, {"from": "B", "to": "y"}, {"from": "B", "to": "z"},
    ]
    proposed = [{"from_id": "A", "to_id": "B", "confidence": "med"}]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=existing)
    assert report["merge_candidate"] == []


def test_merge_candidate_below_threshold_skipped():
    """A and B share 1 of 4 neighbors → Jaccard ≈ 0.25 → below 0.7."""
    cards = [{"id": "A"}, {"id": "B"}, {"id": "x"}, {"id": "y"}, {"id": "z"}, {"id": "w"}]
    existing = [
        {"from": "A", "to": "x"}, {"from": "A", "to": "y"},
        {"from": "B", "to": "x"}, {"from": "B", "to": "z"}, {"from": "B", "to": "w"},
    ]
    proposed = [{"from_id": "A", "to_id": "B", "confidence": "high"}]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=existing)
    assert report["merge_candidate"] == []


def test_merge_candidate_endpoints_excluded_from_neighbor_set():
    """A and B exist as each other's neighbor in existing — must be
    discarded before computing overlap, otherwise it would double-count."""
    cards = [{"id": "A"}, {"id": "B"}, {"id": "x"}]
    existing = [
        {"from": "A", "to": "B"},  # the proposed pair
        {"from": "A", "to": "x"},
        {"from": "B", "to": "x"},
    ]
    proposed = [{"from_id": "A", "to_id": "B", "confidence": "high"}]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=existing)
    # A's existing neighbors (excluding B): {x}
    # B's existing neighbors (excluding A): {x}
    # Jaccard {x}/{x} = 1.0 → still merge candidate
    assert len(report["merge_candidate"]) == 1
    assert report["merge_candidate"][0]["overlap"] == 1.0


def test_merge_candidate_no_existing_neighbors_skipped():
    """A and B have no existing neighbors at all → cannot compute
    Jaccard meaningfully → skip rather than divide by zero."""
    cards = [{"id": "A"}, {"id": "B"}]
    proposed = [{"from_id": "A", "to_id": "B", "confidence": "high"}]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    assert report["merge_candidate"] == []


# ---------- existing connection alias support ----------


def test_existing_connection_supports_beginid_endid_alias():
    """Heptabase MCP responses use beginId/endId; same as connection_diff."""
    cards = [{"id": "A"}, {"id": "B"}, {"id": "x"}]
    existing = [
        {"beginId": "A", "endId": "x"},
        {"beginId": "B", "endId": "x"},
    ]
    proposed = [{"from_id": "A", "to_id": "B", "confidence": "high"}]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=existing)
    # A's existing neighbors (excluding B): {x}
    # B's existing neighbors (excluding A): {x}
    assert len(report["merge_candidate"]) == 1


# ---------- networkx unavailable fallback ----------


def test_networkx_unavailable_returns_empty_report_with_warning(monkeypatch):
    """Codex P1.1 plan §3.1 corner case: graceful degrade if networkx
    isn't installed."""
    monkeypatch.setattr(gap_signals, "_NX_AVAILABLE", False)
    cards = [{"id": f"c{i}"} for i in range(8)]
    proposed = [{"from_id": "c0", "to_id": "c1", "confidence": "high"}]
    existing = [{"from": "c1", "to": "c2"}]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=existing)
    assert report["weak_integration"] == []
    assert report["central_hub"] == []
    assert any("networkx unavailable" in w for w in report["warnings"])


def test_empty_report_helper_returns_full_shape():
    """Callers rely on this shape regardless of code path."""
    r = empty_report()
    assert set(r.keys()) == {
        "weak_integration", "central_hub", "fragile_bridge",
        "merge_candidate", "spaghetti", "node_count", "edge_count",
        "warnings",
    }


# ---------- forward compat / hardening ----------


def test_proposed_link_self_loop_ignored():
    cards = [{"id": "A"}]
    proposed = [{"from_id": "A", "to_id": "A", "confidence": "high"}]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    assert report["edge_count"] == 0


def test_proposed_link_with_unknown_endpoint_still_added():
    """If proposed pair references a card id not in cards list, networkx
    accepts it; the orphan node appears in the graph but isn't in
    weak_integration count for cards we know about."""
    cards = [{"id": "A"}]
    proposed = [{"from_id": "A", "to_id": "B-not-in-cards", "confidence": "med"}]
    report = compute_gap_signals(cards=cards, proposed_links=proposed,
                                 existing_connections=[])
    # Both A and B-not-in-cards end up in graph; both have degree 1 = weak
    # We don't explicitly filter — gap_signals is downstream of inventory
    # validation, so trusting endpoint hygiene to upstream is acceptable.
    assert report["edge_count"] == 1


def test_constants_match_spec():
    """Spec §2.3 v1.2.2 froze these thresholds; flag any drift."""
    assert WEAK_DEGREE_THRESHOLD == 2
    assert MERGE_OVERLAP_THRESHOLD == 0.7
    assert FRAGILE_BRIDGE_MAX == 2
