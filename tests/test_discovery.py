from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.lib.mcp_client import FakeHeptabaseMCPClient
from scripts.propose_links.discovery import (
    AmbiguousWhiteboardError,
    WhiteboardNotFoundError,
    discover_whiteboard,
    pick_unique,
    search_whiteboards,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mock_whiteboard_en_zh.json"


def _client() -> FakeHeptabaseMCPClient:
    return FakeHeptabaseMCPClient(FIXTURE)


def test_search_returns_matches():
    matches = search_whiteboards(_client(), "EN+ZH")
    assert len(matches) == 1


def test_pick_unique_passes_through_single():
    match = pick_unique([{"id": "wb-1", "name": "X"}], "kw")
    assert match["id"] == "wb-1"


def test_pick_unique_raises_on_zero():
    with pytest.raises(WhiteboardNotFoundError, match="no whiteboard matched"):
        pick_unique([], "kw")


def test_pick_unique_raises_on_multiple_with_match_list():
    with pytest.raises(AmbiguousWhiteboardError) as excinfo:
        pick_unique(
            [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            "shared",
        )
    assert excinfo.value.keyword == "shared"
    assert len(excinfo.value.matches) == 2


def test_discover_whiteboard_by_id_exact():
    wb = discover_whiteboard(_client(), "wb-mock-en-zh-001")
    assert wb["id"] == "wb-mock-en-zh-001"


def test_discover_whiteboard_by_unique_keyword():
    wb = discover_whiteboard(_client(), "EN+ZH")
    assert wb["id"] == "wb-mock-en-zh-001"


def test_discover_whiteboard_ambiguous_keyword():
    # "Mock" matches all 5 fixture whiteboards
    with pytest.raises(AmbiguousWhiteboardError) as excinfo:
        discover_whiteboard(_client(), "Mock")
    assert len(excinfo.value.matches) == 5


def test_discover_whiteboard_no_match():
    with pytest.raises(WhiteboardNotFoundError):
        discover_whiteboard(_client(), "nonexistent-keyword-xyz")


def test_discover_whiteboard_empty_keyword_raises():
    with pytest.raises(ValueError, match="empty"):
        discover_whiteboard(_client(), "")


def test_discover_whiteboard_whitespace_only_raises():
    with pytest.raises(ValueError, match="empty"):
        discover_whiteboard(_client(), "   ")


def test_ambiguous_error_message_truncates_at_5():
    matches = [{"id": f"wb-{i}", "name": f"name {i}"} for i in range(8)]
    err = AmbiguousWhiteboardError("shared", matches)
    msg = str(err)
    assert "matched 8 whiteboards" in msg
    assert "+3 more" in msg


# ---------- direct id-fetch path (Codex P1 #2 fix) ----------


def test_discover_uses_direct_id_fetch_first():
    """If client.get_whiteboard_with_objects(id) succeeds, skip search."""
    fake = MagicMock()
    fake.get_whiteboard_with_objects.return_value = {"id": "wb-123", "name": "Direct"}
    fake.search_whiteboards.return_value = []
    wb = discover_whiteboard(fake, "wb-123")
    assert wb == {"id": "wb-123", "name": "Direct"}
    fake.get_whiteboard_with_objects.assert_called_once_with("wb-123")
    fake.search_whiteboards.assert_not_called()


def test_discover_falls_back_to_search_when_id_fetch_fails():
    fake = MagicMock()
    fake.get_whiteboard_with_objects.side_effect = LookupError("not found")
    fake.search_whiteboards.return_value = [{"id": "wb-x", "name": "via search"}]
    wb = discover_whiteboard(fake, "some-keyword")
    assert wb == {"id": "wb-x", "name": "via search"}
    fake.search_whiteboards.assert_called_once_with("some-keyword")


def test_discover_propagates_notimplemented_from_real_client():
    fake = MagicMock()
    fake.get_whiteboard_with_objects.side_effect = NotImplementedError(
        "Real MCPClient ... must be wired"
    )
    with pytest.raises(NotImplementedError):
        discover_whiteboard(fake, "wb-x")
