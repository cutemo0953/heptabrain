from scripts.propose_links.connection_diff import (
    build_existing_pair_set,
    classify_pairs,
    diff_summary,
)


# ---------- build_existing_pair_set ----------


def test_collapses_direction():
    conns = [
        {"from": "a", "to": "b"},
        {"from": "b", "to": "a"},  # reverse direction
    ]
    result = build_existing_pair_set(conns)
    assert len(result) == 1
    assert frozenset({"a", "b"}) in result


def test_supports_beginId_endId_alias():
    """Real Heptabase MCP responses use beginId/endId (XML-style) instead
    of from/to. Our adapter should accept both."""
    conns = [{"beginId": "a", "endId": "b"}]
    assert frozenset({"a", "b"}) in build_existing_pair_set(conns)


def test_skips_self_loops():
    conns = [{"from": "a", "to": "a"}]
    assert build_existing_pair_set(conns) == set()


def test_skips_malformed_entries():
    conns = [
        {"from": "a"},  # missing to
        {"to": "b"},  # missing from
        {},
        {"from": "x", "to": "y"},  # valid
    ]
    result = build_existing_pair_set(conns)
    assert result == {frozenset({"x", "y"})}


def test_empty_input():
    assert build_existing_pair_set([]) == set()


# ---------- classify_pairs ----------


def _cards():
    return [
        {"id": "card-1"},
        {"id": "card-2"},
        {"id": "card-3"},
        {"id": "card-4"},
    ]


def test_classifies_all_new_when_no_existing_connections():
    pair_scores = [(0, 1, 0.5), (1, 2, 0.3)]
    result = classify_pairs(pair_scores, _cards(), [])
    statuses = [r[3] for r in result]
    assert statuses == ["NEW", "NEW"]


def test_marks_exists_when_pair_already_connected():
    pair_scores = [(0, 1, 0.5), (2, 3, 0.4)]
    existing = [{"from": "card-1", "to": "card-2"}]
    result = classify_pairs(pair_scores, _cards(), existing)
    assert result[0][3] == "EXISTS"
    assert result[1][3] == "NEW"


def test_marks_exists_regardless_of_direction():
    pair_scores = [(0, 1, 0.5)]
    existing = [{"from": "card-2", "to": "card-1"}]  # opposite of pair order
    result = classify_pairs(pair_scores, _cards(), existing)
    assert result[0][3] == "EXISTS"


def test_preserves_score_and_indices():
    pair_scores = [(0, 1, 0.732)]
    result = classify_pairs(pair_scores, _cards(), [])
    assert result[0][:3] == (0, 1, 0.732)


def test_handles_card_missing_id_gracefully():
    """If a card lacks an id, the pair is still emitted as NEW (cannot
    match anything in existing set)."""
    cards = [{"title": "no id"}, {"id": "card-2"}]
    pair_scores = [(0, 1, 0.5)]
    result = classify_pairs(pair_scores, cards, [{"from": "x", "to": "card-2"}])
    assert result[0][3] == "NEW"


# ---------- diff_summary ----------


def test_summary_counts_each_status():
    classified = [
        (0, 1, 0.5, "NEW"),
        (1, 2, 0.4, "EXISTS"),
        (2, 3, 0.3, "NEW"),
        (0, 3, 0.2, "EXISTS"),
    ]
    counts = diff_summary(classified)
    assert counts == {"NEW": 2, "EXISTS": 2, "REDUNDANT": 0}


def test_summary_empty_input():
    assert diff_summary([]) == {"NEW": 0, "EXISTS": 0, "REDUNDANT": 0}
