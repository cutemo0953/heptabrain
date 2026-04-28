"""LLM client Protocol for propose-links Pass 2.

Phase 2A scope: this module deliberately does NOT call any external LLM
API. The real "LLM" is Claude running the propose-links skill
(`.claude/commands/propose-links.md`); the skill writes Pass 2 results to
a JSON file, and Phase 2 Python code reads that file. This Protocol
exists so the merge logic can be typed against an abstraction and so
unit tests can substitute a fixture-backed implementation.

Per IMPLEMENTATION_PLAN_PHASE_2.md §2A.1 — "Python doesn't call LLMs".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class LLMClient(Protocol):
    def analyze_pair(self, pair: dict[str, Any]) -> dict[str, Any]: ...


class FixtureLLMClient:
    """Loads pre-recorded analyses keyed by pair_id from a fixture JSON.

    Fixture shape (matches the --with-pass2 envelope so the same file
    can power both unit tests and the live skill):
        {"whiteboard_id": "wb-...",
         "analyses": [
            {"pair_id": "p-0-1", "from_id": "card-x", "to_id": "card-y",
             "relation_type": "shares_principle",
             "rationale": "...", "confidence": "high",
             "evidence_kind": ["text_overlap"]},
            ...
         ]}

    `pair_id` follows the ``p-{i}-{j}`` (i<j) scheme from
    propose_links.pass2_merge.pair_id; `from_id`/`to_id` are required so
    the merger can detect snapshot drift between --emit-pairs and
    --with-pass2 invocations (Codex P1.1 guard).
    """

    def __init__(self, fixture_path: Path | str):
        with Path(fixture_path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        analyses = data.get("analyses", [])
        self._by_id: dict[str, dict[str, Any]] = {
            a["pair_id"]: a for a in analyses if "pair_id" in a
        }

    def analyze_pair(self, pair: dict[str, Any]) -> dict[str, Any]:
        pid = pair.get("pair_id")
        if pid is None or pid not in self._by_id:
            raise LookupError(f"no analysis recorded for pair_id={pid!r}")
        return dict(self._by_id[pid])
