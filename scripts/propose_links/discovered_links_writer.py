"""Phase 2C — write enriched pairs as Schema v2 entries to
``_discovered_links.json``.

Per DEV_SPEC_HEPTABRAIN_PROPOSE_LINKS.md §4.2 (entry shape) and
DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md §3.2 (Schema v2 provenance fields).
Plan: IMPLEMENTATION_PLAN_PHASE_2.md §4.1.

Append-only: never mutates existing entries. Same-run dedup is
intrinsic via the seq counter; cross-run dedup (re-propose cooldown)
is deferred to Phase 3 per plan §0 deferrals.

Eligibility filter (writer = downstream of merge_pass2):
  ✅ status == "NEW"
  ✅ pass2_missing == False (Pass 2 actually analyzed it)
  ✅ pass2_skipped == False (NEW pairs aren't skipped, but defensive)
  ✅ confidence in {"high", "med"}  — reject "low" for registry
  ✅ relation_type non-null (validated by JSON schema enum)

Why exclude confidence='low': low-confidence pairs are speculation
worth a human eyeball but not worth permanently committing to the
registry. They still appear in dry-run markdown for audit.

All writes go through ``registry.atomic_write.atomic_write_json``.
Concurrency: read-modify-write last-writer-wins (acceptable for
single-user CLI; cross-process locking deferred per plan §4.1).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.registry.atomic_write import atomic_write_json
from scripts.registry.schema import validate_entry

ELIGIBLE_CONFIDENCE: frozenset[str] = frozenset({"high", "med"})


def _now_iso() -> str:
    """ISO 8601 with timezone, deterministic via UTC."""
    return datetime.now(timezone.utc).isoformat()


def _default_run_timestamp() -> str:
    """Microsecond-precision timestamp for link_id de-collision (Codex
    Phase 2C P2.1 fix). Two append_discovered_links calls within the
    same second now produce distinct link_id prefixes."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _eligible(pair: dict[str, Any]) -> bool:
    if pair.get("status") != "NEW":
        return False
    if pair.get("pass2_skipped"):
        return False
    if pair.get("pass2_missing"):
        return False
    if pair.get("confidence") not in ELIGIBLE_CONFIDENCE:
        return False
    if not pair.get("relation_type"):
        return False
    return True


def build_v2_entry(
    pair: dict[str, Any],
    *,
    cards: list[dict[str, Any]],
    whiteboard_id: str,
    run_timestamp: str,
    seq: int,
) -> dict[str, Any]:
    """Build a single Schema v2 entry from an enriched pair.

    The pair must already have gone through ``merge_pass2`` (so it
    carries from_id/to_id only as inventory positions, accessed via
    ``cards[i]['id']``). We resolve back to card IDs here because
    Phase 2A's enriched-pair shape doesn't redundantly carry the
    string IDs (snapshot-drift guard already verified them at merge
    time).
    """
    i, j = pair["i"], pair["j"]
    from_id = cards[i]["id"]
    to_id = cards[j]["id"]
    pid = pair["pair_id"]

    entry: dict[str, Any] = {
        # Schema-required core
        "link_id": f"lk-{run_timestamp}-{seq:04d}",
        "from_knowledge_id": f"hb-card:{from_id}",
        "to_knowledge_id": f"hb-card:{to_id}",
        "relation_type": pair["relation_type"],
        "rationale": pair.get("rationale") or "(no rationale)",
        "discovered_at": _now_iso(),
        "discovered_by": "propose-links",

        # Optional metrics
        "evidence_refs": [],
        "novelty_score": None,  # closed-set: not novelty-bearing
        "evidence_score": None,

        # v2 provenance (Cyberbrain v3 §3.2)
        "link_class": "proposed",
        "acceptance_state": "proposed",
        "scope_type": "whiteboard",
        "scope_whiteboard_id": whiteboard_id,
        "source_mode": "propose-links",
        # Codex Phase 2C P2.2 fix: reject non-list evidence_kind so a
        # malformed pair (string instead of list) doesn't get expanded
        # to character-list. CLI path is protected by merge_pass2 but
        # the writer can be called directly.
        "evidence_kind": (
            [str(x) for x in pair["evidence_kind"]
             if isinstance(x, str)]
            if isinstance(pair.get("evidence_kind"), list)
            else []
        ),
        "last_verified_at": _now_iso(),
        "verified_by": "ai",

        # v2 auto-accept fields (Phase 3+; null in Phase 2C)
        "implicit_connection_detected": None,
        "auto_accept_reason": None,
        "auto_accept_confidence": None,
        "promoted_from": None,

        # Taxonomy review flag (mirrors needs_review from merge_pass2)
        "needs_taxonomy_review": bool(pair.get("needs_review")),

        # Legacy compat (pre-v2; mirror of acceptance_state)
        "review_state": "proposed",
        "confidence": pair["confidence"],
        "// origin_pair_id": pid,  # diagnostic only; ignored by validator
    }
    return entry


def append_discovered_links(
    registry_path: Path,
    enriched_pairs: list[dict[str, Any]],
    *,
    cards: list[dict[str, Any]],
    whiteboard_id: str,
    run_timestamp: str | None = None,
) -> dict[str, Any]:
    """Append eligible enriched pairs as Schema v2 entries.

    Returns a small report dict: ``{written: int, skipped: int,
    invalid: list[(pair_id, errors)], registry_size: int}``.

    Reads the registry if it exists, validates the new entries against
    the v2 schema before writing, and atomically writes back the
    combined list. If validation fails for any entry, that entry is
    skipped with errors recorded; valid entries still write.

    The ``run_timestamp`` used in link_id is generated once if not
    supplied so all entries from one call share a prefix (eases manual
    audit trails).
    """
    if run_timestamp is None:
        run_timestamp = _default_run_timestamp()

    existing: list[dict[str, Any]] = []
    if registry_path.exists():
        with registry_path.open("r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"existing registry at {registry_path} is not valid JSON: {e}"
                ) from e
            if not isinstance(existing, list):
                raise ValueError(
                    f"existing registry at {registry_path} must be a JSON array; "
                    f"got {type(existing).__name__}"
                )

    written_entries: list[dict[str, Any]] = []
    invalid: list[tuple[str, list[str]]] = []
    skipped = 0
    seq = 0

    for pair in enriched_pairs:
        if not _eligible(pair):
            skipped += 1
            continue
        try:
            entry = build_v2_entry(
                pair,
                cards=cards,
                whiteboard_id=whiteboard_id,
                run_timestamp=run_timestamp,
                seq=seq,
            )
        except (KeyError, IndexError) as e:
            invalid.append((pair.get("pair_id", "?"),
                            [f"build error: {e}"]))
            continue
        errors = validate_entry(entry)
        if errors:
            invalid.append((pair.get("pair_id", "?"), errors))
            continue
        written_entries.append(entry)
        seq += 1

    if written_entries:
        combined = existing + written_entries
        atomic_write_json(registry_path, combined)
        final_size = len(combined)
    else:
        final_size = len(existing)

    return {
        "written": len(written_entries),
        "skipped": skipped,
        "invalid": invalid,
        "registry_size": final_size,
        "run_timestamp": run_timestamp,
    }
