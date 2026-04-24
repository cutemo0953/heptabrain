"""Whiteboard maturity registry — canonical source for maturity states.

Per DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md §3.5. Paired with §6.1 dual-fallback:
callers check this registry first; on miss they fall through to meta_card,
title convention, then density heuristic.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from scripts.registry.atomic_write import atomic_write_json

Maturity = Literal["seed", "forming", "structured", "canonical"]
MaturitySource = Literal["manual", "heuristic", "meta_card", "title"]

VALID_MATURITIES: frozenset[str] = frozenset(
    {"seed", "forming", "structured", "canonical"}
)
VALID_SOURCES: frozenset[str] = frozenset(
    {"manual", "heuristic", "meta_card", "title"}
)

SOURCE_AUTHORITY: dict[str, int] = {
    "manual": 4,
    "meta_card": 3,
    "heuristic": 2,
    "title": 1,
}

REGISTRY_VERSION = "1.0"
STALE_REVIEW_DAYS = 90


def _empty_registry() -> dict:
    return {"version": REGISTRY_VERSION, "whiteboards": []}


def load_maturity_registry(path: Path | str) -> dict:
    path = Path(path)
    if not path.exists():
        return _empty_registry()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("version", REGISTRY_VERSION)
    data.setdefault("whiteboards", [])
    return data


def get_maturity(
    whiteboard_id: str, registry: dict
) -> tuple[Maturity, MaturitySource] | None:
    for wb in registry.get("whiteboards", []):
        if wb["whiteboard_id"] == whiteboard_id:
            return wb["maturity"], wb["maturity_source"]
    return None


def set_maturity(
    whiteboard_id: str,
    maturity: str,
    source: str,
    registry_path: Path | str,
    *,
    note: str = "",
    now: datetime | None = None,
) -> dict:
    """Upsert a maturity entry, gated by source-authority precedence.

    Returns a structured result:
      {
        "registry": <full registry dict>,
        "applied":  bool,                       # True if on-disk changed
        "outcome":  "created" | "replaced" | "suppressed",
        "reason":   str | None,                 # only when suppressed
        "suppressed_by": {"source": ..., "authority": ...} | None,
      }

    `suppressed` happens when an existing entry has stricter authority than the
    incoming write (Codex P2 #1 fix — callers can distinguish write-applied from
    write-dropped instead of relying on silent precedence).
    """
    if maturity not in VALID_MATURITIES:
        raise ValueError(f"invalid maturity: {maturity!r}")
    if source not in VALID_SOURCES:
        raise ValueError(f"invalid maturity_source: {source!r}")

    now = now or datetime.now(timezone.utc)
    registry = load_maturity_registry(registry_path)

    new_entry = {
        "whiteboard_id": whiteboard_id,
        "maturity": maturity,
        "maturity_source": source,
        "last_maturity_reviewed_at": now.isoformat().replace("+00:00", "Z"),
    }
    if note:
        new_entry["note"] = note

    existing_idx: int | None = None
    for idx, wb in enumerate(registry["whiteboards"]):
        if wb["whiteboard_id"] == whiteboard_id:
            existing_idx = idx
            break

    if existing_idx is None:
        registry["whiteboards"].append(new_entry)
        atomic_write_json(registry_path, registry)
        return {
            "registry": registry,
            "applied": True,
            "outcome": "created",
            "reason": None,
            "suppressed_by": None,
        }

    existing = registry["whiteboards"][existing_idx]
    existing_source = existing.get("maturity_source", "")
    existing_authority = SOURCE_AUTHORITY.get(existing_source, 0)
    new_authority = SOURCE_AUTHORITY[source]

    if new_authority >= existing_authority:
        registry["whiteboards"][existing_idx] = new_entry
        atomic_write_json(registry_path, registry)
        return {
            "registry": registry,
            "applied": True,
            "outcome": "replaced",
            "reason": None,
            "suppressed_by": None,
        }

    # Lower authority than existing — do NOT write. No file touch.
    return {
        "registry": registry,
        "applied": False,
        "outcome": "suppressed",
        "reason": (
            f"source={source!r} (authority={new_authority}) lower than existing "
            f"source={existing_source!r} (authority={existing_authority})"
        ),
        "suppressed_by": {
            "source": existing_source,
            "authority": existing_authority,
        },
    }


def is_stale(
    entry: dict, *, threshold_days: int = STALE_REVIEW_DAYS, now: datetime | None = None
) -> bool:
    now = now or datetime.now(timezone.utc)
    ts = entry.get("last_maturity_reviewed_at")
    if not ts:
        return True
    reviewed_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return now - reviewed_at > timedelta(days=threshold_days)


def find_stale_entries(
    registry: dict, *, threshold_days: int = STALE_REVIEW_DAYS, now: datetime | None = None
) -> list[dict]:
    return [
        wb
        for wb in registry.get("whiteboards", [])
        if is_stale(wb, threshold_days=threshold_days, now=now)
    ]
