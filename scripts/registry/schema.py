"""Registry v2 schema loading and entry validation.

Per DEV_SPEC_CYBERBRAIN_ARCHITECTURE.md §3.2. v2 provenance fields are optional
in the JSON schema so legacy v2.1 entries still validate; `is_v2_complete()`
distinguishes complete-v2 from legacy-fallback entries.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "registry-schemas"
    / "discovered_links.v2.schema.json"
)

V2_REQUIRED_FIELDS: tuple[str, ...] = (
    "link_class",
    "acceptance_state",
    "scope_type",
    "source_mode",
    "evidence_kind",
    "last_verified_at",
    "verified_by",
)

V2_AUTO_ACCEPT_FIELDS: tuple[str, ...] = (
    "implicit_connection_detected",
    "auto_accept_reason",
    "auto_accept_confidence",
    "promoted_from",
)


@lru_cache(maxsize=1)
def load_v2_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _item_validator() -> Draft202012Validator:
    item_schema = load_v2_schema()["items"]
    return Draft202012Validator(item_schema)


def validate_entry(entry: dict[str, Any]) -> list[str]:
    errors = []
    for err in _item_validator().iter_errors(entry):
        path = "/".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{path}: {err.message}")
    return errors


def is_v2_complete(entry: dict[str, Any]) -> bool:
    for field in V2_REQUIRED_FIELDS:
        if field not in entry or entry[field] is None:
            return False
    for field in V2_AUTO_ACCEPT_FIELDS:
        if field not in entry:
            return False
    return True


def validate_registry(entries: list[dict[str, Any]]) -> list[tuple[int, list[str]]]:
    problems = []
    for idx, entry in enumerate(entries):
        errs = validate_entry(entry)
        if errs:
            problems.append((idx, errs))
    return problems
