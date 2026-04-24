"""Relation type vocabulary for Cyberbrain registry.

Frozen per DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md §5.3. Mixed underscore/hyphen
naming is intentional — historical ADR; do not normalize without a new ADR.
"""
from __future__ import annotations

RELATION_TYPES: tuple[str, ...] = (
    "supports",
    "contradicts",
    "derives_from",
    "applies_to",
    "example_of",
    "bridge_to",
    "tensions_with",
    "synergizes-with",
    "attracts",
    "precedes",
    "shares_principle",
)

FALLBACK_RELATION: str = "related_to"


def is_valid_relation(relation: str) -> bool:
    return relation in RELATION_TYPES


def needs_taxonomy_review(relation: str) -> bool:
    return relation == FALLBACK_RELATION
