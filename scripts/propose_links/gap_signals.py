"""Phase 2B — gap signal detection via NetworkX.

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §2.3 Step 7 (5-class signal
taxonomy) and IMPLEMENTATION_PLAN_PHASE_2.md §3.

Computes 5 gap signal types from the union graph of (existing
connections ∪ proposed links):

  🔹 weak_integration  — degree < 2
  🔹 central_hub       — top-3 by betweenness centrality (positive only)
  🔹 fragile_bridge    — inter-community edge where the community-pair
                         has only 1-2 inter-community connections
                         (Louvain on connected subgraph)
  🔹 merge_candidate   — proposed-NEW pair with confidence='high' AND
                         endpoints' existing-neighbor overlap > 70%
                         (Jaccard, excluding the pair endpoints from
                         each other's neighbor set)
  🔹 spaghetti         — degree > max(5, N / 3) — concept overload

Edge cases per plan §3.1:
- Isolated nodes (degree 0) → weak_integration; never enter Louvain
- Empty graph → empty report (no crash, no warning)
- N < 5 → skip clustering; fragile_bridge always [] (whiteboard too
  small for community structure to be meaningful)
- networkx ImportError → graceful empty report + warning

Pure function. No I/O. Caller is responsible for rendering the report
into markdown (see ``output.render_dryrun_markdown``).
"""
from __future__ import annotations

from typing import Any

try:
    import networkx as nx  # type: ignore[import-not-found]
    _NX_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised via monkeypatch test
    nx = None  # type: ignore[assignment]
    _NX_AVAILABLE = False

# ---------------------------------------------------------------------------
# Tunable thresholds — frozen by spec §2.3 Step 7. Do not change without
# updating the spec and the merge_candidate / fragile_bridge tests.
# ---------------------------------------------------------------------------
WEAK_DEGREE_THRESHOLD: int = 2  # degree < this → weak
SPAGHETTI_DEGREE_FLOOR: int = 5  # absolute floor; small whiteboards safe
TOP_HUB_COUNT: int = 3
MERGE_OVERLAP_THRESHOLD: float = 0.7
MIN_NODES_FOR_CLUSTERING: int = 5
FRAGILE_BRIDGE_MAX: int = 2  # community pair with ≤ this many edges = fragile
LOUVAIN_SEED: int = 42  # determinism for tests


def _spaghetti_threshold(n: int) -> int:
    """Per spec §2.3 v1.2.2: degree > max(5, N/3)."""
    return max(SPAGHETTI_DEGREE_FLOOR, n // 3)


def _existing_neighbors_index(
    existing_connections: list[dict[str, Any]],
) -> dict[str, set[str]]:
    """Build adjacency index from existing connections only.

    Used for merge_candidate Jaccard. Keyed by card id; value is the
    set of neighbor ids reached via existing (already-drawn) connections.
    Direction is ignored (existing connections are treated as undirected
    for this purpose, matching connection_diff semantics).
    """
    idx: dict[str, set[str]] = {}
    for conn in existing_connections:
        from_id = conn.get("from") or conn.get("beginId")
        to_id = conn.get("to") or conn.get("endId")
        if not (from_id and to_id) or from_id == to_id:
            continue
        idx.setdefault(from_id, set()).add(to_id)
        idx.setdefault(to_id, set()).add(from_id)
    return idx


def _build_graph(
    cards: list[dict[str, Any]],
    proposed_links: list[dict[str, Any]],
    existing_connections: list[dict[str, Any]],
):
    """Build the union graph (existing ∪ proposed) on which all metrics
    are computed. Nodes = card ids. Edges carry ``source`` attribute
    (``existing`` / ``proposed``) for diagnostic introspection.
    """
    G = nx.Graph()
    for c in cards:
        cid = c.get("id")
        if cid:
            G.add_node(cid)

    for conn in existing_connections:
        from_id = conn.get("from") or conn.get("beginId")
        to_id = conn.get("to") or conn.get("endId")
        if from_id and to_id and from_id != to_id:
            G.add_edge(from_id, to_id, source="existing")

    for p in proposed_links:
        a = p.get("from_id")
        b = p.get("to_id")
        if a and b and a != b:
            # Don't downgrade an existing edge's 'source'; if the same
            # pair appears in both lists, mark it 'both' for diagnostics.
            if G.has_edge(a, b):
                G[a][b]["source"] = "both"
            else:
                G.add_edge(a, b, source="proposed")
    return G


def _compute_central_hub(G) -> list[str]:
    """Top-3 by betweenness, positive scores only."""
    if G.number_of_edges() == 0:
        return []
    bc = nx.betweenness_centrality(G)
    ranked = sorted(bc.items(), key=lambda x: (-x[1], x[0]))
    return [node for node, score in ranked[:TOP_HUB_COUNT] if score > 0]


def _compute_fragile_bridges(G) -> list[tuple[str, str]]:
    """Inter-community edges in community-pairs with ≤ FRAGILE_BRIDGE_MAX
    inter-community connections. Computed on the largest connected piece;
    isolated nodes are stripped so Louvain doesn't choke.
    """
    if G.number_of_nodes() < MIN_NODES_FOR_CLUSTERING:
        return []
    connected_nodes = [n for n in G.nodes if G.degree(n) > 0]
    if len(connected_nodes) < 2:
        return []
    sub = G.subgraph(connected_nodes).copy()
    if sub.number_of_edges() == 0:
        return []

    try:
        communities = nx.community.louvain_communities(sub, seed=LOUVAIN_SEED)
    except Exception:  # pragma: no cover — defensive; networkx ≥3.2 stable
        return []

    node_to_community: dict[str, int] = {}
    for idx, comm in enumerate(communities):
        for node in comm:
            node_to_community[node] = idx

    inter_edges: dict[tuple[int, int], list[tuple[str, str]]] = {}
    for u, v in sub.edges:
        ca = node_to_community.get(u)
        cb = node_to_community.get(v)
        if ca is None or cb is None or ca == cb:
            continue
        key = (ca, cb) if ca < cb else (cb, ca)
        inter_edges.setdefault(key, []).append(tuple(sorted((u, v))))

    fragile: list[tuple[str, str]] = []
    for edges in inter_edges.values():
        if 1 <= len(edges) <= FRAGILE_BRIDGE_MAX:
            fragile.extend(edges)
    return fragile


def _compute_merge_candidates(
    proposed_links: list[dict[str, Any]],
    existing_index: dict[str, set[str]],
) -> list[dict[str, Any]]:
    """Pair where confidence='high' AND endpoints' existing-neighbor
    Jaccard overlap > MERGE_OVERLAP_THRESHOLD.

    Excludes the other endpoint from each side's neighbor set so we
    don't count the proposed pair itself as overlap.

    If neither endpoint has any existing neighbor (other than each
    other), the union is empty and we cannot compute a meaningful
    Jaccard — skip.
    """
    out: list[dict[str, Any]] = []
    for p in proposed_links:
        if p.get("confidence") != "high":
            continue
        a = p.get("from_id")
        b = p.get("to_id")
        if not (a and b) or a == b:
            continue
        a_neigh = set(existing_index.get(a, set()))
        b_neigh = set(existing_index.get(b, set()))
        a_neigh.discard(b)
        b_neigh.discard(a)
        union = a_neigh | b_neigh
        if not union:
            continue
        overlap = len(a_neigh & b_neigh) / len(union)
        if overlap > MERGE_OVERLAP_THRESHOLD:
            out.append(
                {
                    "from_id": a,
                    "to_id": b,
                    "overlap": round(overlap, 2),
                    "shared_neighbors": sorted(a_neigh & b_neigh),
                }
            )
    return out


def empty_report() -> dict[str, Any]:
    """The shape callers can rely on even when networkx is unavailable
    or the graph is empty."""
    return {
        "weak_integration": [],
        "central_hub": [],
        "fragile_bridge": [],
        "merge_candidate": [],
        "spaghetti": [],
        "node_count": 0,
        "edge_count": 0,
        "warnings": [],
    }


def compute_gap_signals(
    cards: list[dict[str, Any]],
    proposed_links: list[dict[str, Any]],
    existing_connections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Top-level signal computation. See module docstring for taxonomy."""
    if not _NX_AVAILABLE:
        report = empty_report()
        report["warnings"].append(
            "networkx unavailable — gap signal detection skipped (graph "
            "topology requires networkx ≥ 3.2)"
        )
        return report

    G = _build_graph(cards, proposed_links, existing_connections)
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    if n_nodes == 0:
        return empty_report()

    weak = sorted([n for n in G.nodes if G.degree(n) < WEAK_DEGREE_THRESHOLD])
    spaghetti_t = _spaghetti_threshold(n_nodes)
    spaghetti = sorted(
        [
            {"card_id": n, "degree": G.degree(n), "threshold": spaghetti_t}
            for n in G.nodes
            if G.degree(n) > spaghetti_t
        ],
        key=lambda x: (-x["degree"], x["card_id"]),
    )
    central_hub = _compute_central_hub(G)
    fragile_bridge = _compute_fragile_bridges(G)
    existing_index = _existing_neighbors_index(existing_connections)
    merge_candidate = _compute_merge_candidates(proposed_links, existing_index)

    return {
        "weak_integration": weak,
        "central_hub": central_hub,
        "fragile_bridge": fragile_bridge,
        "merge_candidate": merge_candidate,
        "spaghetti": spaghetti,
        "node_count": n_nodes,
        "edge_count": n_edges,
        "warnings": [],
    }
