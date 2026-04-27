"""Whiteboard discovery — translate keyword/id input into a single
whiteboard match.

Stateless functions; CLI handles user-facing disambiguation.
"""
from __future__ import annotations

from typing import Any

from scripts.lib.mcp_client import MCPClient


class WhiteboardNotFoundError(LookupError):
    """No whiteboard matched the given keyword or id."""


class AmbiguousWhiteboardError(LookupError):
    """More than one whiteboard matched. Caller should disambiguate."""

    def __init__(self, keyword: str, matches: list[dict[str, Any]]):
        self.keyword = keyword
        self.matches = matches
        names = ", ".join(f"{m['id']} ({m['name']})" for m in matches[:5])
        more = f" (+{len(matches) - 5} more)" if len(matches) > 5 else ""
        super().__init__(
            f"keyword {keyword!r} matched {len(matches)} whiteboards: {names}{more}"
        )


def search_whiteboards(client: MCPClient, keyword: str) -> list[dict[str, Any]]:
    return client.search_whiteboards(keyword)


def pick_unique(
    matches: list[dict[str, Any]], keyword: str
) -> dict[str, Any]:
    if not matches:
        raise WhiteboardNotFoundError(f"no whiteboard matched: {keyword!r}")
    if len(matches) > 1:
        raise AmbiguousWhiteboardError(keyword, matches)
    return matches[0]


def discover_whiteboard(
    client: MCPClient, keyword_or_id: str
) -> dict[str, Any]:
    """Convenience wrapper for the common case where a single match is
    expected.

    Per Codex P1 review 2026-04-27: tries direct id-fetch first (the
    spec/plan path for known ids), then falls back to keyword search.
    A live MCP `search_whiteboards` may not accept exact ids the way
    `FakeHeptabaseMCPClient` does.

    Raises on 0 or >1 matches; CLI catches and prompts.
    """
    if not keyword_or_id or not keyword_or_id.strip():
        raise ValueError("keyword_or_id is empty")
    raw = keyword_or_id.strip()

    # Try direct id-fetch first
    try:
        wb = client.get_whiteboard_with_objects(raw)
    except (LookupError, KeyError):
        pass
    except NotImplementedError:
        # Real client without wiring — propagate so CLI surfaces it
        raise
    else:
        return {"id": wb["id"], "name": wb.get("name", "")}

    # Fall back to keyword search
    matches = search_whiteboards(client, raw)
    return pick_unique(matches, raw)
