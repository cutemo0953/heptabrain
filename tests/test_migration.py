import json
from pathlib import Path

from scripts.registry.migration import (
    commit_lazy_writeback,
    fallback_legacy_entry,
    generate_migration_report,
)
from scripts.registry.schema import is_v2_complete


def _legacy_zettel_entry() -> dict:
    return {
        "link_id": "lk-legacy-001",
        "from_knowledge_id": "kb-a",
        "to_knowledge_id": "kb-b",
        "relation_type": "shares_principle",
        "rationale": "both exhibit feedback loops",
        "evidence_refs": ["KB Safety-II p3", "Heptabase card: E-P-E-R §2"],
        "novelty_score": 0.8,
        "evidence_score": 0.7,
        "review_state": "accepted",
        "discovered_at": "2026-04-06T15:00:00+08:00",
        "discovered_by": "zettel-walk wander",
    }


def _legacy_manual_entry() -> dict:
    e = _legacy_zettel_entry()
    e.update(
        {
            "link_id": "lk-legacy-002",
            "review_state": None,
            "discovered_by": "manual",
            "evidence_refs": [],
        }
    )
    return e


def _legacy_propose_entry() -> dict:
    e = _legacy_zettel_entry()
    e.update(
        {
            "link_id": "lk-legacy-003",
            "discovered_by": "propose-links",
            "review_state": "proposed",
            "evidence_refs": [],
        }
    )
    return e


# ---------- fallback_legacy_entry ----------


def test_zettel_fallback_sets_proposed_class():
    out = fallback_legacy_entry(_legacy_zettel_entry())
    assert out["link_class"] == "proposed"


def test_zettel_fallback_scope_cross_whiteboard():
    out = fallback_legacy_entry(_legacy_zettel_entry())
    assert out["scope_type"] == "cross_whiteboard"


def test_zettel_fallback_source_mode_colonized():
    out = fallback_legacy_entry(_legacy_zettel_entry())
    assert out["source_mode"] == "zettel-walk:wander"


def test_zettel_fallback_evidence_kind_kb_detection():
    out = fallback_legacy_entry(_legacy_zettel_entry())
    assert out["evidence_kind"] == ["text_overlap"]


def test_manual_fallback_sets_canonical_class():
    out = fallback_legacy_entry(_legacy_manual_entry())
    assert out["link_class"] == "canonical"


def test_propose_links_fallback_sets_whiteboard_scope():
    out = fallback_legacy_entry(_legacy_propose_entry())
    assert out["scope_type"] == "whiteboard"
    assert out["source_mode"] == "propose-links"


def test_fallback_maps_review_state_to_acceptance_state():
    out = fallback_legacy_entry(_legacy_zettel_entry())
    assert out["acceptance_state"] == "accepted"


def test_fallback_acceptance_defaults_to_proposed_when_missing():
    entry = _legacy_zettel_entry()
    entry["review_state"] = None
    out = fallback_legacy_entry(entry)
    assert out["acceptance_state"] == "proposed"


def test_fallback_last_verified_at_from_discovered_at():
    out = fallback_legacy_entry(_legacy_zettel_entry())
    assert out["last_verified_at"] == "2026-04-06T15:00:00+08:00"


def test_fallback_verified_by_ai_default():
    out = fallback_legacy_entry(_legacy_zettel_entry())
    assert out["verified_by"] == "ai"


def test_fallback_fills_auto_accept_fields_as_null():
    out = fallback_legacy_entry(_legacy_zettel_entry())
    for field in (
        "implicit_connection_detected",
        "auto_accept_reason",
        "auto_accept_confidence",
        "promoted_from",
    ):
        assert field in out
        assert out[field] is None


def test_fallback_enriched_entry_is_v2_complete():
    out = fallback_legacy_entry(_legacy_zettel_entry())
    assert is_v2_complete(out)


def test_fallback_does_not_mutate_input():
    entry = _legacy_zettel_entry()
    snapshot = json.dumps(entry, sort_keys=True)
    fallback_legacy_entry(entry)
    assert json.dumps(entry, sort_keys=True) == snapshot


def test_fallback_preserves_existing_v2_fields():
    entry = _legacy_zettel_entry()
    entry["link_class"] = "exploratory"
    entry["scope_type"] = "whiteboard"
    out = fallback_legacy_entry(entry)
    assert out["link_class"] == "exploratory"
    assert out["scope_type"] == "whiteboard"


def test_evidence_kind_empty_when_no_kb():
    entry = _legacy_zettel_entry()
    entry["evidence_refs"] = ["personal note 1"]
    out = fallback_legacy_entry(entry)
    assert out["evidence_kind"] == []


# ---------- generate_migration_report ----------


def _write_registry(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "_discovered_links.json"
    p.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def test_report_counts_legacy_entries(tmp_path: Path):
    reg = _write_registry(
        tmp_path,
        [_legacy_zettel_entry(), _legacy_manual_entry(), _legacy_propose_entry()],
    )
    report = generate_migration_report(reg)
    assert "Total entries: 3" in report
    assert "Needs normalization: 3" in report


def test_report_does_not_modify_main_file(tmp_path: Path):
    reg = _write_registry(tmp_path, [_legacy_zettel_entry()])
    before = reg.read_bytes()
    generate_migration_report(reg)
    after = reg.read_bytes()
    assert before == after


def test_report_flags_manual_without_review_state(tmp_path: Path):
    reg = _write_registry(tmp_path, [_legacy_manual_entry()])
    report = generate_migration_report(reg)
    assert "review_state missing" in report


def test_report_flags_empty_discovered_by(tmp_path: Path):
    entry = _legacy_zettel_entry()
    entry["discovered_by"] = ""
    reg = _write_registry(tmp_path, [entry])
    report = generate_migration_report(reg)
    assert "discovered_by empty" in report


def test_report_captures_fallback_distribution(tmp_path: Path):
    reg = _write_registry(
        tmp_path,
        [_legacy_zettel_entry(), _legacy_manual_entry(), _legacy_propose_entry()],
    )
    report = generate_migration_report(reg)
    assert "canonical (from `manual` heuristic): 1" in report
    assert "proposed (default): 2" in report
    assert "whiteboard (from `propose-links` heuristic): 1" in report
    assert "cross_whiteboard (default): 2" in report


# ---------- commit_lazy_writeback ----------


def test_commit_normalizes_main_file(tmp_path: Path):
    reg = _write_registry(tmp_path, [_legacy_zettel_entry()])
    commit_lazy_writeback(reg)
    normalized = json.loads(reg.read_text(encoding="utf-8"))
    assert is_v2_complete(normalized[0])


def test_commit_creates_backup(tmp_path: Path):
    reg = _write_registry(tmp_path, [_legacy_zettel_entry()])
    backup = commit_lazy_writeback(reg)
    assert backup.exists()
    backed_up = json.loads(backup.read_text(encoding="utf-8"))
    # backup should be the raw original entries (no fallback applied)
    assert "link_class" not in backed_up[0] or backed_up[0].get("link_class") is None


def test_commit_backup_suffix_format(tmp_path: Path):
    reg = _write_registry(tmp_path, [_legacy_zettel_entry()])
    backup = commit_lazy_writeback(reg)
    # Spec §3.2: `_discovered_links.json.v2.1-backup-<ts>.json`
    assert backup.name.startswith("_discovered_links.json.v2.1-backup-")
    assert backup.name.endswith(".json")
