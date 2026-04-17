#!/usr/bin/env bash
# install.sh — copy Cyberbrain slash command + memory skeleton into ~/.claude/
#
# Safe to re-run. Won't clobber:
#   - an existing slash command with the same name (prompts for overwrite)
#   - an existing ~/.claude/memory/ directory with any content
#   - existing registry JSON files (only creates when missing)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"

echo "HeptaBrain install"
echo "  Repo:         $REPO_ROOT"
echo "  Claude home:  $CLAUDE_HOME"
echo

# --- 1. Slash command ---

COMMANDS_DIR="$CLAUDE_HOME/commands"
mkdir -p "$COMMANDS_DIR"
for cmd_file in "$REPO_ROOT/.claude/commands/"*.md; do
  base="$(basename "$cmd_file")"
  TARGET_CMD="$COMMANDS_DIR/$base"

  if [ -f "$TARGET_CMD" ]; then
    if cmp -s "$cmd_file" "$TARGET_CMD"; then
      echo "✓ $base already up to date"
    else
      printf "! %s exists and differs. Overwrite? [y/N] " "$base"
      read -r reply
      if [[ "$reply" =~ ^[Yy]$ ]]; then
        cp "$cmd_file" "$TARGET_CMD"
        echo "✓ overwrote $base"
      else
        echo "  skipped $base."
      fi
    fi
  else
    cp "$cmd_file" "$TARGET_CMD"
    echo "✓ installed $base"
  fi
done

# --- 2. Memory skeleton ---

MEMORY_DIR="$CLAUDE_HOME/memory"
SOURCE_MEM="$REPO_ROOT/examples/memory"

TEMPLATES_SEEDED=0

# "Meaningful content" = anything other than our two registry JSONs. A dir that
# holds only _heptabrain_registry.json / _heptabase_refs.json is still effectively
# empty from the user's perspective, so we should still seed templates.
meaningful_memory_content() {
  [ -d "$1" ] || return 1
  while IFS= read -r entry; do
    case "$entry" in
      "_heptabrain_registry.json"|"_heptabase_refs.json") continue ;;
      *) return 0 ;;
    esac
  done < <(ls -A "$1" 2>/dev/null)
  return 1
}

if meaningful_memory_content "$MEMORY_DIR"; then
  echo "✓ $MEMORY_DIR already has content — preserving (templates available at $SOURCE_MEM/)"
else
  mkdir -p "$MEMORY_DIR"
  # Copy only the templates + MEMORY.md index, NOT the README.md (that's a repo artifact)
  for f in "$SOURCE_MEM"/*.md "$SOURCE_MEM"/*.json; do
    base="$(basename "$f")"
    [ "$base" = "README.md" ] && continue
    # Skip registries if they already exist (don't clobber real sync history)
    case "$base" in
      _heptabrain_registry.json|_heptabase_refs.json)
        [ -f "$MEMORY_DIR/$base" ] && continue ;;
    esac
    cp "$f" "$MEMORY_DIR/$base"
  done
  echo "✓ seeded $MEMORY_DIR with templates"
  TEMPLATES_SEEDED=1
fi

# --- 3. Registry files (create only if missing) ---

for reg in "_heptabrain_registry.json" "_heptabase_refs.json"; do
  TARGET="$MEMORY_DIR/$reg"
  SOURCE="$SOURCE_MEM/$reg"
  if [ ! -f "$TARGET" ] && [ -f "$SOURCE" ]; then
    cp "$SOURCE" "$TARGET"
    echo "✓ created $TARGET"
  fi
done

echo
echo "Done. Open Claude Code and run:"
echo "    /heptabrain-sync status"
echo
echo "Next steps:"
if [ "$TEMPLATES_SEEDED" = "1" ]; then
  echo "  1. Replace $MEMORY_DIR/user_example.md with your real profile."
  echo "  2. Connect the Heptabase MCP (or adapt the slash command per README)."
  echo "  3. Start writing memory files with appropriate frontmatter — sync is explicit, nothing auto-pushes."
else
  echo "  1. Your existing memory was preserved. If you want to compare with the"
  echo "     templates or copy any, they're at $SOURCE_MEM/"
  echo "  2. Verify your Heptabase MCP is connected, then run /heptabrain-sync status."
fi
