from scripts.constants.relation_types import (
    FALLBACK_RELATION,
    RELATION_TYPES,
    is_valid_relation,
    needs_taxonomy_review,
)


def test_exactly_eleven_relation_types():
    assert len(RELATION_TYPES) == 11
    assert len(set(RELATION_TYPES)) == 11


def test_zettel_walk_seven_present():
    for name in (
        "supports",
        "contradicts",
        "derives_from",
        "applies_to",
        "example_of",
        "bridge_to",
        "tensions_with",
    ):
        assert name in RELATION_TYPES


def test_mda_three_present():
    for name in ("synergizes-with", "attracts", "precedes"):
        assert name in RELATION_TYPES


def test_shares_principle_present():
    assert "shares_principle" in RELATION_TYPES


def test_mixed_naming_preserved():
    assert "synergizes-with" in RELATION_TYPES
    assert "synergizes_with" not in RELATION_TYPES
    assert "shares_principle" in RELATION_TYPES


def test_fallback_is_not_canonical():
    assert FALLBACK_RELATION == "related_to"
    assert FALLBACK_RELATION not in RELATION_TYPES


def test_is_valid_relation_positive():
    assert is_valid_relation("shares_principle")
    assert is_valid_relation("synergizes-with")


def test_is_valid_relation_negative():
    assert not is_valid_relation("related_to")
    assert not is_valid_relation("supports_weakly")
    assert not is_valid_relation("")


def test_needs_taxonomy_review():
    assert needs_taxonomy_review("related_to")
    assert not needs_taxonomy_review("supports")
