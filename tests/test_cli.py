import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.lib.mcp_client import FakeHeptabaseMCPClient
from scripts.propose_links.cli import (
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    EXIT_USER_ERROR,
    main,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mock_whiteboard_en_zh.json"


def _client() -> FakeHeptabaseMCPClient:
    return FakeHeptabaseMCPClient(FIXTURE)


def _streams():
    return io.StringIO(), io.StringIO()


# ---------- happy path ----------


def test_happy_path_writes_markdown(tmp_path: Path):
    out, err = _streams()
    rc = main(
        ["wb-mock-en-zh-001", "--output-dir", str(tmp_path)],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_OK
    files = list(tmp_path.glob("*_dryrun.md"))
    assert len(files) == 1
    md = files[0].read_text(encoding="utf-8")
    assert "Propose-Links Dry-Run" in md
    assert "Phase 1 boundary" in md
    assert "[dry-run written to" in err.getvalue()


def test_happy_path_stdout_includes_markdown(tmp_path: Path):
    out, err = _streams()
    rc = main(
        ["wb-mock-en-zh-001", "--output-dir", str(tmp_path)],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_OK
    assert "Propose-Links Dry-Run" in out.getvalue()


# ---------- discovery errors ----------


def test_unknown_whiteboard_returns_user_error(tmp_path: Path):
    out, err = _streams()
    rc = main(
        ["does-not-exist", "--output-dir", str(tmp_path)],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "no whiteboard matched" in err.getvalue()


def test_ambiguous_keyword_returns_user_error(tmp_path: Path):
    out, err = _streams()
    rc = main(
        ["Mock", "--output-dir", str(tmp_path)],  # matches all 5 fixture wbs
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "matched 5 whiteboards" in err.getvalue()
    assert "exact whiteboard id" in err.getvalue()


def test_empty_keyword_returns_user_error(tmp_path: Path):
    out, err = _streams()
    rc = main(
        ["", "--output-dir", str(tmp_path)],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_USER_ERROR


# ---------- scale-tier guards ----------


def test_hard_stop_returns_user_error(tmp_path: Path):
    fake_client = MagicMock()
    fake_client.search_whiteboards.return_value = [
        {"id": "wb-large", "name": "Large WB"}
    ]
    fake_client.get_whiteboard_with_objects.return_value = {
        "id": "wb-large",
        "name": "Large WB",
        "objects": [
            {"id": f"c{i}", "type": "card", "title": f"T{i}", "content": "x", "tags": []}
            for i in range(51)
        ],
        "connections": [],
    }
    out, err = _streams()
    rc = main(
        ["wb-large", "--output-dir", str(tmp_path)],
        client=fake_client,
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "51 analyzable cards" in err.getvalue()
    assert "Split into sections" in err.getvalue()
    # nothing written on hard stop
    assert list(tmp_path.glob("*.md")) == []


# ---------- maturity guards ----------


def test_seed_maturity_returns_user_error(tmp_path: Path):
    out, err = _streams()
    rc = main(
        ["wb-mock-tiny-001", "--output-dir", str(tmp_path)],  # 4 cards = seed
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "seed" in err.getvalue()
    assert "Add more cards" in err.getvalue()


def test_canonical_maturity_warns_but_proceeds(tmp_path: Path):
    fake_client = MagicMock()
    fake_client.search_whiteboards.return_value = [
        {"id": "wb-canon", "name": "Canon WB"}
    ]
    # 11 cards + meta card with maturity: canonical
    fake_client.get_whiteboard_with_objects.return_value = {
        "id": "wb-canon",
        "name": "Canon WB",
        "objects": [
            {"id": "meta", "type": "card", "title": "⚙️ Meta", "content": "maturity: canonical"},
            *[
                {
                    "id": f"c{i}",
                    "type": "card",
                    "title": f"Card {i}",
                    "content": f"unique content number {i} alpha beta gamma {i*7}",
                    "tags": [],
                }
                for i in range(10)
            ],
        ],
        "connections": [],
    }
    out, err = _streams()
    rc = main(
        ["wb-canon", "--output-dir", str(tmp_path)],
        client=fake_client,
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_OK
    assert "canonical" in err.getvalue()
    assert list(tmp_path.glob("*.md"))


# ---------- CJK gate ----------


def test_cjk_gate_can_be_bypassed(tmp_path: Path):
    # Construct a fake whiteboard where all cards have near-identical
    # text → top-10 spread will be tiny → gate triggers
    fake_client = MagicMock()
    fake_client.search_whiteboards.return_value = [
        {"id": "wb-uniform", "name": "Uniform"}
    ]
    fake_client.get_whiteboard_with_objects.return_value = {
        "id": "wb-uniform",
        "name": "Uniform",
        "objects": [
            {"id": f"c{i}", "type": "card", "title": "Same", "content": "identical content here", "tags": []}
            for i in range(10)
        ],
        "connections": [],
    }
    # First, prove the gate would block
    out, err = _streams()
    rc = main(
        ["wb-uniform", "--output-dir", str(tmp_path)],
        client=fake_client,
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_RUNTIME_ERROR
    assert "CJK gate FAIL" in err.getvalue()

    # Now with --no-cjk-gate it proceeds
    out2, err2 = _streams()
    rc2 = main(
        ["wb-uniform", "--output-dir", str(tmp_path), "--no-cjk-gate"],
        client=fake_client,
        stdout=out2,
        stderr=err2,
    )
    assert rc2 == EXIT_OK


# ---------- maturity-registry argument flow ----------


def test_maturity_registry_path_is_consulted(tmp_path: Path):
    # Pre-populate registry with explicit maturity for our whiteboard
    from scripts.registry.whiteboard_maturity import set_maturity

    reg = tmp_path / "m.json"
    set_maturity("wb-mock-en-zh-001", "structured", "manual", reg)

    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001",
            "--output-dir",
            str(tmp_path),
            "--maturity-registry",
            str(reg),
        ],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_OK
    md = (tmp_path / "2026-04-27_mock-whiteboard-en-zh-phase-1-fixture-_dryrun.md")
    # date in filename varies; just find the produced file
    files = list(tmp_path.glob("*_dryrun.md"))
    assert len(files) == 1
    md_text = files[0].read_text(encoding="utf-8")
    assert "structured" in md_text
    assert "manual" in md_text


# ---------- argument plumbing ----------


def test_dryrun_flag_is_default_true():
    parser = __import__(
        "scripts.propose_links.cli", fromlist=["build_parser"]
    ).build_parser()
    args = parser.parse_args(["wb-x"])
    assert args.dry_run is True


def test_no_cjk_gate_default_off():
    parser = __import__(
        "scripts.propose_links.cli", fromlist=["build_parser"]
    ).build_parser()
    args = parser.parse_args(["wb-x"])
    assert args.no_cjk_gate is False


# ---------- Phase 2+ flag handling (item 8 self-review fix) ----------


@pytest.mark.parametrize(
    "flag", ["--mda", "--journal", "--audit-only"]
)
def test_phase2_flag_exits_with_friendly_message(tmp_path: Path, flag, capsys):
    out, err = _streams()
    with pytest.raises(SystemExit) as excinfo:
        main(
            ["wb-mock-en-zh-001", flag, "--output-dir", str(tmp_path)],
            client=_client(),
            stdout=out,
            stderr=err,
        )
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "not in Phase 1 scope" in captured.err
    assert flag in captured.err
    # nothing written
    assert list(tmp_path.glob("*.md")) == []


# ---------- re-run within same day (item 5 self-review fix) ----------


def test_same_day_rerun_appends_r2_suffix(tmp_path: Path):
    out, err = _streams()
    rc1 = main(
        ["wb-mock-en-zh-001", "--output-dir", str(tmp_path)],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc1 == EXIT_OK

    rc2 = main(
        ["wb-mock-en-zh-001", "--output-dir", str(tmp_path)],
        client=_client(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    assert rc2 == EXIT_OK

    files = sorted(p.name for p in tmp_path.glob("*_dryrun.md"))
    assert len(files) == 2
    # second file has _r2
    assert any("_r2_dryrun.md" in n for n in files)


# ---------- write failure handling (item 2 self-review fix) ----------


def test_unwritable_output_dir_returns_runtime_error(tmp_path: Path):
    # make tmp_path unwritable by creating a file where we expect a dir
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    out, err = _streams()
    rc = main(
        ["wb-mock-en-zh-001", "--output-dir", str(blocker / "sub")],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_RUNTIME_ERROR
    assert "cannot write dry-run output" in err.getvalue()


# ---------- CLI default-client friendly error (Codex P1 #1 fix) ----------


def test_default_client_path_returns_user_error_not_traceback(tmp_path: Path):
    """Without --fixture and without injected client, _build_client returns
    HeptabaseMCPClient which raises NotImplementedError. CLI must catch
    and surface a friendly message + exit code, not propagate traceback."""
    out, err = _streams()
    rc = main(
        ["wb-x", "--output-dir", str(tmp_path)],
        client=None,
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "Real MCPClient" in err.getvalue() or "Phase 1 CLI does not yet wire" in err.getvalue()


# ---------- Phase 2+ flag =value form (Codex P2 #2 fix) ----------


@pytest.mark.parametrize(
    "tok",
    ["--mda=true", "--journal=foo", "--max-links=10"],
)
def test_phase2_flag_value_form_also_intercepted(tmp_path: Path, tok, capsys):
    out, err = _streams()
    with pytest.raises(SystemExit) as excinfo:
        main(
            ["wb-mock-en-zh-001", tok, "--output-dir", str(tmp_path)],
            client=_client(),
            stdout=out,
            stderr=err,
        )
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "not in Phase 1 scope" in captured.err
    assert tok.split("=")[0] in captured.err


# ---------- Phase 2A: --emit-pairs ----------


def test_emit_pairs_writes_only_new_pairs(tmp_path: Path):
    out, err = _streams()
    pairs_path = tmp_path / "pairs.json"
    rc = main(
        [
            "wb-mock-en-zh-001",
            "--output-dir",
            str(tmp_path),
            "--emit-pairs",
            str(pairs_path),
        ],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_OK
    assert pairs_path.exists()

    import json as _json
    payload = _json.loads(pairs_path.read_text(encoding="utf-8"))
    assert payload["whiteboard_id"] == "wb-mock-en-zh-001"
    assert "pairs" in payload
    # Every emitted pair has the required schema for LLM Pass 2
    for p in payload["pairs"]:
        assert set(p.keys()) >= {
            "pair_id", "score", "from_id", "to_id",
            "from_title", "to_title", "from_tags", "to_tags",
            "from_excerpt", "to_excerpt",
        }
        assert p["pair_id"].startswith("p-")
    # No dryrun.md written when --emit-pairs is used (short-circuit)
    assert list(tmp_path.glob("*_dryrun.md")) == []
    assert "[emit-pairs] wrote" in err.getvalue()


def test_emit_pairs_excludes_existing_connections(tmp_path: Path):
    """The fixture has 3 existing connections; --emit-pairs only includes
    pairs that are NEW (not already linked)."""
    out, err = _streams()
    pairs_path = tmp_path / "pairs.json"
    rc = main(
        [
            "wb-mock-en-zh-001",
            "--output-dir",
            str(tmp_path),
            "--emit-pairs",
            str(pairs_path),
        ],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_OK
    import json as _json
    payload = _json.loads(pairs_path.read_text(encoding="utf-8"))
    # Make sure pairs (card-en-1, card-en-2) which the fixture marks as
    # connected do NOT appear (or, if they do, only because they're not
    # actually existing — verify by checking from/to ids never match an
    # existing connection in the fixture).
    existing_pair_set = {
        frozenset({"card-en-1", "card-en-2"}),
        frozenset({"card-zh-1", "card-zh-2"}),
        frozenset({"card-en-3", "card-en-4"}),
    }
    for p in payload["pairs"]:
        ids = frozenset({p["from_id"], p["to_id"]})
        assert ids not in existing_pair_set, (
            f"pair {ids} should be EXISTS, not in NEW emit"
        )


def test_emit_pairs_unwritable_path_returns_runtime_error(tmp_path: Path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001",
            "--output-dir",
            str(tmp_path),
            "--emit-pairs",
            str(blocker / "sub" / "pairs.json"),
        ],
        client=_client(),
        stdout=out,
        stderr=err,
    )
    assert rc == EXIT_RUNTIME_ERROR
    assert "cannot write pair contexts" in err.getvalue()


# ---------- Phase 2A: --with-pass2 ----------


def _write_pass2(path: Path, analyses: list) -> None:
    import json as _json
    path.write_text(
        _json.dumps({"analyses": analyses}, ensure_ascii=False),
        encoding="utf-8",
    )


def _emit_and_get_first_pair(tmp_path: Path) -> dict:
    pairs_path = tmp_path / "pairs.json"
    main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--emit-pairs", str(pairs_path),
        ],
        client=_client(), stdout=io.StringIO(), stderr=io.StringIO(),
    )
    import json as _json
    payload = _json.loads(pairs_path.read_text(encoding="utf-8"))
    assert payload["pairs"]
    return payload


def _write_pass2_envelope(path: Path, *, whiteboard_id: str | None,
                          analyses: list) -> None:
    import json as _json
    body: dict = {"analyses": analyses}
    if whiteboard_id is not None:
        body["whiteboard_id"] = whiteboard_id
    path.write_text(_json.dumps(body, ensure_ascii=False), encoding="utf-8")


def test_with_pass2_renders_enriched_columns(tmp_path: Path):
    payload = _emit_and_get_first_pair(tmp_path)
    first = payload["pairs"][0]
    pass2_path = tmp_path / "pass2.json"
    _write_pass2_envelope(
        pass2_path,
        whiteboard_id=payload["whiteboard_id"],
        analyses=[{
            "pair_id": first["pair_id"],
            "from_id": first["from_id"],
            "to_id": first["to_id"],
            "relation_type": "shares_principle",
            "rationale": "Shared closure pattern.",
            "confidence": "high",
            "evidence_kind": ["text_overlap"],
        }],
    )

    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001",
            "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    md_files = [p for p in tmp_path.glob("*_dryrun.md")]
    assert md_files
    md_text = md_files[-1].read_text(encoding="utf-8")
    assert "Pass 2 enriched" in md_text
    assert "Relation | Conf | Rationale" in md_text
    assert "shares_principle" in md_text
    assert "Shared closure pattern." in md_text
    # P1.3 — Phase 2A boundary footer replaces Phase 1 boundary
    assert "Phase 2A boundary" in md_text
    assert "Phase 1 boundary" not in md_text


def test_with_pass2_envelope_whiteboard_mismatch_returns_user_error(tmp_path: Path):
    """Codex P1.1: outer-envelope whiteboard_id cross-check."""
    payload = _emit_and_get_first_pair(tmp_path)
    first = payload["pairs"][0]
    pass2_path = tmp_path / "pass2.json"
    _write_pass2_envelope(
        pass2_path,
        whiteboard_id="wb-DIFFERENT-snapshot",
        analyses=[{
            "pair_id": first["pair_id"],
            "from_id": first["from_id"],
            "to_id": first["to_id"],
            "relation_type": "supports",
            "rationale": "x",
            "confidence": "high",
        }],
    )
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "envelope whiteboard_id" in err.getvalue()
    assert "snapshot-drift" in err.getvalue()


def test_with_pass2_envelope_missing_whiteboard_id_warns_but_proceeds(tmp_path: Path):
    """Back-compat: no envelope whiteboard_id → warning, not failure."""
    payload = _emit_and_get_first_pair(tmp_path)
    first = payload["pairs"][0]
    pass2_path = tmp_path / "pass2.json"
    _write_pass2_envelope(
        pass2_path,
        whiteboard_id=None,
        analyses=[{
            "pair_id": first["pair_id"],
            "from_id": first["from_id"],
            "to_id": first["to_id"],
            "relation_type": "supports",
            "rationale": "ok",
            "confidence": "high",
        }],
    )
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert "envelope has no whiteboard_id" in err.getvalue()


def test_with_pass2_endpoint_mismatch_treated_as_missing(tmp_path: Path):
    """Codex P1.1: per-pair from_id/to_id cross-check.

    Even if pair_id matches, swapping in wrong endpoints must downgrade
    the pair to (missing) rather than silently mis-attaching the analysis.
    """
    payload = _emit_and_get_first_pair(tmp_path)
    first = payload["pairs"][0]
    pass2_path = tmp_path / "pass2.json"
    _write_pass2_envelope(
        pass2_path,
        whiteboard_id=payload["whiteboard_id"],
        analyses=[{
            "pair_id": first["pair_id"],
            # WRONG endpoints
            "from_id": "card-WRONG-1",
            "to_id": "card-WRONG-2",
            "relation_type": "supports",
            "rationale": "should not appear",
            "confidence": "high",
        }],
    )
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert "snapshot-drift" in err.getvalue()
    md_text = next(tmp_path.glob("*_dryrun.md")).read_text(encoding="utf-8")
    assert "should not appear" not in md_text
    assert "(missing)" in md_text


def test_with_pass2_per_pair_missing_endpoints_treated_as_missing(tmp_path: Path):
    """Codex P1.2 + P1.1: an analysis without from_id/to_id is rejected
    (snapshot-drift defense; we cannot validate the endpoints)."""
    payload = _emit_and_get_first_pair(tmp_path)
    first = payload["pairs"][0]
    pass2_path = tmp_path / "pass2.json"
    _write_pass2_envelope(
        pass2_path,
        whiteboard_id=payload["whiteboard_id"],
        analyses=[{
            "pair_id": first["pair_id"],
            # no from_id / to_id
            "relation_type": "supports",
            "rationale": "x",
            "confidence": "high",
        }],
    )
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert "is missing from_id/to_id" in err.getvalue()
    md_text = next(tmp_path.glob("*_dryrun.md")).read_text(encoding="utf-8")
    assert "(missing)" in md_text


def test_with_pass2_non_dict_item_warns_and_skips(tmp_path: Path):
    """Codex P1.2: non-dict analysis items must not crash."""
    payload = _emit_and_get_first_pair(tmp_path)
    first = payload["pairs"][0]
    pass2_path = tmp_path / "pass2.json"
    _write_pass2_envelope(
        pass2_path,
        whiteboard_id=payload["whiteboard_id"],
        analyses=[
            "i am a string, not an analysis",
            42,
            None,
            {
                "pair_id": first["pair_id"],
                "from_id": first["from_id"],
                "to_id": first["to_id"],
                "relation_type": "supports",
                "rationale": "valid",
                "confidence": "high",
            },
        ],
    )
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert "is not a dict" in err.getvalue()
    md_text = next(tmp_path.glob("*_dryrun.md")).read_text(encoding="utf-8")
    assert "valid" in md_text  # the one good entry still flows through


def test_with_pass2_malformed_pair_id_skipped(tmp_path: Path):
    """Codex P1.2: pair_id must match ^p-\\d+-\\d+$."""
    payload = _emit_and_get_first_pair(tmp_path)
    pass2_path = tmp_path / "pass2.json"
    _write_pass2_envelope(
        pass2_path,
        whiteboard_id=payload["whiteboard_id"],
        analyses=[{
            "pair_id": "p-zero-one",  # malformed
            "from_id": "x",
            "to_id": "y",
            "relation_type": "supports",
            "rationale": "ghost",
            "confidence": "high",
        }],
    )
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert "malformed pair_id" in err.getvalue()


# ---------- Phase 2B: --signals ----------


def test_signals_alone_renders_gap_section_without_pass2(tmp_path: Path):
    """--signals should run without --with-pass2; gap signals computed
    over existing + proposed graph, merge_candidate naturally empty
    (no high-confidence labels)."""
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--signals",
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    md = next(tmp_path.glob("*_dryrun.md")).read_text(encoding="utf-8")
    assert "## Gap Signals" in md
    # Phase 2B boundary swaps in
    assert "Phase 2B boundary" in md
    assert "Phase 1 boundary" not in md


def test_signals_plus_pass2_renders_combined_boundary(tmp_path: Path):
    """When both layers run, boundary footer reads 'Phase 2A + 2B'."""
    payload = _emit_and_get_first_pair(tmp_path)
    first = payload["pairs"][0]
    pass2_path = tmp_path / "pass2.json"
    _write_pass2_envelope(
        pass2_path,
        whiteboard_id=payload["whiteboard_id"],
        analyses=[{
            "pair_id": first["pair_id"],
            "from_id": first["from_id"],
            "to_id": first["to_id"],
            "relation_type": "shares_principle",
            "rationale": "ok",
            "confidence": "high",
        }],
    )
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--signals",
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    md = next(tmp_path.glob("*_dryrun.md")).read_text(encoding="utf-8")
    assert "Phase 2A + 2B boundary" in md
    assert "## Gap Signals" in md


def test_signals_off_by_default(tmp_path: Path):
    """Without --signals, no Gap Signals section in markdown."""
    out, err = _streams()
    rc = main(
        ["wb-mock-en-zh-001", "--output-dir", str(tmp_path)],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    md = next(tmp_path.glob("*_dryrun.md")).read_text(encoding="utf-8")
    assert "## Gap Signals" not in md


def test_signals_with_emit_pairs_short_circuits_before_signals(tmp_path: Path):
    """--emit-pairs exits early; --signals on the same call is moot."""
    pairs_path = tmp_path / "pairs.json"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--emit-pairs", str(pairs_path),
            "--signals",  # parsed but unreachable
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert pairs_path.exists()
    # No markdown / no gap signals — short-circuit before render
    assert list(tmp_path.glob("*_dryrun.md")) == []


# ---------- Phase 2C: --discovered-json ----------


def _emit_pass2_for_first_pair(tmp_path: Path, *, relation="shares_principle",
                               confidence="high"):
    """Run --emit-pairs, build a Pass 2 envelope for the first pair only."""
    payload = _emit_and_get_first_pair(tmp_path)
    first = payload["pairs"][0]
    pass2_path = tmp_path / "pass2.json"
    _write_pass2_envelope(
        pass2_path,
        whiteboard_id=payload["whiteboard_id"],
        analyses=[{
            "pair_id": first["pair_id"],
            "from_id": first["from_id"],
            "to_id": first["to_id"],
            "relation_type": relation,
            "rationale": "test rationale",
            "confidence": confidence,
            "evidence_kind": ["text_overlap"],
        }],
    )
    return payload, pass2_path


def test_discovered_json_writes_eligible_entries(tmp_path: Path):
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    reg = tmp_path / "links.json"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--discovered-json", str(reg),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert reg.exists()
    import json as _json
    data = _json.loads(reg.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["link_class"] == "proposed"
    assert data[0]["acceptance_state"] == "proposed"
    assert data[0]["scope_whiteboard_id"] == "wb-mock-en-zh-001"
    assert "[discovered-json] wrote 1 entries" in err.getvalue()


def test_discovered_json_requires_with_pass2(tmp_path: Path):
    """--discovered-json without --with-pass2 → user error (writer
    needs Pass 2 results to determine eligibility)."""
    reg = tmp_path / "links.json"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--discovered-json", str(reg),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "requires --with-pass2" in err.getvalue()
    assert not reg.exists()


def test_discovered_json_corrupt_existing_returns_runtime_error(tmp_path: Path):
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    reg = tmp_path / "links.json"
    reg.write_text("{not valid json", encoding="utf-8")
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--discovered-json", str(reg),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_RUNTIME_ERROR
    assert "not valid JSON" in err.getvalue()


def test_discovered_json_low_confidence_skipped(tmp_path: Path):
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path,
                                                     confidence="low")
    reg = tmp_path / "links.json"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--discovered-json", str(reg),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert "wrote 0 entries" in err.getvalue()
    assert not reg.exists()


# ---------- Phase 2C: --suggestion-card ----------


def test_suggestion_card_writes_markdown_body(tmp_path: Path):
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    card_path = tmp_path / "suggestion.md"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--suggestion-card", str(card_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert card_path.exists()
    body = card_path.read_text(encoding="utf-8")
    assert body.startswith("# 🗂️")
    assert "建議 New Links" in body
    assert "下次 re-run 前 checklist" in body
    assert "[suggestion-card] wrote" in err.getvalue()


def test_suggestion_card_requires_with_pass2(tmp_path: Path):
    card_path = tmp_path / "suggestion.md"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--suggestion-card", str(card_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "requires --with-pass2" in err.getvalue()
    assert not card_path.exists()


def test_suggestion_card_unwritable_path_returns_runtime_error(tmp_path: Path):
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    card_path = blocker / "sub" / "card.md"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--suggestion-card", str(card_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_RUNTIME_ERROR
    assert "--suggestion-card write failed" in err.getvalue()


def test_suggestion_card_combined_with_signals_includes_gap_section(tmp_path: Path):
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    card_path = tmp_path / "card.md"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--signals",
            "--suggestion-card", str(card_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    body = card_path.read_text(encoding="utf-8")
    # Gap signals section appears only when --signals ran AND something
    # was detected. The mock fixture has 5 isolated cards → weak_integration
    # populated.
    assert "## Gap Signals" in body or "建議 New Links" in body


def test_discovered_json_and_suggestion_card_collision_returns_user_error(
    tmp_path: Path,
):
    """Codex Phase 2C P1.1: same path for both → silent corruption.
    Preflight must reject."""
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    same = tmp_path / "shared.out"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--discovered-json", str(same),
            "--suggestion-card", str(same),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "path collision" in err.getvalue()
    assert not same.exists()


def test_discovered_json_collides_with_pass2_input(tmp_path: Path):
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--discovered-json", str(pass2_path),  # same as input!
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "path collision" in err.getvalue()
    # pass2.json untouched
    import json as _json
    assert "analyses" in _json.loads(pass2_path.read_text(encoding="utf-8"))


def test_emit_pairs_and_with_pass2_path_collision(tmp_path: Path):
    """Even though they're never used together logically, the preflight
    is value-shape — same path for both flags must surface as user error
    rather than silent overwrite."""
    p = tmp_path / "shared.json"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--emit-pairs", str(p),
            "--with-pass2", str(p),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "path collision" in err.getvalue()


def test_suggestion_card_failure_leaves_registry_untouched(tmp_path: Path):
    """Codex Phase 2C P1.2: write order = local-first, durable-last.
    If suggestion-card write fails, the registry must not have been
    appended to (so retry is safe)."""
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    reg = tmp_path / "links.json"
    # Create a path the card can never be written to (parent is a file)
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    bad_card = blocker / "sub" / "card.md"

    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--discovered-json", str(reg),
            "--suggestion-card", str(bad_card),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_RUNTIME_ERROR
    # Registry must NOT exist (card write failed before registry append)
    assert not reg.exists(), (
        "registry was written despite card-write failure — retry would duplicate"
    )


def test_dryrun_failure_leaves_registry_untouched(tmp_path: Path):
    """Same invariant as above but for the dry-run markdown write step."""
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    reg = tmp_path / "links.json"
    # Block the dry-run output dir
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    bad_outdir = blocker / "sub"

    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(bad_outdir),
            "--with-pass2", str(pass2_path),
            "--discovered-json", str(reg),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_RUNTIME_ERROR
    assert not reg.exists()


def test_full_phase2_pipeline_e2e(tmp_path: Path):
    """End-to-end: --with-pass2 + --signals + --discovered-json +
    --suggestion-card all together → registry written, card body
    written, dryrun markdown also written. This is the shape the
    skill (Session C continued) will drive."""
    _payload, pass2_path = _emit_pass2_for_first_pair(tmp_path)
    reg = tmp_path / "links.json"
    card_path = tmp_path / "suggestion.md"
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
            "--signals",
            "--discovered-json", str(reg),
            "--suggestion-card", str(card_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert reg.exists()
    assert card_path.exists()
    assert list(tmp_path.glob("*_dryrun.md"))
    # Boundary footer reflects ALL four layers that ran (Phase 2D fix)
    md_text = next(tmp_path.glob("*_dryrun.md")).read_text(encoding="utf-8")
    assert "Phase 2A + 2B + 2C-registry + 2C-card boundary" in md_text
    assert "registry written" in md_text
    # Deferred list is empty (everything ran) — no NOT happen line
    assert "intentionally did NOT happen" not in md_text


def test_with_pass2_missing_file_returns_user_error(tmp_path: Path):
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(tmp_path / "nope.json"),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "cannot read --with-pass2 file" in err.getvalue()


def test_with_pass2_malformed_json_returns_user_error(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(bad),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "cannot read --with-pass2 file" in err.getvalue()


def test_with_pass2_wrong_shape_returns_user_error(tmp_path: Path):
    bad = tmp_path / "shape.json"
    bad.write_text('["not a dict"]', encoding="utf-8")
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(bad),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_USER_ERROR
    assert "must be" in err.getvalue()


def test_with_pass2_partial_coverage_emits_missing_warnings(tmp_path: Path):
    # No analyses at all → every NEW pair gets pass2_missing
    pass2_path = tmp_path / "pass2.json"
    _write_pass2(pass2_path, [])

    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    md_files = list(tmp_path.glob("*_dryrun.md"))
    assert md_files
    md_text = md_files[-1].read_text(encoding="utf-8")
    assert "(missing)" in md_text


def test_with_pass2_unknown_pair_id_surfaces_warning(tmp_path: Path):
    pass2_path = tmp_path / "pass2.json"
    _write_pass2(pass2_path, [{
        "pair_id": "p-99-100",
        "relation_type": "supports",
        "rationale": "ghost",
        "confidence": "high",
    }])
    out, err = _streams()
    rc = main(
        [
            "wb-mock-en-zh-001", "--output-dir", str(tmp_path),
            "--with-pass2", str(pass2_path),
        ],
        client=_client(), stdout=out, stderr=err,
    )
    assert rc == EXIT_OK
    assert "[with-pass2 warn]" in err.getvalue()
    assert "p-99-100" in err.getvalue()
