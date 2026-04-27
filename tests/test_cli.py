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
    "flag", ["--mda", "--journal", "--suggestion-card", "--audit-only"]
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
    ["--mda=true", "--journal=foo", "--suggestion-card=anything", "--max-links=10"],
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
