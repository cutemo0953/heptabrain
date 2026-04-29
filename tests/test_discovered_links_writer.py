"""Tests for Phase 2C discovered_links_writer.

Per IMPLEMENTATION_PLAN_PHASE_2.md §4.1 acceptance — 5 cases plus
schema-validation + atomic-write hardening coverage.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.propose_links.discovered_links_writer import (
    ELIGIBLE_CONFIDENCE,
    _eligible,
    append_discovered_links,
    build_v2_entry,
)


def _cards():
    return [
        {"id": "card-a", "title": "Alpha"},
        {"id": "card-b", "title": "Beta"},
        {"id": "card-c", "title": "Gamma"},
    ]


def _enriched(
    *,
    pair_id="p-0-1", i=0, j=1, status="NEW",
    relation_type="shares_principle", rationale="ok", confidence="high",
    needs_review=False, pass2_skipped=False, pass2_missing=False,
    score=0.5, evidence_kind=None,
):
    return {
        "pair_id": pair_id, "i": i, "j": j, "score": score,
        "status": status,
        "relation_type": relation_type, "rationale": rationale,
        "confidence": confidence,
        "evidence_kind": evidence_kind or [],
        "needs_review": needs_review,
        "pass2_skipped": pass2_skipped,
        "pass2_missing": pass2_missing,
    }


# ---------- _eligible ----------


@pytest.mark.parametrize("conf,expected", [
    ("high", True), ("med", True), ("low", False), (None, False), ("", False),
])
def test_eligible_filters_confidence(conf, expected):
    assert _eligible(_enriched(confidence=conf)) is expected


def test_eligible_filters_non_new_status():
    assert _eligible(_enriched(status="EXISTS")) is False
    assert _eligible(_enriched(status="REDUNDANT")) is False


def test_eligible_filters_pass2_skipped_and_missing():
    assert _eligible(_enriched(pass2_skipped=True)) is False
    assert _eligible(_enriched(pass2_missing=True)) is False


def test_eligible_requires_relation_type():
    assert _eligible(_enriched(relation_type=None)) is False
    assert _eligible(_enriched(relation_type="")) is False


def test_eligible_constants_match_spec():
    assert ELIGIBLE_CONFIDENCE == frozenset({"high", "med"})


# ---------- build_v2_entry shape ----------


def test_build_v2_entry_has_all_required_schema_fields():
    pair = _enriched()
    entry = build_v2_entry(
        pair, cards=_cards(), whiteboard_id="wb-1",
        run_timestamp="20260429T120000Z", seq=0,
    )
    # Schema-required core
    assert entry["link_id"] == "lk-20260429T120000Z-0000"
    assert entry["from_knowledge_id"] == "hb-card:card-a"
    assert entry["to_knowledge_id"] == "hb-card:card-b"
    assert entry["relation_type"] == "shares_principle"
    assert entry["rationale"] == "ok"
    assert entry["discovered_by"] == "propose-links"
    assert "discovered_at" in entry  # ISO string

    # v2 provenance (Cyberbrain v3 §3.2)
    assert entry["link_class"] == "proposed"
    assert entry["acceptance_state"] == "proposed"
    assert entry["scope_type"] == "whiteboard"
    assert entry["scope_whiteboard_id"] == "wb-1"
    assert entry["source_mode"] == "propose-links"
    assert entry["verified_by"] == "ai"
    assert entry["evidence_kind"] == []

    # v2 auto-accept fields stay null in Phase 2C
    assert entry["implicit_connection_detected"] is None
    assert entry["auto_accept_reason"] is None
    assert entry["auto_accept_confidence"] is None
    assert entry["promoted_from"] is None


def test_build_v2_entry_falls_back_to_no_rationale_string():
    """JSON schema requires rationale minLength 1; empty pair rationale
    must not fail validation."""
    pair = _enriched(rationale="")
    entry = build_v2_entry(
        pair, cards=_cards(), whiteboard_id="wb-1",
        run_timestamp="X", seq=0,
    )
    assert entry["rationale"] == "(no rationale)"


def test_build_v2_entry_propagates_needs_review():
    pair = _enriched(needs_review=True)
    entry = build_v2_entry(
        pair, cards=_cards(), whiteboard_id="wb-1",
        run_timestamp="X", seq=0,
    )
    assert entry["needs_taxonomy_review"] is True


def test_build_v2_entry_seq_zero_padded_to_four_digits():
    pair = _enriched()
    entry = build_v2_entry(
        pair, cards=_cards(), whiteboard_id="wb-1",
        run_timestamp="X", seq=42,
    )
    assert entry["link_id"] == "lk-X-0042"


# ---------- append_discovered_links ----------


def test_append_writes_eligible_skips_low_confidence(tmp_path: Path):
    reg = tmp_path / "_discovered_links.json"
    pairs = [
        _enriched(pair_id="p-0-1", i=0, j=1, confidence="high"),
        _enriched(pair_id="p-0-2", i=0, j=2, confidence="med"),
        _enriched(pair_id="p-1-2", i=1, j=2, confidence="low"),  # skipped
    ]
    report = append_discovered_links(
        reg, pairs, cards=_cards(), whiteboard_id="wb-1",
    )
    assert report["written"] == 2
    assert report["skipped"] == 1
    assert report["registry_size"] == 2
    assert report["invalid"] == []

    data = json.loads(reg.read_text(encoding="utf-8"))
    assert len(data) == 2
    rels = {e["from_knowledge_id"] + "→" + e["to_knowledge_id"] for e in data}
    assert rels == {"hb-card:card-a→hb-card:card-b",
                    "hb-card:card-a→hb-card:card-c"}


def test_append_excludes_existing_redundant_skipped_missing(tmp_path: Path):
    reg = tmp_path / "_discovered_links.json"
    pairs = [
        _enriched(pair_id="p-0-1", i=0, j=1, status="EXISTS",
                  pass2_skipped=True),
        _enriched(pair_id="p-0-2", i=0, j=2, status="REDUNDANT",
                  pass2_skipped=True),
        _enriched(pair_id="p-1-2", i=1, j=2, pass2_missing=True,
                  confidence="low"),
    ]
    report = append_discovered_links(
        reg, pairs, cards=_cards(), whiteboard_id="wb-1",
    )
    assert report["written"] == 0
    assert report["skipped"] == 3
    assert not reg.exists()  # nothing written → no file created


def test_append_to_existing_registry_preserves_old_entries(tmp_path: Path):
    reg = tmp_path / "_discovered_links.json"
    # Pre-populate with 2 valid entries
    seed = [
        {
            "link_id": "lk-OLD-0000",
            "from_knowledge_id": "hb-card:old-1",
            "to_knowledge_id": "hb-card:old-2",
            "relation_type": "supports",
            "rationale": "seeded",
            "discovered_at": "2026-01-01T00:00:00Z",
            "discovered_by": "manual",
        },
        {
            "link_id": "lk-OLD-0001",
            "from_knowledge_id": "hb-card:old-3",
            "to_knowledge_id": "hb-card:old-4",
            "relation_type": "contradicts",
            "rationale": "seeded2",
            "discovered_at": "2026-01-02T00:00:00Z",
            "discovered_by": "manual",
        },
    ]
    reg.write_text(json.dumps(seed), encoding="utf-8")

    pairs = [_enriched()]
    report = append_discovered_links(
        reg, pairs, cards=_cards(), whiteboard_id="wb-1",
    )
    assert report["written"] == 1
    assert report["registry_size"] == 3

    data = json.loads(reg.read_text(encoding="utf-8"))
    assert len(data) == 3
    assert data[0]["link_id"] == "lk-OLD-0000"
    assert data[1]["link_id"] == "lk-OLD-0001"
    assert data[2]["link_id"].startswith("lk-")


def test_append_no_eligible_pairs_does_not_touch_existing(tmp_path: Path):
    """Defensive: registry must not be rewritten when nothing eligible."""
    reg = tmp_path / "_discovered_links.json"
    seed = [{
        "link_id": "lk-OLD-0000",
        "from_knowledge_id": "hb-card:old-1",
        "to_knowledge_id": "hb-card:old-2",
        "relation_type": "supports",
        "rationale": "x",
        "discovered_at": "2026-01-01T00:00:00Z",
        "discovered_by": "manual",
    }]
    reg.write_text(json.dumps(seed), encoding="utf-8")
    mtime_before = reg.stat().st_mtime

    report = append_discovered_links(
        reg, [_enriched(confidence="low")],
        cards=_cards(), whiteboard_id="wb-1",
    )
    assert report["written"] == 0
    # File untouched
    assert reg.stat().st_mtime == mtime_before


def test_append_atomic_write_failure_preserves_original(tmp_path: Path):
    """Codex P1.1 from Phase 2A pattern: simulate atomic_write_json
    crash mid-write — original registry must remain valid.

    atomic_write_json uses os.replace which is atomic; we simulate
    failure of the underlying write by raising during atomic_write_json.
    """
    reg = tmp_path / "_discovered_links.json"
    seed = [{
        "link_id": "lk-OLD-0000",
        "from_knowledge_id": "hb-card:old-1",
        "to_knowledge_id": "hb-card:old-2",
        "relation_type": "supports",
        "rationale": "x",
        "discovered_at": "2026-01-01T00:00:00Z",
        "discovered_by": "manual",
    }]
    reg.write_text(json.dumps(seed), encoding="utf-8")
    original = reg.read_text(encoding="utf-8")

    with patch(
        "scripts.propose_links.discovered_links_writer.atomic_write_json",
        side_effect=OSError("simulated disk full"),
    ):
        with pytest.raises(OSError, match="simulated disk full"):
            append_discovered_links(
                reg, [_enriched()],
                cards=_cards(), whiteboard_id="wb-1",
            )
    # Original content intact
    assert reg.read_text(encoding="utf-8") == original


def test_append_corrupted_existing_registry_raises(tmp_path: Path):
    reg = tmp_path / "_discovered_links.json"
    reg.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        append_discovered_links(
            reg, [_enriched()],
            cards=_cards(), whiteboard_id="wb-1",
        )


def test_append_existing_registry_must_be_array(tmp_path: Path):
    reg = tmp_path / "_discovered_links.json"
    reg.write_text('{"not": "an array"}', encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON array"):
        append_discovered_links(
            reg, [_enriched()],
            cards=_cards(), whiteboard_id="wb-1",
        )


def test_append_invalid_relation_type_recorded_not_raised(tmp_path: Path):
    """If pass2_merge let through an invalid relation_type (shouldn't
    happen because it falls back to 'related_to'), validate_entry
    catches it. The writer surfaces it as 'invalid', does NOT raise."""
    reg = tmp_path / "_discovered_links.json"
    pairs = [_enriched(relation_type="invented_relation")]
    report = append_discovered_links(
        reg, pairs, cards=_cards(), whiteboard_id="wb-1",
    )
    assert report["written"] == 0
    assert len(report["invalid"]) == 1
    assert report["invalid"][0][0] == "p-0-1"


def test_append_run_timestamp_shared_across_seq(tmp_path: Path):
    """All entries from one append() call share the same run timestamp,
    differing only in seq (eases manual run-set audit)."""
    reg = tmp_path / "_discovered_links.json"
    pairs = [
        _enriched(pair_id="p-0-1", i=0, j=1),
        _enriched(pair_id="p-0-2", i=0, j=2),
    ]
    report = append_discovered_links(
        reg, pairs, cards=_cards(), whiteboard_id="wb-1",
        run_timestamp="20260429T130000Z",
    )
    data = json.loads(reg.read_text(encoding="utf-8"))
    assert data[0]["link_id"] == "lk-20260429T130000Z-0000"
    assert data[1]["link_id"] == "lk-20260429T130000Z-0001"


def test_append_origin_pair_id_preserved_for_audit(tmp_path: Path):
    reg = tmp_path / "_discovered_links.json"
    pairs = [_enriched(pair_id="p-7-9", i=0, j=1)]
    append_discovered_links(
        reg, pairs, cards=_cards(), whiteboard_id="wb-1",
    )
    data = json.loads(reg.read_text(encoding="utf-8"))
    assert data[0]["// origin_pair_id"] == "p-7-9"


def test_append_entry_validates_against_schema(tmp_path: Path):
    """End-to-end schema gate: every written entry must pass
    registry/schema.validate_entry."""
    from scripts.registry.schema import validate_entry
    reg = tmp_path / "_discovered_links.json"
    pairs = [_enriched()]
    append_discovered_links(
        reg, pairs, cards=_cards(), whiteboard_id="wb-1",
    )
    data = json.loads(reg.read_text(encoding="utf-8"))
    assert validate_entry(data[0]) == []
