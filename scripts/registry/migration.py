"""Legacy → v2 migration: fallback, report, lazy write-back.

Per DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md §3.3. In-memory fallback is used for
read paths; explicit `commit_lazy_writeback()` performs the audit-triggered
write per §3.2. Legacy entries are never silently mutated.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.registry.atomic_write import atomic_write_json
from scripts.registry.schema import V2_AUTO_ACCEPT_FIELDS, V2_REQUIRED_FIELDS


def _infer_link_class(discovered_by: str) -> str:
    if "manual" in discovered_by.lower():
        return "canonical"
    return "proposed"


def _infer_acceptance_state(review_state: str | None) -> str:
    if review_state in ("accepted", "rejected", "proposed"):
        return review_state
    return "proposed"


def _infer_scope_type(discovered_by: str) -> str:
    if "propose-links" in discovered_by.lower():
        return "whiteboard"
    return "cross_whiteboard"


def _infer_source_mode(discovered_by: str) -> str:
    # "zettel-walk wander" → "zettel-walk:wander"
    # "propose-links" → "propose-links"
    parts = discovered_by.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    return parts[0] if parts else "unknown"


def _infer_evidence_kind(evidence_refs: list[str] | None) -> list[str]:
    if not evidence_refs:
        return []
    joined = " ".join(evidence_refs).lower()
    if "kb" in joined:
        return ["text_overlap"]
    return []


def fallback_legacy_entry(entry: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(entry)
    discovered_by = out.get("discovered_by", "")
    discovered_at = out.get("discovered_at", "")

    if out.get("link_class") is None:
        out["link_class"] = _infer_link_class(discovered_by)
    if out.get("acceptance_state") is None:
        out["acceptance_state"] = _infer_acceptance_state(out.get("review_state"))
    if out.get("scope_type") is None:
        out["scope_type"] = _infer_scope_type(discovered_by)
    if "scope_whiteboard_id" not in out:
        out["scope_whiteboard_id"] = None
    if out.get("source_mode") is None:
        out["source_mode"] = _infer_source_mode(discovered_by)
    if out.get("evidence_kind") is None:
        out["evidence_kind"] = _infer_evidence_kind(out.get("evidence_refs"))
    if out.get("last_verified_at") is None:
        out["last_verified_at"] = discovered_at
    if out.get("verified_by") is None:
        out["verified_by"] = "ai"

    for field in V2_AUTO_ACCEPT_FIELDS:
        out.setdefault(field, None)

    return out


def _legacy_field_diff(original: dict, enriched: dict) -> list[str]:
    changed = []
    for field in V2_REQUIRED_FIELDS + V2_AUTO_ACCEPT_FIELDS:
        orig_present = field in original and original[field] is not None
        enriched_present = field in enriched and enriched[field] is not None
        if not orig_present and (enriched_present or field in V2_AUTO_ACCEPT_FIELDS):
            changed.append(field)
    return changed


def _is_ambiguous(original: dict) -> list[str]:
    notes = []
    discovered_by = original.get("discovered_by", "")
    review_state = original.get("review_state")
    if "manual" in discovered_by.lower() and not review_state:
        notes.append(
            "discovered_by=manual but review_state missing — link_class inference may be wrong"
        )
    if not discovered_by:
        notes.append("discovered_by empty — source_mode/scope_type inference unreliable")
    return notes


def generate_migration_report(registry_path: Path | str) -> str:
    registry_path = Path(registry_path)
    with registry_path.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    total = len(entries)
    needs_migration = 0
    by_link_class_fallback = {"canonical": 0, "proposed": 0}
    by_scope_fallback = {"whiteboard": 0, "cross_whiteboard": 0}
    ambiguities: list[tuple[str, list[str]]] = []

    for entry in entries:
        enriched = fallback_legacy_entry(entry)
        diff = _legacy_field_diff(entry, enriched)
        if diff:
            needs_migration += 1
            if "link_class" in diff:
                by_link_class_fallback[enriched["link_class"]] += 1
            if "scope_type" in diff:
                by_scope_fallback[enriched["scope_type"]] += 1
        notes = _is_ambiguous(entry)
        if notes:
            ambiguities.append((entry.get("link_id", "<no-id>"), notes))

    lines = [
        "# Registry Migration Report — Legacy v2.1 → v3.0.1 Schema v2",
        "",
        f"- Total entries: {total}",
        f"- Needs normalization: {needs_migration}",
        f"- Already v2-complete: {total - needs_migration}",
        "",
        "## Fallback distribution",
        "",
        "### link_class inference",
        f"- canonical (from `manual` heuristic): {by_link_class_fallback['canonical']}",
        f"- proposed (default): {by_link_class_fallback['proposed']}",
        "",
        "### scope_type inference",
        f"- whiteboard (from `propose-links` heuristic): {by_scope_fallback['whiteboard']}",
        f"- cross_whiteboard (default): {by_scope_fallback['cross_whiteboard']}",
        "",
        "## Ambiguous entries",
        "",
    ]
    if ambiguities:
        for link_id, notes in ambiguities:
            lines.append(f"- `{link_id}`:")
            for n in notes:
                lines.append(f"  - {n}")
    else:
        lines.append("(none)")

    lines += [
        "",
        "---",
        "",
        "_This report was generated from fallback inference only; the main registry file has NOT been modified._",
        "_Run `commit_lazy_writeback()` after human review to actually normalize the on-disk registry._",
    ]
    return "\n".join(lines)


def commit_lazy_writeback(registry_path: Path | str) -> Path:
    registry_path = Path(registry_path)
    with registry_path.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Per §3.2: preserve original filename, append `.v2.1-backup-<ts>.json`
    # e.g. `_discovered_links.json` → `_discovered_links.json.v2.1-backup-<ts>.json`
    backup_path = registry_path.with_name(f"{registry_path.name}.v2.1-backup-{ts}.json")
    atomic_write_json(backup_path, entries)

    normalized = [fallback_legacy_entry(e) for e in entries]
    atomic_write_json(registry_path, normalized)
    return backup_path
