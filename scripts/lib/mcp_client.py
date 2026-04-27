"""Heptabase MCP client wrapper.

Defines the minimal interface our Phase 1 modules call. Two
implementations:

- `HeptabaseMCPClient`: real wrapper around the Claude Code Heptabase
  MCP tools. Phase 1 dry-run uses this only for the final
  human-driven smoke test against a real whiteboard.
- `FakeHeptabaseMCPClient`: in-memory implementation backed by a
  fixture JSON file. Used by all unit tests.

Both implement the same `MCPClient` Protocol so callers can be
typed against the abstraction.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class MCPClient(Protocol):
    def search_whiteboards(self, keyword: str) -> list[dict[str, Any]]: ...
    def get_whiteboard_with_objects(self, whiteboard_id: str) -> dict[str, Any]: ...
    def get_object(self, object_id: str) -> dict[str, Any]: ...


class HeptabaseMCPClient:
    """Real MCP client.

    Phase 1 does NOT execute against a real Heptabase from any unit
    test — this class exists for the human-driven smoke run only.
    The actual MCP tool invocations happen at the Claude Code call
    site; this class documents the expected response shape.
    """

    def search_whiteboards(self, keyword: str) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Real MCPClient.search_whiteboards must be wired at call site via "
            "mcp__heptabase-mcp__search_whiteboards. Phase 1 unit tests use "
            "FakeHeptabaseMCPClient; smoke run injects the live tool."
        )

    def get_whiteboard_with_objects(self, whiteboard_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Real MCPClient.get_whiteboard_with_objects must be wired at call "
            "site via mcp__heptabase-mcp__get_whiteboard_with_objects."
        )

    def get_object(self, object_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Real MCPClient.get_object must be wired at call site via "
            "mcp__heptabase-mcp__get_object."
        )


class FakeHeptabaseMCPClient:
    """Fixture-backed client for unit tests.

    Loads the fixture once at construction. All lookups are
    in-memory. Whiteboards are matched by exact id or by case-
    insensitive substring on name (mirrors how a real keyword
    search behaves).
    """

    def __init__(self, fixture_path: Path | str):
        path = Path(fixture_path)
        with path.open("r", encoding="utf-8") as f:
            self._data = json.load(f)
        self._whiteboards = self._data["whiteboards"]
        self._objects_by_id: dict[str, dict[str, Any]] = {}
        for wb in self._whiteboards:
            for obj in wb.get("objects", []):
                self._objects_by_id[obj["id"]] = obj

    def search_whiteboards(self, keyword: str) -> list[dict[str, Any]]:
        if not keyword:
            return []
        kw_lower = keyword.lower()
        matches = []
        for wb in self._whiteboards:
            if wb["id"] == keyword:
                matches.append({"id": wb["id"], "name": wb["name"]})
            elif kw_lower in wb["name"].lower():
                matches.append({"id": wb["id"], "name": wb["name"]})
        return matches

    def get_whiteboard_with_objects(self, whiteboard_id: str) -> dict[str, Any]:
        for wb in self._whiteboards:
            if wb["id"] == whiteboard_id:
                return {
                    "id": wb["id"],
                    "name": wb["name"],
                    "objects": list(wb.get("objects", [])),
                    "connections": list(wb.get("connections", [])),
                }
        raise LookupError(f"whiteboard not found: {whiteboard_id!r}")

    def get_object(self, object_id: str) -> dict[str, Any]:
        if object_id not in self._objects_by_id:
            raise LookupError(f"object not found: {object_id!r}")
        return dict(self._objects_by_id[object_id])
