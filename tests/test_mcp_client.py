from pathlib import Path

import pytest

from scripts.lib.mcp_client import (
    FakeHeptabaseMCPClient,
    HeptabaseMCPClient,
    MCPClient,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mock_whiteboard_en_zh.json"


def _client() -> FakeHeptabaseMCPClient:
    return FakeHeptabaseMCPClient(FIXTURE)


# ---------- Fake search_whiteboards ----------


def test_search_by_id_exact():
    result = _client().search_whiteboards("wb-mock-en-zh-001")
    assert len(result) == 1
    assert result[0]["id"] == "wb-mock-en-zh-001"


def test_search_by_keyword_partial_case_insensitive():
    result = _client().search_whiteboards("EN+ZH")
    assert len(result) == 1
    assert "EN+ZH" in result[0]["name"]


def test_search_by_keyword_multi_match():
    result = _client().search_whiteboards("Mock")
    # all 5 fixture whiteboards have "Mock" in name
    assert len(result) == 5


def test_search_no_match_returns_empty():
    assert _client().search_whiteboards("nonexistent-keyword-xyz") == []


def test_search_empty_keyword_returns_empty():
    assert _client().search_whiteboards("") == []


# ---------- Fake get_whiteboard_with_objects ----------


def test_get_whiteboard_returns_objects_and_connections():
    wb = _client().get_whiteboard_with_objects("wb-mock-en-zh-001")
    assert wb["id"] == "wb-mock-en-zh-001"
    # 5 EN cards + 5 ZH cards + 1 section + 1 image + 1 pdfCard
    assert len(wb["objects"]) == 13
    assert len(wb["connections"]) == 3


def test_get_whiteboard_missing_raises():
    with pytest.raises(LookupError):
        _client().get_whiteboard_with_objects("wb-does-not-exist")


def test_get_whiteboard_returns_copies_not_references():
    wb1 = _client().get_whiteboard_with_objects("wb-mock-en-zh-001")
    wb1["objects"].append({"id": "mutation"})
    wb2 = _client().get_whiteboard_with_objects("wb-mock-en-zh-001")
    assert len(wb2["objects"]) == 13


# ---------- Fake get_object ----------


def test_get_object_returns_card():
    obj = _client().get_object("card-en-1")
    assert obj["type"] == "card"
    assert "Feedback Loop" in obj["title"]


def test_get_object_returns_pdfcard():
    obj = _client().get_object("pdf-1")
    assert obj["type"] == "pdfCard"


def test_get_object_missing_raises():
    with pytest.raises(LookupError):
        _client().get_object("does-not-exist")


def test_get_object_returns_copy_not_reference():
    o1 = _client().get_object("card-en-1")
    o1["title"] = "MUTATED"
    o2 = _client().get_object("card-en-1")
    assert o2["title"] != "MUTATED"


# ---------- Real client smoke (fail-loud expectations) ----------


def test_real_client_methods_raise_not_implemented():
    real = HeptabaseMCPClient()
    for fn, args in (
        (real.search_whiteboards, ("k",)),
        (real.get_whiteboard_with_objects, ("id",)),
        (real.get_object, ("id",)),
    ):
        with pytest.raises(NotImplementedError, match="Real MCPClient"):
            fn(*args)


def test_fake_satisfies_protocol():
    # structural typing — both classes satisfy MCPClient
    fake: MCPClient = _client()
    real: MCPClient = HeptabaseMCPClient()
    assert hasattr(fake, "search_whiteboards")
    assert hasattr(real, "search_whiteboards")
