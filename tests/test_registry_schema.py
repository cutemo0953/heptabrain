from scripts.registry.schema import (
    V2_AUTO_ACCEPT_FIELDS,
    V2_REQUIRED_FIELDS,
    is_v2_complete,
    load_v2_schema,
    validate_entry,
    validate_registry,
)


def _legacy_entry() -> dict:
    return {
        "link_id": "lk-001",
        "from_knowledge_id": "kb-a",
        "to_knowledge_id": "kb-b",
        "relation_type": "shares_principle",
        "rationale": "both optimize through feedback loops",
        "evidence_refs": ["A §1", "B §2"],
        "novelty_score": 0.8,
        "evidence_score": 0.7,
        "review_state": "proposed",
        "discovered_at": "2026-04-06T15:00:00+08:00",
        "discovered_by": "zettel-walk wander",
    }


def _v2_complete_entry() -> dict:
    entry = _legacy_entry()
    entry.update(
        {
            "link_class": "proposed",
            "acceptance_state": "proposed",
            "scope_type": "cross_whiteboard",
            "scope_whiteboard_id": None,
            "source_mode": "zettel-walk:wander",
            "evidence_kind": ["text_overlap"],
            "last_verified_at": "2026-04-24T11:00:00+08:00",
            "verified_by": "ai",
            "implicit_connection_detected": None,
            "auto_accept_reason": None,
            "auto_accept_confidence": None,
            "promoted_from": None,
        }
    )
    return entry


def test_schema_loads():
    schema = load_v2_schema()
    assert schema["title"].startswith("Discovered Links Registry v2")


def test_legacy_entry_validates():
    assert validate_entry(_legacy_entry()) == []


def test_legacy_entry_not_v2_complete():
    assert is_v2_complete(_legacy_entry()) is False


def test_v2_complete_entry_validates():
    assert validate_entry(_v2_complete_entry()) == []


def test_v2_complete_entry_is_v2_complete():
    assert is_v2_complete(_v2_complete_entry()) is True


def test_missing_link_id_flagged():
    bad = _legacy_entry()
    del bad["link_id"]
    errs = validate_entry(bad)
    assert errs
    assert any("link_id" in e for e in errs)


def test_unknown_relation_type_flagged():
    bad = _legacy_entry()
    bad["relation_type"] = "supports_weakly"
    errs = validate_entry(bad)
    assert errs
    assert any("relation_type" in e for e in errs)


def test_related_to_allowed_as_fallback():
    entry = _legacy_entry()
    entry["relation_type"] = "related_to"
    assert validate_entry(entry) == []


def test_bad_link_class_rejected():
    bad = _v2_complete_entry()
    bad["link_class"] = "deprecated"
    errs = validate_entry(bad)
    assert errs


def test_bad_acceptance_state_rejected():
    bad = _v2_complete_entry()
    bad["acceptance_state"] = "halfway"
    errs = validate_entry(bad)
    assert errs


def test_null_v2_field_breaks_completeness():
    entry = _v2_complete_entry()
    entry["link_class"] = None
    assert is_v2_complete(entry) is False


def test_missing_auto_accept_field_breaks_completeness():
    entry = _v2_complete_entry()
    del entry["promoted_from"]
    assert is_v2_complete(entry) is False


def test_validate_registry_collects_all():
    registry = [
        _legacy_entry(),
        _legacy_entry() | {"link_id": "lk-002", "relation_type": "not_a_type"},
        _v2_complete_entry() | {"link_id": "lk-003"},
    ]
    problems = validate_registry(registry)
    assert len(problems) == 1
    assert problems[0][0] == 1


def test_required_fields_match_spec():
    assert set(V2_REQUIRED_FIELDS) == {
        "link_class",
        "acceptance_state",
        "scope_type",
        "source_mode",
        "evidence_kind",
        "last_verified_at",
        "verified_by",
    }
    assert set(V2_AUTO_ACCEPT_FIELDS) == {
        "implicit_connection_detected",
        "auto_accept_reason",
        "auto_accept_confidence",
        "promoted_from",
    }
