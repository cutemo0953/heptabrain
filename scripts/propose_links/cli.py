"""Phase 1 + Phase 2 CLI entry — `python -m scripts.propose_links.cli <whiteboard>`.

Phase 1 (dry-run): inventory + TF-IDF prefilter + connection diff →
markdown only.

Phase 2A: --emit-pairs writes pair contexts for LLM Pass 2; --with-pass2
reads LLM results and merges into the markdown.

Remaining Phase 2+ flags (--mda / --audit-only / --max-links) and the
journal flag are still trapped with a friendly "not in this scope"
message.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.lib.mcp_client import (
    FakeHeptabaseMCPClient,
    HeptabaseMCPClient,
    MCPClient,
)
from scripts.propose_links.connection_diff import classify_pairs, diff_summary
from scripts.propose_links.discovery import (
    AmbiguousWhiteboardError,
    WhiteboardNotFoundError,
    discover_whiteboard,
)
from scripts.propose_links.inventory import build_inventory
from scripts.propose_links.maturity_detect import detect_maturity
from scripts.propose_links.output import dryrun_filename, render_dryrun_markdown
from scripts.propose_links.pass2_merge import emit_pair_contexts, merge_pass2
from scripts.propose_links.tfidf_prefilter import (
    assert_cjk_gate,
    build_tfidf_prefilter,
)
from scripts.registry.atomic_write import atomic_write_json

EXIT_OK = 0
EXIT_USER_ERROR = 2
EXIT_RUNTIME_ERROR = 1


PHASE_2_PLUS_FLAGS = {
    "--mda": "MDA 4D sketch (spec 04 §2.4)",
    "--journal": "append summary to today's Heptabase Journal (spec 04 §4.3)",
    "--suggestion-card": "create 🗂️ suggestion card in whiteboard (spec 04 §4.5)",
    "--audit-only": "audit-only mode for canonical maturity (spec 04 §3)",
    "--max-links": "limit proposed link count (spec 04 §3)",
}


def _exit_phase2_notimpl(parser: argparse.ArgumentParser, flag: str) -> None:
    purpose = PHASE_2_PLUS_FLAGS.get(flag, "Phase 2+ feature")
    parser.exit(
        2,
        f"error: {flag} is not in Phase 1 scope ({purpose}). "
        f"See docs/IMPLEMENTATION_PLAN_PHASE_0_1.md §7 for deferred scope.\n",
    )


class _Phase2NotImplemented(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        _exit_phase2_notimpl(parser, option_string)


def _intercept_phase2_value_form(parser: argparse.ArgumentParser, argv: list[str]) -> None:
    """Catch the `--flag=value` form of Phase 2+ flags before argparse sees
    them — argparse treats `nargs=0` actions as not accepting `=value` and
    would surface a generic 'ignored explicit argument' error otherwise.
    Per Codex P2 #2 review 2026-04-27.
    """
    for tok in argv:
        if not tok.startswith("--"):
            continue
        flag, _, _value = tok.partition("=")
        if flag in PHASE_2_PLUS_FLAGS:
            _exit_phase2_notimpl(parser, flag)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="propose-links",
        description="Cyberbrain Phase 1 propose-links dry-run.",
    )
    p.add_argument("whiteboard", help="Whiteboard id or unique name keyword")
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="(Phase 1: always on; flag accepted for forward compatibility)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("propose_links"),
        help="Directory to write dry-run markdown (default: propose_links/)",
    )
    p.add_argument(
        "--maturity-registry",
        type=Path,
        default=None,
        help="Path to whiteboard_maturity.json (optional)",
    )
    p.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Load FakeMCPClient from this fixture JSON (testing/dev only)",
    )
    p.add_argument(
        "--no-cjk-gate",
        action="store_true",
        help="Skip the CJK score-spread gate (escape hatch; default off)",
    )
    # Phase 2A: emit pair contexts for LLM Pass 2
    p.add_argument(
        "--emit-pairs",
        type=Path,
        default=None,
        help=(
            "[Phase 2A] Write NEW pair contexts as JSON to this path and exit "
            "(skips markdown render). Used by .claude/commands/propose-links.md "
            "to hand off pairs to Claude native LLM Pass 2."
        ),
    )
    # Phase 2A: merge LLM Pass 2 results back into the markdown
    p.add_argument(
        "--with-pass2",
        type=Path,
        default=None,
        help=(
            "[Phase 2A] Path to a Pass 2 results JSON "
            "({\"analyses\": [{pair_id, relation_type, rationale, "
            "confidence, evidence_kind}, ...]}). Merges into the dry-run "
            "markdown so each NEW pair carries relation_type + rationale + "
            "confidence."
        ),
    )
    # Phase 2+ flags surface a friendly "not yet implemented" message
    # (item 8 self-review fix — was mismatch between docstring and CLI surface)
    for flag in PHASE_2_PLUS_FLAGS:
        p.add_argument(
            flag,
            action=_Phase2NotImplemented,
            nargs=0 if flag != "--max-links" else "?",
            help=f"[Phase 2+] {PHASE_2_PLUS_FLAGS[flag]}",
        )
    return p


def _build_client(fixture: Path | None) -> MCPClient:
    if fixture is not None:
        return FakeHeptabaseMCPClient(fixture)
    return HeptabaseMCPClient()


def main(
    argv: list[str] | None = None,
    *,
    client: MCPClient | None = None,
    stdout: Any = None,
    stderr: Any = None,
) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr

    parser = build_parser()
    # Pre-scan for Phase 2+ `--flag=value` form before argparse rejects it
    # with a less-friendly "ignored explicit argument" error
    _intercept_phase2_value_form(parser, list(argv) if argv is not None else sys.argv[1:])
    args = parser.parse_args(argv)

    if client is not None:
        mcp = client
    else:
        try:
            mcp = _build_client(args.fixture)
        except NotImplementedError as e:
            print(f"error: {e}", file=err)
            print(
                "Phase 1 CLI does not yet wire the live Heptabase MCP. "
                "Use --fixture <path> for testing, or call modules directly "
                "(see scripts/propose_links/smoke_run.py).",
                file=err,
            )
            return EXIT_USER_ERROR

    # Step 1: discover whiteboard
    try:
        wb_match = discover_whiteboard(mcp, args.whiteboard)
    except WhiteboardNotFoundError as e:
        print(f"error: {e}", file=err)
        return EXIT_USER_ERROR
    except AmbiguousWhiteboardError as e:
        print(f"error: {e}", file=err)
        print("Pass an exact whiteboard id to disambiguate.", file=err)
        return EXIT_USER_ERROR
    except ValueError as e:
        print(f"error: {e}", file=err)
        return EXIT_USER_ERROR
    except NotImplementedError as e:
        # Real client without wiring (Codex P1 #1 fix — friendly exit
        # path for the default-client-not-wired case)
        print(f"error: {e}", file=err)
        print(
            "Phase 1 CLI does not yet wire the live Heptabase MCP. "
            "Use --fixture <path> for testing, or call modules directly "
            "(see scripts/propose_links/smoke_run.py).",
            file=err,
        )
        return EXIT_USER_ERROR

    # Step 2: inventory
    inventory = build_inventory(wb_match["id"], mcp)

    # Step 3: scale-tier guard
    tier = inventory["scale_tier"]
    if tier == "hard_stop":
        print(
            f"error: whiteboard has {inventory['card_count']} analyzable cards "
            "(>50). Split into sections via Heptabase UI or narrow scope, then "
            "re-run.",
            file=err,
        )
        return EXIT_USER_ERROR

    # Step 4: maturity detect
    maturity = detect_maturity(inventory, args.maturity_registry)
    mat, _src = maturity

    # Step 5: maturity guard
    if mat == "seed":
        print(
            f"error: whiteboard maturity is 'seed' ({inventory['card_count']} "
            "cards). Add more cards (≥5) before requesting propose-links.",
            file=err,
        )
        return EXIT_USER_ERROR
    if mat == "canonical":
        print(
            "warning: whiteboard maturity is 'canonical' (stable). Phase 1 "
            "propose-links is informational; do not bulk-apply suggestions to a "
            "stable whiteboard.",
            file=err,
        )

    # Step 6: TF-IDF prefilter
    pair_scores, diagnostics = build_tfidf_prefilter(inventory["cards"])

    # Step 7: CJK gate (unless escaped)
    if not args.no_cjk_gate:
        try:
            assert_cjk_gate(diagnostics)
        except RuntimeError as e:
            print(f"error: {e}", file=err)
            print(
                "Use --no-cjk-gate to bypass during debugging, but fix the "
                "tokenizer before relying on these scores.",
                file=err,
            )
            return EXIT_RUNTIME_ERROR

    # Step 7.5: connection diff (Phase 2.1) — classify each proposed pair
    # against existing whiteboard connections (NEW / EXISTS / REDUNDANT)
    classified = classify_pairs(
        pair_scores, inventory["cards"], inventory["existing_connections"]
    )
    summary = diff_summary(classified)

    # Phase 2A: --emit-pairs short-circuits before markdown render. Skill
    # (.claude/commands/propose-links.md) calls CLI twice; the first call
    # emits pair contexts for Claude's native LLM Pass 2.
    if args.emit_pairs is not None:
        contexts = emit_pair_contexts(classified, inventory["cards"])
        payload = {
            "whiteboard_id": inventory["whiteboard_id"],
            "whiteboard_name": inventory["whiteboard_name"],
            "pairs": contexts,
        }
        try:
            atomic_write_json(args.emit_pairs, payload)
        except OSError as e:
            print(
                f"error: cannot write pair contexts to {args.emit_pairs}: {e}",
                file=err,
            )
            return EXIT_RUNTIME_ERROR
        print(
            f"[emit-pairs] wrote {len(contexts)} NEW pair contexts to "
            f"{args.emit_pairs}",
            file=err,
        )
        return EXIT_OK

    # Phase 2A: --with-pass2 merges LLM analyses into the classified pairs
    # before markdown render. Errors here are user errors (bad path / shape);
    # render still runs without enrichment if the user wanted dry-run.
    enriched: list[dict[str, Any]] | None = None
    if args.with_pass2 is not None:
        try:
            with args.with_pass2.open("r", encoding="utf-8") as f:
                pass2_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: cannot read --with-pass2 file: {e}", file=err)
            return EXIT_USER_ERROR
        if not isinstance(pass2_data, dict):
            print(
                "error: --with-pass2 file must be a JSON object "
                f"({{whiteboard_id, analyses}}); got {type(pass2_data).__name__}",
                file=err,
            )
            return EXIT_USER_ERROR
        # Codex P1.1 — whiteboard_id cross-check is the outer-envelope
        # snapshot-drift guard. If absent, warn (back-compat); if present
        # and mismatched, fail closed.
        envelope_wb = pass2_data.get("whiteboard_id")
        if envelope_wb is None:
            print(
                "[with-pass2 warn] envelope has no whiteboard_id; "
                "skipping snapshot-drift outer guard (per-pair from_id/to_id "
                "check still runs)",
                file=err,
            )
        elif envelope_wb != inventory["whiteboard_id"]:
            print(
                "error: --with-pass2 envelope whiteboard_id "
                f"{envelope_wb!r} does not match inventory whiteboard_id "
                f"{inventory['whiteboard_id']!r}; refusing to merge "
                "across snapshots (Codex P1.1 snapshot-drift guard)",
                file=err,
            )
            return EXIT_USER_ERROR
        analyses = pass2_data.get("analyses")
        if not isinstance(analyses, list):
            print(
                "error: --with-pass2 file must be {\"analyses\": [...]}; "
                f"got analyses={type(analyses).__name__}",
                file=err,
            )
            return EXIT_USER_ERROR
        enriched, warnings = merge_pass2(
            classified, analyses, cards=inventory["cards"]
        )
        for w in warnings:
            print(f"[with-pass2 warn] {w}", file=err)

    # Step 8: render markdown
    md = render_dryrun_markdown(
        inventory,
        maturity,
        classified,
        diagnostics,
        status_summary=summary,
        enriched_pairs=enriched,
    )
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        # Same-day re-run suffix per spec §4.1 (item 5 self-review fix)
        out_path = args.output_dir / dryrun_filename(
            inventory["whiteboard_name"], output_dir=args.output_dir
        )
        out_path.write_text(md, encoding="utf-8")
    except OSError as e:
        print(
            f"error: cannot write dry-run output to {args.output_dir}: {e}",
            file=err,
        )
        return EXIT_RUNTIME_ERROR

    # Step 9: human-readable echo
    print(md, file=out)
    print(f"\n[dry-run written to {out_path}]", file=err)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
