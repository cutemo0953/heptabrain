"""Whiteboard maturity detection — registry → meta_card → title → density.

Per DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md §6.1 + DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §2.1.1.

Each layer that fails to produce a confident answer logs a WARNING and
falls through to the next layer. The function never raises on
malformed inputs; the worst case is the density heuristic, which works
on any non-negative card count.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from scripts.registry.whiteboard_maturity import (
    Maturity,
    MaturitySource,
    STALE_REVIEW_DAYS,
    VALID_MATURITIES,
    get_maturity,
    is_stale,
    load_maturity_registry,
)

logger = logging.getLogger(__name__)

# Regex per Gemini caveat 4: lenient YAML probe, never use PyYAML strict parse
_META_MATURITY_RE = re.compile(r"maturity:\s*([a-zA-Z_]+)", re.IGNORECASE)
_TITLE_MATURITY_RE = re.compile(
    r"\[maturity:\s*(seed|forming|structured|canonical)\]", re.IGNORECASE
)
_META_CARD_TITLE_HINTS = ("⚙️ meta", "⚙ meta", "meta card", "meta")


def detect_maturity(
    inventory: dict[str, Any], registry_path: Path | str | None
) -> tuple[Maturity, MaturitySource]:
    """Resolve maturity for an already-built inventory.

    Caller passes the inventory dict from `build_inventory()`. The
    registry path may be None (skip registry lookup, useful for test
    isolation).
    """
    wb_id = inventory["whiteboard_id"]

    # Layer 1: registry (with staleness check per Codex P1 #4 review)
    if registry_path is not None:
        try:
            registry = load_maturity_registry(registry_path)
            entry = _find_entry(wb_id, registry)
            if entry is not None:
                if is_stale(entry):
                    logger.warning(
                        "registry entry for %s is stale (>%d days since "
                        "last_maturity_reviewed_at); falling through to "
                        "fresher detection layers",
                        wb_id,
                        STALE_REVIEW_DAYS,
                    )
                else:
                    return entry["maturity"], entry["maturity_source"]
        except Exception as exc:
            logger.warning("registry lookup failed for %s: %s", wb_id, exc)

    # Layer 2: ⚙️ Meta card YAML probe
    meta_result = _probe_meta_card(inventory.get("cards", []))
    if meta_result is not None:
        return meta_result, "meta_card"

    # Layer 3: title convention
    title_result = _probe_title(inventory.get("whiteboard_name", ""))
    if title_result is not None:
        return title_result, "title"

    # Layer 4: density heuristic — always returns a value
    return _density_heuristic(inventory["card_count"]), "heuristic"


def _find_entry(wb_id: str, registry: dict[str, Any]) -> dict[str, Any] | None:
    for wb in registry.get("whiteboards", []):
        if wb.get("whiteboard_id") == wb_id:
            return wb
    return None


def _probe_meta_card(cards: list[dict[str, Any]]) -> Maturity | None:
    for card in cards:
        title = (card.get("title") or "").lower()
        if not any(hint in title for hint in _META_CARD_TITLE_HINTS):
            continue
        content = card.get("content") or ""
        match = _META_MATURITY_RE.search(content)
        if not match:
            logger.warning(
                "meta card %r found but no maturity field; falling through",
                card.get("id"),
            )
            continue
        candidate = match.group(1).lower()
        if candidate not in VALID_MATURITIES:
            logger.warning(
                "meta card %r had maturity=%r not in %s; falling through",
                card.get("id"),
                candidate,
                sorted(VALID_MATURITIES),
            )
            continue
        return candidate  # type: ignore[return-value]
    return None


def _probe_title(name: str) -> Maturity | None:
    match = _TITLE_MATURITY_RE.search(name)
    if not match:
        return None
    return match.group(1).lower()  # type: ignore[return-value]


def _density_heuristic(card_count: int) -> Maturity:
    if card_count < 5:
        return "seed"
    if card_count <= 15:
        return "forming"
    if card_count <= 40:
        return "structured"
    return "structured"  # density alone can't distinguish canonical from large-but-immature
