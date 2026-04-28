from datetime import datetime

from scripts.propose_links.output import (
    _slugify,
    dryrun_filename,
    render_dryrun_markdown,
)


def _sample_inventory() -> dict:
    return {
        "whiteboard_id": "wb-x",
        "whiteboard_name": "Sample WB",
        "cards": [
            {"id": "c1", "type": "card", "title": "Alpha"},
            {"id": "c2", "type": "card", "title": "Beta"},
            {"id": "c3", "type": "card", "title": "Gamma"},
        ],
        "skipped": {"section": 1, "image": 2},
        "existing_connections": [{"from": "c1", "to": "c2", "label": "supports"}],
        "scale_tier": "small_no_cluster",
    }


def _sample_diag() -> dict:
    return {
        "tokenizer": "char_wb",
        "ngram_range": (2, 3),
        "vocab_size": 100,
        "card_count": 3,
        "pair_count_total": 3,
        "pair_count_returned": 3,
        "top10_score_distribution": [0.5, 0.3, 0.1],
        "top10_score_spread": 0.4,
        "empty_content_count": 0,
        "dummy_token_count": 0,
    }


# ---------- _slugify ----------


def test_slugify_basic():
    assert _slugify("Hello World") == "hello-world"


def test_slugify_collapses_runs():
    assert _slugify("Hello   World!!!") == "hello-world"


def test_slugify_strips_edges():
    assert _slugify("--Hello--") == "hello"


def test_slugify_preserves_chinese():
    # alnum() returns True for CJK chars
    assert _slugify("反饋迴路") == "反饋迴路"


def test_slugify_empty_returns_default():
    assert _slugify("") == "whiteboard"
    assert _slugify("---") == "whiteboard"


# ---------- dryrun_filename ----------


def test_dryrun_filename_format():
    fixed = datetime(2026, 4, 27, 10, 0, 0)
    name = dryrun_filename("My Whiteboard", today=fixed)
    assert name == "2026-04-27_my-whiteboard_dryrun.md"


def test_dryrun_filename_no_dir_returns_base_name():
    fixed = datetime(2026, 4, 27)
    name = dryrun_filename("WB", today=fixed, output_dir=None)
    assert name == "2026-04-27_wb_dryrun.md"


def test_dryrun_filename_first_run_no_suffix(tmp_path):
    fixed = datetime(2026, 4, 27)
    name = dryrun_filename("WB", today=fixed, output_dir=tmp_path)
    assert name == "2026-04-27_wb_dryrun.md"


def test_dryrun_filename_second_run_same_day_gets_r2(tmp_path):
    from pathlib import Path
    fixed = datetime(2026, 4, 27)
    (tmp_path / "2026-04-27_wb_dryrun.md").write_text("first run")
    name = dryrun_filename("WB", today=fixed, output_dir=tmp_path)
    assert name == "2026-04-27_wb_r2_dryrun.md"


def test_dryrun_filename_third_run_same_day_gets_r3(tmp_path):
    fixed = datetime(2026, 4, 27)
    (tmp_path / "2026-04-27_wb_dryrun.md").write_text("first")
    (tmp_path / "2026-04-27_wb_r2_dryrun.md").write_text("second")
    name = dryrun_filename("WB", today=fixed, output_dir=tmp_path)
    assert name == "2026-04-27_wb_r3_dryrun.md"


def test_dryrun_filename_cross_day_no_suffix(tmp_path):
    # yesterday's file does not affect today's first run
    (tmp_path / "2026-04-26_wb_dryrun.md").write_text("yesterday")
    today = datetime(2026, 4, 27)
    name = dryrun_filename("WB", today=today, output_dir=tmp_path)
    assert name == "2026-04-27_wb_dryrun.md"


def test_dryrun_filename_other_whiteboard_does_not_affect(tmp_path):
    fixed = datetime(2026, 4, 27)
    (tmp_path / "2026-04-27_other_dryrun.md").write_text("different wb")
    name = dryrun_filename("WB", today=fixed, output_dir=tmp_path)
    assert name == "2026-04-27_wb_dryrun.md"


def test_dryrun_filename_handles_missing_output_dir(tmp_path):
    fixed = datetime(2026, 4, 27)
    missing = tmp_path / "does-not-exist-yet"
    name = dryrun_filename("WB", today=fixed, output_dir=missing)
    assert name == "2026-04-27_wb_dryrun.md"


# ---------- render_dryrun_markdown ----------


def test_render_includes_all_required_sections():
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        [(0, 1, 0.5), (0, 2, 0.3), (1, 2, 0.1)],
        _sample_diag(),
    )
    for section in (
        "# Propose-Links Dry-Run",
        "## Existing connections",
        "## Card inventory",
        "## ⭐ Top 5",  # spec §4.1 attention-protected hierarchy
        "## Diagnostics",
        "## Phase 1 boundary",
    ):
        assert section in md, f"missing section: {section}"


def test_render_attention_protected_hierarchy_with_many_pairs():
    inv = _sample_inventory()
    # Build 20 pairs to force Top 5 / Next 10 / Appendix split
    inv["cards"] = [
        {"id": f"c{i}", "type": "card", "title": f"C{i}"} for i in range(8)
    ]
    pairs = [(i, j, round(1.0 - 0.01 * (i * 8 + j), 4))
             for i in range(8) for j in range(i + 1, 8)]  # 28 pairs
    md = render_dryrun_markdown(inv, ("forming", "heuristic"), pairs, _sample_diag())
    assert "## ⭐ Top 5" in md
    assert "## 📌 Next 10" in md
    assert "## 📎 Appendix" in md
    assert "<details>" in md  # appendix collapsed


def test_render_only_top5_when_5_or_fewer_pairs():
    inv = _sample_inventory()
    md = render_dryrun_markdown(
        inv, ("forming", "heuristic"), [(0, 1, 0.5), (0, 2, 0.3)], _sample_diag()
    )
    assert "## ⭐ Top 5" in md
    assert "## 📌 Next 10" not in md
    assert "## 📎 Appendix" not in md


def test_render_includes_inventory_metadata():
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        [],
        _sample_diag(),
    )
    assert "wb-x" in md
    assert "Sample WB" in md
    assert "small_no_cluster" in md
    assert "forming" in md
    assert "heuristic" in md


def test_render_includes_skipped_breakdown():
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        [],
        _sample_diag(),
    )
    assert "section=1" in md
    assert "image=2" in md


def test_render_no_skipped_shows_none():
    inv = _sample_inventory()
    inv["skipped"] = {}
    md = render_dryrun_markdown(inv, ("forming", "heuristic"), [], _sample_diag())
    assert "Skipped object types:** (none)" in md


def test_render_pair_table_when_pairs_present():
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        [(0, 1, 0.5)],
        _sample_diag(),
    )
    assert "| Rank | Card A | Card B | Score |" in md
    assert "0.5000" in md
    assert "Alpha" in md and "Beta" in md


# ---------- slug-collision regex (Codex P1 #3 fix) ----------


def test_dryrun_filename_no_collision_with_slug_prefix(tmp_path):
    """Existing file `2026-04-27_wb-extra_dryrun.md` must NOT block
    new file `2026-04-27_wb_dryrun.md`. Regex anchors slug exactly."""
    fixed = datetime(2026, 4, 27)
    (tmp_path / "2026-04-27_wb-extra_dryrun.md").write_text("different wb")
    name = dryrun_filename("WB", today=fixed, output_dir=tmp_path)
    assert name == "2026-04-27_wb_dryrun.md"


def test_dryrun_filename_handles_garbled_existing_files(tmp_path):
    """Files that don't match the strict pattern are ignored entirely."""
    fixed = datetime(2026, 4, 27)
    (tmp_path / "2026-04-27_wb_dryrun.md").write_text("first")
    (tmp_path / "2026-04-27_wb_rNAN_dryrun.md").write_text("garbled")
    (tmp_path / "2026-04-27_wb_r2_dryrun.txt").write_text("wrong ext")
    name = dryrun_filename("WB", today=fixed, output_dir=tmp_path)
    assert name == "2026-04-27_wb_r2_dryrun.md"


def test_render_no_pairs_shows_placeholder():
    md = render_dryrun_markdown(
        _sample_inventory(), ("seed", "heuristic"), [], _sample_diag()
    )
    assert "_(no pairs — fewer than 2 analyzable cards)_" in md


def test_render_phase1_boundary_explicit():
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        [],
        _sample_diag(),
    )
    # All four exclusions explicitly named
    for excluded in (
        "No LLM Pass 2",
        "No write to `_discovered_links.json`",
        "No suggestion card",
        "No clustering",
        "No gap-signal",
    ):
        assert excluded in md, f"Phase 1 boundary missing: {excluded}"


def test_render_diagnostics_includes_critical_keys():
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        [],
        _sample_diag(),
    )
    for key in ("tokenizer", "vocab_size", "top10_score_spread", "dummy_token_count"):
        assert f"`{key}`" in md


def test_render_handles_existing_connection_without_label():
    inv = _sample_inventory()
    inv["existing_connections"] = [{"from": "c1", "to": "c2"}]
    md = render_dryrun_markdown(inv, ("forming", "heuristic"), [], _sample_diag())
    assert "`c1` → `c2`" in md
    assert "label: `—`" in md


def test_render_no_cards_placeholder():
    inv = _sample_inventory()
    inv["cards"] = []
    md = render_dryrun_markdown(inv, ("seed", "heuristic"), [], _sample_diag())
    assert "_(no analyzable cards)_" in md


def test_render_handles_untitled_card():
    inv = _sample_inventory()
    inv["cards"][0]["title"] = ""
    md = render_dryrun_markdown(
        inv, ("forming", "heuristic"), [(0, 1, 0.5)], _sample_diag()
    )
    assert "(untitled)" in md


# ---------- Phase 2.1: status column ----------


def test_render_with_status_adds_column_and_summary():
    classified = [(0, 1, 0.5, "NEW"), (0, 2, 0.3, "EXISTS")]
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        classified,
        _sample_diag(),
        status_summary={"NEW": 1, "EXISTS": 1, "REDUNDANT": 0},
    )
    assert "| Rank | Card A | Card B | Score | Status |" in md
    assert "`NEW`" in md
    assert "`EXISTS`" in md
    assert "Pair diff" in md
    assert "1 NEW" in md
    assert "1 EXISTS" in md


def test_render_without_status_keeps_legacy_table():
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        [(0, 1, 0.5)],  # 3-tuple, no status
        _sample_diag(),
    )
    assert "| Rank | Card A | Card B | Score |" in md
    assert "Status" not in md


def test_render_status_summary_omits_zero_buckets():
    classified = [(0, 1, 0.5, "NEW")]
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        classified,
        _sample_diag(),
        status_summary={"NEW": 1, "EXISTS": 0, "REDUNDANT": 0},
    )
    assert "1 NEW" in md
    assert "EXISTS" not in md.split("Pair diff")[1].split("\n")[0]
    assert "REDUNDANT" not in md.split("Pair diff")[1].split("\n")[0]


# ---------- Phase 2A: enriched_pairs (LLM Pass 2) ----------


def _enriched(pair_id, *, relation_type=None, rationale=None, confidence=None,
              needs_review=False, pass2_skipped=False, pass2_missing=False):
    return {
        "pair_id": pair_id,
        "relation_type": relation_type,
        "rationale": rationale,
        "confidence": confidence,
        "evidence_kind": [],
        "needs_review": needs_review,
        "pass2_skipped": pass2_skipped,
        "pass2_missing": pass2_missing,
    }


def test_render_with_enriched_pairs_adds_pass2_columns():
    classified = [(0, 1, 0.5, "NEW")]
    enriched = [
        _enriched("p-0-1", relation_type="shares_principle",
                  rationale="Both invoke recursion across boundaries.",
                  confidence="high")
    ]
    md = render_dryrun_markdown(
        _sample_inventory(),
        ("forming", "heuristic"),
        classified,
        _sample_diag(),
        status_summary={"NEW": 1, "EXISTS": 0, "REDUNDANT": 0},
        enriched_pairs=enriched,
    )
    assert "Pass 2 enriched" in md
    assert "| Rank | Card A | Card B | Score | Status | Relation | Conf | Rationale |" in md
    assert "`shares_principle`" in md
    assert "🟢 high" in md
    assert "Both invoke recursion" in md


def test_render_enriched_needs_review_flags_warning():
    classified = [(0, 1, 0.5, "NEW")]
    enriched = [
        _enriched("p-0-1", relation_type="related_to", rationale="weak",
                  confidence="low", needs_review=True)
    ]
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        classified, _sample_diag(),
        enriched_pairs=enriched,
    )
    assert "related_to ⚠️" in md
    assert "🔴 low" in md


def test_render_enriched_skipped_pair_shows_skipped_label():
    classified = [(0, 1, 0.5, "EXISTS")]
    enriched = [_enriched("p-0-1", pass2_skipped=True)]
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        classified, _sample_diag(),
        enriched_pairs=enriched,
    )
    assert "(skipped)" in md
    # confidence column shows em-dash for unanalyzed pair
    assert "| `(skipped)` | — |" in md


def test_render_enriched_missing_pair_shows_missing_label():
    classified = [(0, 1, 0.5, "NEW")]
    enriched = [_enriched("p-0-1", pass2_missing=True, confidence="low")]
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        classified, _sample_diag(),
        enriched_pairs=enriched,
    )
    assert "(missing)" in md
    assert "🔴 low" in md


def test_render_enriched_truncates_long_rationale():
    classified = [(0, 1, 0.5, "NEW")]
    long_rationale = "x" * 300
    enriched = [_enriched("p-0-1", relation_type="supports",
                          rationale=long_rationale, confidence="med")]
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        classified, _sample_diag(),
        enriched_pairs=enriched,
    )
    # 160-char cap with ellipsis
    assert "x" * 157 + "…" in md
    assert "x" * 300 not in md


def test_render_enriched_escapes_pipe_and_collapses_newlines():
    classified = [(0, 1, 0.5, "NEW")]
    enriched = [_enriched("p-0-1", relation_type="supports",
                          rationale="line1\nline2 | with pipe",
                          confidence="med")]
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        classified, _sample_diag(),
        enriched_pairs=enriched,
    )
    assert "line1 line2 \\| with pipe" in md
    # No raw newline mid-row
    assert "line1\nline2" not in md


def test_render_no_enriched_pairs_keeps_legacy_table():
    """Default enriched_pairs=None preserves Phase 2.1 4-column table."""
    classified = [(0, 1, 0.5, "NEW")]
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        classified, _sample_diag(),
        status_summary={"NEW": 1, "EXISTS": 0, "REDUNDANT": 0},
    )
    assert "Pass 2 enriched" not in md
    assert "Relation | Conf | Rationale" not in md


def test_render_empty_enriched_list_treated_as_no_pass2():
    classified = [(0, 1, 0.5, "NEW")]
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        classified, _sample_diag(),
        enriched_pairs=[],
    )
    assert "Pass 2 enriched" not in md
    assert "Relation" not in md


def test_render_enriched_partial_coverage_mixes_known_and_missing():
    """Realistic scenario: 2 NEW pairs, only 1 has an analysis.
    The one without analysis gets pass2_missing=True from merge_pass2,
    so renderer must show both rows (one analyzed, one '(missing)').
    """
    inventory = _sample_inventory()
    classified = [(0, 1, 0.5, "NEW"), (0, 2, 0.3, "NEW")]
    enriched = [
        _enriched("p-0-1", relation_type="supports", rationale="r1",
                  confidence="high"),
        _enriched("p-0-2", pass2_missing=True, confidence="low"),
    ]
    md = render_dryrun_markdown(
        inventory, ("forming", "heuristic"),
        classified, _sample_diag(),
        status_summary={"NEW": 2, "EXISTS": 0, "REDUNDANT": 0},
        enriched_pairs=enriched,
    )
    assert "`supports`" in md
    assert "🟢 high" in md
    assert "(missing)" in md
    assert "🔴 low" in md


# ---------- Phase 2B: Gap Signals section ----------


def _gap_report(**overrides):
    """Default empty-but-not-None report; tests override specific keys."""
    base = {
        "weak_integration": [],
        "central_hub": [],
        "fragile_bridge": [],
        "merge_candidate": [],
        "spaghetti": [],
        "node_count": 0,
        "edge_count": 0,
        "warnings": [],
    }
    base.update(overrides)
    return base


def test_render_gap_signals_none_omits_section():
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=None,
    )
    assert "## Gap Signals" not in md


def test_render_gap_signals_empty_report_shows_healthy_message():
    """Empty-but-not-None report → section present, but '結構健康' line."""
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=_gap_report(node_count=5, edge_count=3),
    )
    assert "## Gap Signals" in md
    assert "5 nodes" in md
    assert "3 edges" in md
    assert "結構健康" in md
    # No section bullets for absent signal types
    assert "Weak integration" not in md
    assert "Central hub" not in md


def test_render_gap_signals_weak_integration_lists_cards():
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=_gap_report(
            weak_integration=["card-x", "card-y"], node_count=3, edge_count=1,
        ),
    )
    assert "**Weak integration (2)**" in md
    assert "`card-x`" in md
    assert "`card-y`" in md
    assert "rethink 位置" in md


def test_render_gap_signals_central_hub_lists_top_n():
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=_gap_report(
            central_hub=["hub-a", "hub-b"], node_count=8, edge_count=12,
        ),
    )
    assert "**Central hub**" in md
    assert "`hub-a`" in md
    assert "`hub-b`" in md
    assert "physical 中央" in md or "物理中央" in md


def test_render_gap_signals_fragile_bridge_renders_each_edge():
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=_gap_report(
            fragile_bridge=[("a", "b"), ("c", "d")],
            node_count=10, edge_count=11,
        ),
    )
    assert "**Fragile bridge (2)**" in md
    assert "`a` ↔ `b`" in md
    assert "`c` ↔ `d`" in md
    assert "redundant bridge" in md


def test_render_gap_signals_merge_candidate_includes_overlap_and_shared():
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=_gap_report(
            merge_candidate=[
                {"from_id": "A", "to_id": "B", "overlap": 0.85,
                 "shared_neighbors": ["x", "y", "z"]},
            ],
            node_count=5, edge_count=8,
        ),
    )
    assert "**Merge candidate (1)**" in md
    assert "`A` ⇄ `B`" in md
    assert "0.85" in md
    assert "`x`" in md and "`y`" in md and "`z`" in md
    assert "合併為一張卡片" in md


def test_render_gap_signals_spaghetti_includes_degree_and_threshold():
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=_gap_report(
            spaghetti=[
                {"card_id": "hub-of-doom", "degree": 9, "threshold": 6},
            ],
            node_count=20, edge_count=18,
        ),
    )
    assert "**Spaghetti warning (1)**" in md
    assert "`hub-of-doom`" in md
    assert "degree 9" in md
    assert "threshold 6" in md
    assert "高維原則" in md or "拆為" in md


def test_render_gap_signals_warnings_surface_with_emoji():
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=_gap_report(
            warnings=["networkx unavailable — degraded"],
        ),
    )
    assert "⚠️ networkx unavailable — degraded" in md


def test_render_gap_signals_all_five_types_in_order():
    """Smoke test for sequencing: weak → hub → fragile → merge → spaghetti."""
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=_gap_report(
            weak_integration=["w1"],
            central_hub=["h1"],
            fragile_bridge=[("f1", "f2")],
            merge_candidate=[{"from_id": "m1", "to_id": "m2",
                              "overlap": 0.9, "shared_neighbors": ["s1"]}],
            spaghetti=[{"card_id": "sp1", "degree": 8, "threshold": 5}],
            node_count=15, edge_count=22,
        ),
    )
    weak_pos = md.index("Weak integration")
    hub_pos = md.index("Central hub")
    fragile_pos = md.index("Fragile bridge")
    merge_pos = md.index("Merge candidate")
    spag_pos = md.index("Spaghetti warning")
    assert weak_pos < hub_pos < fragile_pos < merge_pos < spag_pos


def test_render_phase2b_only_boundary_when_signals_without_pass2():
    """Codex P1.3 follow-through: signals alone → 'Phase 2B boundary'."""
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        gap_signals_report=_gap_report(),
    )
    assert "Phase 2B boundary" in md
    assert "Phase 2A boundary" not in md
    assert "Phase 1 boundary" not in md


def test_render_combined_phase_2a_2b_boundary_when_both():
    md = render_dryrun_markdown(
        _sample_inventory(), ("forming", "heuristic"),
        [(0, 1, 0.5, "NEW")], _sample_diag(),
        enriched_pairs=[
            _enriched("p-0-1", relation_type="supports", rationale="x",
                      confidence="high"),
        ],
        gap_signals_report=_gap_report(),
    )
    assert "Phase 2A + 2B boundary" in md
    # Combined footer should NOT list pass2/signals as deferred
    deferred_block = md.split("intentionally did NOT happen")[1]
    assert "No LLM Pass 2" not in deferred_block
    assert "No gap-signal" not in deferred_block
    # But registry / suggestion card still listed as deferred
    assert "_discovered_links.json" in deferred_block
    assert "suggestion card" in deferred_block
