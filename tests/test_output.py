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
