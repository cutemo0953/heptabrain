import json
from pathlib import Path
from unittest.mock import MagicMock

from scripts.lib.mcp_client import FakeHeptabaseMCPClient
from scripts.propose_links.inventory import build_inventory
from scripts.propose_links.maturity_detect import (
    detect_maturity,
    _density_heuristic,
    _probe_meta_card,
    _probe_title,
)
from scripts.registry.whiteboard_maturity import set_maturity

FIXTURE = Path(__file__).parent / "fixtures" / "mock_whiteboard_en_zh.json"


def _client() -> FakeHeptabaseMCPClient:
    return FakeHeptabaseMCPClient(FIXTURE)


# ---------- density heuristic ----------


def test_density_seed_under_5():
    for n in (0, 1, 4):
        assert _density_heuristic(n) == "seed"


def test_density_forming_5_to_15():
    for n in (5, 10, 15):
        assert _density_heuristic(n) == "forming"


def test_density_structured_16_to_40():
    for n in (16, 25, 40):
        assert _density_heuristic(n) == "structured"


def test_density_above_40_returns_structured():
    # density alone cannot tell canonical apart; must come from registry/meta/title
    assert _density_heuristic(100) == "structured"


# ---------- meta-card probe ----------


def test_meta_card_with_valid_maturity():
    cards = [
        {
            "id": "m1",
            "title": "⚙️ Meta",
            "content": "---\nmaturity: structured\nlast_reviewed: 2026\n---",
        }
    ]
    assert _probe_meta_card(cards) == "structured"


def test_meta_card_case_insensitive_value():
    cards = [{"id": "m1", "title": "⚙️ Meta", "content": "maturity: FORMING"}]
    assert _probe_meta_card(cards) == "forming"


def test_meta_card_invalid_maturity_falls_through():
    cards = [{"id": "m1", "title": "⚙️ Meta", "content": "maturity: legendary"}]
    assert _probe_meta_card(cards) is None


def test_meta_card_no_maturity_field_falls_through():
    cards = [{"id": "m1", "title": "⚙️ Meta", "content": "no yaml here"}]
    assert _probe_meta_card(cards) is None


def test_no_meta_card_returns_none():
    cards = [{"id": "c1", "title": "regular", "content": "x"}]
    assert _probe_meta_card(cards) is None


def test_meta_card_with_no_title_field_skipped():
    cards = [{"id": "m1", "content": "maturity: forming"}]
    assert _probe_meta_card(cards) is None


# ---------- title probe ----------


def test_title_with_maturity_marker():
    assert _probe_title("Project [maturity:forming]") == "forming"


def test_title_case_insensitive():
    assert _probe_title("Project [MATURITY: structured]") == "structured"


def test_title_without_marker_returns_none():
    assert _probe_title("Just a project name") is None


def test_title_with_invalid_maturity_returns_none():
    # regex enum-restricted — invalid value doesn't match
    assert _probe_title("Project [maturity:legendary]") is None


# ---------- detect_maturity precedence ----------


def test_precedence_registry_wins(tmp_path: Path):
    reg_path = tmp_path / "m.json"
    set_maturity("wb-mock-en-zh-001", "canonical", "manual", reg_path)

    inv = build_inventory("wb-mock-en-zh-001", _client())
    assert detect_maturity(inv, reg_path) == ("canonical", "manual")


def test_precedence_meta_card_when_no_registry_hit(tmp_path: Path):
    inv = build_inventory("wb-mock-meta-001", _client())
    # registry empty, fixture's meta-card-1 has maturity: structured
    assert detect_maturity(inv, tmp_path / "missing.json") == (
        "structured",
        "meta_card",
    )


def test_precedence_title_when_no_meta_card(tmp_path: Path):
    inv = build_inventory("wb-mock-title-maturity-001", _client())
    assert detect_maturity(inv, tmp_path / "missing.json") == (
        "forming",
        "title",
    )


def test_precedence_density_fallback_when_all_layers_miss(tmp_path: Path):
    inv = build_inventory("wb-mock-tiny-001", _client())
    # 4 cards, no meta, no title marker, registry missing
    assert detect_maturity(inv, tmp_path / "missing.json") == (
        "seed",
        "heuristic",
    )


def test_precedence_density_normal_funnel_count(tmp_path: Path):
    inv = build_inventory("wb-mock-en-zh-001", _client())
    # 11 analyzable cards, no meta in this fixture, no title marker
    assert detect_maturity(inv, tmp_path / "missing.json") == (
        "forming",
        "heuristic",
    )


def test_registry_path_none_skips_layer1(tmp_path: Path):
    # explicit None means caller deliberately skipping registry
    inv = build_inventory("wb-mock-meta-001", _client())
    assert detect_maturity(inv, None) == ("structured", "meta_card")


def test_registry_load_error_falls_through(tmp_path: Path, caplog):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("not valid json {{{", encoding="utf-8")
    inv = build_inventory("wb-mock-meta-001", _client())
    result = detect_maturity(inv, bad_path)
    # falls through to meta_card layer, doesn't crash
    assert result == ("structured", "meta_card")


# ---------- stale registry entry fall-through (Codex P1 #4 fix) ----------


def test_stale_registry_entry_falls_through_to_next_layer(tmp_path: Path, caplog):
    import logging
    from datetime import datetime, timedelta, timezone
    from scripts.registry.whiteboard_maturity import STALE_REVIEW_DAYS

    reg_path = tmp_path / "m.json"
    # Set maturity with a timestamp older than the stale threshold
    old_ts = datetime.now(timezone.utc) - timedelta(days=STALE_REVIEW_DAYS + 5)
    set_maturity(
        "wb-mock-meta-001",
        "canonical",
        "manual",
        reg_path,
        now=old_ts,
    )

    inv = build_inventory("wb-mock-meta-001", _client())  # this WB has a meta card
    with caplog.at_level(logging.WARNING):
        result = detect_maturity(inv, reg_path)

    # Should fall through to meta_card layer (NOT return the stale registry value)
    assert result == ("structured", "meta_card")
    assert any("stale" in r.message.lower() for r in caplog.records)


def test_fresh_registry_entry_still_wins(tmp_path: Path):
    reg_path = tmp_path / "m.json"
    set_maturity("wb-mock-meta-001", "canonical", "manual", reg_path)
    inv = build_inventory("wb-mock-meta-001", _client())
    # Fresh entry → registry wins over meta card
    assert detect_maturity(inv, reg_path) == ("canonical", "manual")
