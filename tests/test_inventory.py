import json
from pathlib import Path
from unittest.mock import MagicMock

from scripts.lib.mcp_client import FakeHeptabaseMCPClient
from scripts.propose_links.inventory import (
    ANALYZABLE_TYPES,
    build_inventory,
    classify_scale_tier,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mock_whiteboard_en_zh.json"


def _client() -> FakeHeptabaseMCPClient:
    return FakeHeptabaseMCPClient(FIXTURE)


# ---------- classify_scale_tier ----------


def test_tier_small_no_cluster_under_8():
    for n in (0, 1, 4, 7):
        assert classify_scale_tier(n) == "small_no_cluster"


def test_tier_normal_funnel_8_to_50():
    for n in (8, 11, 30, 50):
        assert classify_scale_tier(n) == "normal_funnel"


def test_tier_hard_stop_over_50():
    for n in (51, 100, 999):
        assert classify_scale_tier(n) == "hard_stop"


def test_analyzable_types_locked():
    assert ANALYZABLE_TYPES == frozenset(
        {"card", "pdfCard", "mediaCard", "highlightElement"}
    )


# ---------- build_inventory ----------


def test_inventory_filters_to_analyzable_types_only():
    inv = build_inventory("wb-mock-en-zh-001", _client())
    # 5 EN cards + 5 ZH cards + 1 pdfCard = 11 analyzable
    assert inv["card_count"] == 11
    for card in inv["cards"]:
        assert card["type"] in ANALYZABLE_TYPES


def test_inventory_records_skipped_by_type():
    inv = build_inventory("wb-mock-en-zh-001", _client())
    assert inv["skipped"].get("section") == 1
    assert inv["skipped"].get("image") == 1


def test_inventory_extracts_existing_connections():
    inv = build_inventory("wb-mock-en-zh-001", _client())
    assert len(inv["existing_connections"]) == 3
    edges = {(c["from"], c["to"]) for c in inv["existing_connections"]}
    assert ("card-en-1", "card-en-2") in edges


def test_inventory_scale_tier_normal_funnel_for_11_cards():
    inv = build_inventory("wb-mock-en-zh-001", _client())
    assert inv["scale_tier"] == "normal_funnel"


def test_inventory_scale_tier_small_no_cluster_for_tiny_whiteboard():
    inv = build_inventory("wb-mock-tiny-001", _client())
    assert inv["card_count"] == 4
    assert inv["scale_tier"] == "small_no_cluster"


def test_inventory_passes_through_metadata():
    inv = build_inventory("wb-mock-en-zh-001", _client())
    assert inv["whiteboard_id"] == "wb-mock-en-zh-001"
    assert "EN+ZH" in inv["whiteboard_name"]


def test_inventory_hard_stop_with_synthetic_51_cards():
    fake_client = MagicMock()
    fake_client.get_whiteboard_with_objects.return_value = {
        "id": "wb-syn-large",
        "name": "Large",
        "objects": [
            {"id": f"c{i}", "type": "card", "title": f"T{i}", "content": "x", "tags": []}
            for i in range(51)
        ],
        "connections": [],
    }
    inv = build_inventory("wb-syn-large", fake_client)
    assert inv["card_count"] == 51
    assert inv["scale_tier"] == "hard_stop"


def test_inventory_unknown_object_type_grouped_under_actual_type():
    fake_client = MagicMock()
    fake_client.get_whiteboard_with_objects.return_value = {
        "id": "wb-x",
        "name": "X",
        "objects": [
            {"id": "card-1", "type": "card", "title": "ok", "content": "x", "tags": []},
            {"id": "weird-1", "type": "futureType", "data": {}},
            {"id": "weird-2", "type": "futureType", "data": {}},
        ],
        "connections": [],
    }
    inv = build_inventory("wb-x", fake_client)
    assert inv["card_count"] == 1
    assert inv["skipped"]["futureType"] == 2


def test_inventory_object_missing_type_field_skipped_as_unknown():
    fake_client = MagicMock()
    fake_client.get_whiteboard_with_objects.return_value = {
        "id": "wb-x",
        "name": "X",
        "objects": [{"id": "no-type-1"}],
        "connections": [],
    }
    inv = build_inventory("wb-x", fake_client)
    assert inv["card_count"] == 0
    assert inv["skipped"].get("unknown") == 1


def test_inventory_empty_whiteboard():
    fake_client = MagicMock()
    fake_client.get_whiteboard_with_objects.return_value = {
        "id": "wb-empty",
        "name": "Empty",
        "objects": [],
        "connections": [],
    }
    inv = build_inventory("wb-empty", fake_client)
    assert inv["card_count"] == 0
    assert inv["scale_tier"] == "small_no_cluster"
    assert inv["existing_connections"] == []
    assert inv["skipped"] == {}
