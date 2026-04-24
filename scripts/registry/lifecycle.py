"""Link lifecycle — class × state matrix + class promotion on accept.

Per DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md §5.2.1 (matrix) and §5.2.2 (promotion).

Matrix semantics: these are the VALID (class, state) combinations an entry may
hold at rest. Transitions are separate — §5.4. The special case is accepting
an `exploratory` link: that would produce the illegal (exploratory, accepted)
combo, so `apply_acceptance` runs the class promotion rule simultaneously.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

LinkClass = Literal["canonical", "proposed", "exploratory"]
AcceptanceState = Literal["proposed", "accepted", "rejected", "superseded", "stale"]

ALLOWED_STATES_BY_CLASS: dict[LinkClass, frozenset[AcceptanceState]] = {
    "canonical": frozenset({"accepted", "stale", "superseded"}),
    "proposed": frozenset(
        {"proposed", "accepted", "rejected", "superseded", "stale"}
    ),
    "exploratory": frozenset({"proposed", "rejected", "superseded", "stale"}),
}

# §5.4 — transitions that are allowed at all (class-agnostic; class×state
# validity is checked separately against the matrix).
ALLOWED_STATE_TRANSITIONS: dict[AcceptanceState, frozenset[AcceptanceState]] = {
    "proposed": frozenset({"accepted", "rejected", "superseded"}),
    "accepted": frozenset({"stale", "superseded"}),
    "rejected": frozenset(),
    "stale": frozenset({"accepted", "rejected", "superseded"}),
    "superseded": frozenset(),
}


def is_valid_combination(link_class: str, acceptance_state: str) -> bool:
    if link_class not in ALLOWED_STATES_BY_CLASS:
        return False
    return acceptance_state in ALLOWED_STATES_BY_CLASS[link_class]


def is_valid_state_transition(current: str, new: str) -> bool:
    if current not in ALLOWED_STATE_TRANSITIONS:
        return False
    return new in ALLOWED_STATE_TRANSITIONS[current]


def apply_acceptance(entry: dict[str, Any]) -> dict[str, Any]:
    if "link_class" not in entry or entry["link_class"] is None:
        raise ValueError("entry has no link_class; cannot apply acceptance")

    out = deepcopy(entry)
    original_class = out["link_class"]

    if original_class in ("proposed", "exploratory"):
        out["promoted_from"] = original_class
        out["link_class"] = "canonical"
    elif original_class == "canonical":
        # already canonical; leave promoted_from untouched
        pass
    else:
        raise ValueError(f"unknown link_class: {original_class!r}")

    out["acceptance_state"] = "accepted"
    return out


def audit_combination(entry: dict[str, Any]) -> dict[str, Any] | None:
    link_class = entry.get("link_class")
    state = entry.get("acceptance_state")
    if link_class is None or state is None:
        return None
    if not is_valid_combination(link_class, state):
        return {
            "link_id": entry.get("link_id"),
            "link_class": link_class,
            "acceptance_state": state,
            "reason": "invalid class × state combination per §5.2.1",
        }
    return None
