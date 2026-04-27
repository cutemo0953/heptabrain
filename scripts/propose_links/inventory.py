"""Whiteboard inventory — filter analyzable cards, extract existing
connections, decide processing scale tier.

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §2.1 + §2.3.
"""
from __future__ import annotations

from typing import Any, Literal

from scripts.lib.mcp_client import MCPClient

ANALYZABLE_TYPES: frozenset[str] = frozenset(
    {"card", "pdfCard", "mediaCard", "highlightElement"}
)

ScaleTier = Literal["small_no_cluster", "normal_funnel", "hard_stop"]


def classify_scale_tier(card_count: int) -> ScaleTier:
    """Per spec §2.3: <8 small_no_cluster, 8-50 normal_funnel, >50 hard_stop."""
    if card_count < 8:
        return "small_no_cluster"
    if card_count <= 50:
        return "normal_funnel"
    return "hard_stop"


def build_inventory(whiteboard_id: str, client: MCPClient) -> dict[str, Any]:
    wb = client.get_whiteboard_with_objects(whiteboard_id)
    objects = wb.get("objects", [])

    analyzable: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    for obj in objects:
        obj_type = obj.get("type", "unknown")
        if obj_type in ANALYZABLE_TYPES:
            analyzable.append(obj)
        else:
            skipped[obj_type] = skipped.get(obj_type, 0) + 1

    return {
        "whiteboard_id": wb["id"],
        "whiteboard_name": wb.get("name", ""),
        "cards": analyzable,
        "card_count": len(analyzable),
        "skipped": skipped,
        "existing_connections": list(wb.get("connections", [])),
        "scale_tier": classify_scale_tier(len(analyzable)),
    }
