import pytest

from scripts.registry.lifecycle import (
    ALLOWED_STATES_BY_CLASS,
    apply_acceptance,
    audit_combination,
    is_valid_combination,
    is_valid_state_transition,
)


# ---------- matrix §5.2.1 ----------


def test_canonical_allowed_combinations():
    for state in ("accepted", "stale", "superseded"):
        assert is_valid_combination("canonical", state)


def test_canonical_disallowed_combinations():
    for state in ("proposed", "rejected"):
        assert not is_valid_combination("canonical", state)


def test_proposed_allowed_combinations():
    for state in ("proposed", "accepted", "rejected", "superseded", "stale"):
        assert is_valid_combination("proposed", state)


def test_exploratory_cannot_be_accepted_directly():
    assert not is_valid_combination("exploratory", "accepted")


def test_exploratory_allowed_combinations():
    for state in ("proposed", "rejected", "superseded", "stale"):
        assert is_valid_combination("exploratory", state)


def test_unknown_class_fails():
    assert not is_valid_combination("deprecated", "accepted")


def test_matrix_shape_frozen():
    assert set(ALLOWED_STATES_BY_CLASS) == {"canonical", "proposed", "exploratory"}


# ---------- state-only transitions §5.4 ----------


def test_proposed_to_accepted():
    assert is_valid_state_transition("proposed", "accepted")


def test_accepted_to_stale():
    assert is_valid_state_transition("accepted", "stale")


def test_stale_to_accepted():
    assert is_valid_state_transition("stale", "accepted")


def test_rejected_is_terminal():
    for state in ("accepted", "stale", "superseded", "proposed"):
        assert not is_valid_state_transition("rejected", state)


def test_superseded_is_terminal():
    for state in ("accepted", "stale", "proposed"):
        assert not is_valid_state_transition("superseded", state)


def test_unknown_current_state_rejected():
    assert not is_valid_state_transition("imagined", "accepted")


# ---------- class promotion §5.2.2 ----------


def test_canonical_accept_stays_canonical():
    entry = {"link_class": "canonical", "acceptance_state": "stale"}
    out = apply_acceptance(entry)
    assert out["link_class"] == "canonical"
    assert out["acceptance_state"] == "accepted"
    assert "promoted_from" not in out


def test_proposed_accept_promotes_to_canonical():
    entry = {
        "link_class": "proposed",
        "acceptance_state": "proposed",
        "link_id": "lk-001",
    }
    out = apply_acceptance(entry)
    assert out["link_class"] == "canonical"
    assert out["acceptance_state"] == "accepted"
    assert out["promoted_from"] == "proposed"


def test_exploratory_accept_promotes_to_canonical_one_step():
    entry = {"link_class": "exploratory", "acceptance_state": "proposed"}
    out = apply_acceptance(entry)
    assert out["link_class"] == "canonical"
    assert out["acceptance_state"] == "accepted"
    assert out["promoted_from"] == "exploratory"


def test_apply_acceptance_does_not_mutate_input():
    entry = {"link_class": "proposed", "acceptance_state": "proposed"}
    apply_acceptance(entry)
    assert entry == {"link_class": "proposed", "acceptance_state": "proposed"}


def test_apply_acceptance_requires_link_class():
    with pytest.raises(ValueError):
        apply_acceptance({"acceptance_state": "proposed"})


def test_apply_acceptance_rejects_unknown_class():
    with pytest.raises(ValueError):
        apply_acceptance({"link_class": "mystery", "acceptance_state": "proposed"})


def test_post_promotion_combination_is_valid():
    for origin in ("proposed", "exploratory"):
        entry = {"link_class": origin, "acceptance_state": "proposed"}
        out = apply_acceptance(entry)
        assert is_valid_combination(out["link_class"], out["acceptance_state"])


# ---------- audit_combination ----------


def test_audit_passes_valid():
    entry = {
        "link_id": "lk-001",
        "link_class": "proposed",
        "acceptance_state": "proposed",
    }
    assert audit_combination(entry) is None


def test_audit_flags_invalid():
    entry = {
        "link_id": "lk-002",
        "link_class": "exploratory",
        "acceptance_state": "accepted",
    }
    issue = audit_combination(entry)
    assert issue is not None
    assert issue["link_id"] == "lk-002"
    assert "§5.2.1" in issue["reason"]


def test_audit_skips_entries_missing_fields():
    assert audit_combination({"link_id": "lk-003"}) is None
