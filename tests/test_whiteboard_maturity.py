import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.registry.whiteboard_maturity import (
    REGISTRY_VERSION,
    SOURCE_AUTHORITY,
    STALE_REVIEW_DAYS,
    VALID_MATURITIES,
    VALID_SOURCES,
    find_stale_entries,
    get_maturity,
    is_stale,
    load_maturity_registry,
    set_maturity,
)


# ---------- load ----------


def test_load_missing_file_returns_empty(tmp_path: Path):
    reg = load_maturity_registry(tmp_path / "does-not-exist.json")
    assert reg == {"version": REGISTRY_VERSION, "whiteboards": []}


def test_load_existing_file(tmp_path: Path):
    p = tmp_path / "m.json"
    p.write_text(
        json.dumps(
            {
                "version": "1.0",
                "whiteboards": [
                    {
                        "whiteboard_id": "wb-1",
                        "maturity": "forming",
                        "maturity_source": "manual",
                        "last_maturity_reviewed_at": "2026-04-24T11:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    reg = load_maturity_registry(p)
    assert len(reg["whiteboards"]) == 1


# ---------- get ----------


def test_get_maturity_hit():
    reg = {
        "version": "1.0",
        "whiteboards": [
            {
                "whiteboard_id": "wb-1",
                "maturity": "forming",
                "maturity_source": "heuristic",
                "last_maturity_reviewed_at": "2026-04-24T11:00:00+00:00",
            }
        ],
    }
    result = get_maturity("wb-1", reg)
    assert result == ("forming", "heuristic")


def test_get_maturity_miss_returns_none():
    assert get_maturity("wb-absent", {"version": "1.0", "whiteboards": []}) is None


# ---------- set ----------


def test_set_maturity_new_entry(tmp_path: Path):
    p = tmp_path / "m.json"
    result = set_maturity("wb-new", "forming", "manual", p)
    assert result["applied"] is True
    assert result["outcome"] == "created"
    assert get_maturity("wb-new", result["registry"]) == ("forming", "manual")

    on_disk = load_maturity_registry(p)
    assert get_maturity("wb-new", on_disk) == ("forming", "manual")


def test_set_maturity_upgrade_overwrites(tmp_path: Path):
    p = tmp_path / "m.json"
    set_maturity("wb-1", "seed", "heuristic", p)
    result = set_maturity("wb-1", "forming", "manual", p)  # manual > heuristic
    assert result["applied"] is True
    assert result["outcome"] == "replaced"

    reg = load_maturity_registry(p)
    assert get_maturity("wb-1", reg) == ("forming", "manual")
    assert len(reg["whiteboards"]) == 1


def test_lower_authority_source_does_not_overwrite_higher(tmp_path: Path):
    p = tmp_path / "m.json"
    set_maturity("wb-1", "forming", "manual", p)
    result = set_maturity("wb-1", "seed", "heuristic", p)  # heuristic < manual

    assert result["applied"] is False
    assert result["outcome"] == "suppressed"
    assert result["reason"] is not None
    assert "heuristic" in result["reason"]
    assert result["suppressed_by"]["source"] == "manual"

    reg = load_maturity_registry(p)
    assert get_maturity("wb-1", reg) == ("forming", "manual")


def test_suppressed_write_does_not_touch_disk(tmp_path: Path):
    p = tmp_path / "m.json"
    set_maturity("wb-1", "forming", "manual", p)
    mtime_before = p.stat().st_mtime_ns
    result = set_maturity("wb-1", "seed", "heuristic", p)
    assert result["outcome"] == "suppressed"
    assert p.stat().st_mtime_ns == mtime_before


def test_equal_authority_source_replaces_with_fresh_timestamp(tmp_path: Path):
    p = tmp_path / "m.json"
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new = datetime(2026, 4, 24, tzinfo=timezone.utc)
    set_maturity("wb-1", "seed", "heuristic", p, now=old)
    result = set_maturity("wb-1", "forming", "heuristic", p, now=new)
    assert result["outcome"] == "replaced"

    reg = load_maturity_registry(p)
    entry = reg["whiteboards"][0]
    assert entry["maturity"] == "forming"
    assert entry["last_maturity_reviewed_at"].startswith("2026-04-24")


def test_set_maturity_rejects_invalid_maturity(tmp_path: Path):
    with pytest.raises(ValueError):
        set_maturity("wb-1", "mature", "manual", tmp_path / "m.json")


def test_set_maturity_rejects_invalid_source(tmp_path: Path):
    with pytest.raises(ValueError):
        set_maturity("wb-1", "forming", "intuition", tmp_path / "m.json")


def test_set_maturity_records_note(tmp_path: Path):
    p = tmp_path / "m.json"
    set_maturity("wb-1", "forming", "manual", p, note="user tagged 2026-04-25")
    reg = load_maturity_registry(p)
    assert reg["whiteboards"][0]["note"] == "user tagged 2026-04-25"


# ---------- constants ----------


def test_valid_maturities_match_spec():
    assert VALID_MATURITIES == frozenset({"seed", "forming", "structured", "canonical"})


def test_valid_sources_match_spec():
    assert VALID_SOURCES == frozenset({"manual", "heuristic", "meta_card", "title"})


def test_source_authority_ordering():
    assert (
        SOURCE_AUTHORITY["manual"]
        > SOURCE_AUTHORITY["meta_card"]
        > SOURCE_AUTHORITY["heuristic"]
        > SOURCE_AUTHORITY["title"]
    )


# ---------- stale ----------


def test_is_stale_past_threshold():
    entry = {"last_maturity_reviewed_at": "2026-01-01T00:00:00+00:00"}
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    assert is_stale(entry, now=now)


def test_is_stale_within_threshold():
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    recent = (now - timedelta(days=10)).isoformat()
    assert not is_stale({"last_maturity_reviewed_at": recent}, now=now)


def test_is_stale_missing_timestamp_treated_as_stale():
    assert is_stale({})


def test_stale_threshold_is_ninety_days():
    assert STALE_REVIEW_DAYS == 90


def test_find_stale_entries(tmp_path: Path):
    p = tmp_path / "m.json"
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    r1 = set_maturity("wb-fresh", "forming", "manual", p, now=now)
    r2 = set_maturity(
        "wb-old", "seed", "heuristic", p, now=now - timedelta(days=STALE_REVIEW_DAYS + 1)
    )
    assert r1["applied"] and r2["applied"]

    reg = load_maturity_registry(p)
    stale = find_stale_entries(reg, now=now)
    stale_ids = {e["whiteboard_id"] for e in stale}
    assert stale_ids == {"wb-old"}
