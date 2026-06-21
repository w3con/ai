#!/usr/bin/env bash
# bootstrap.sh — Idempotently recreate ~/.claude symlinks from this repo.
#
# Usage:
#   ./bootstrap.sh          # Apply symlinks (safe — only replaces non-symlinks or wrong symlinks)
#   ./bootstrap.sh --dry-run  # Print what would be created without changing anything
#
# Run this once after a fresh clone on a new machine to wire up Claude Code.
# Requires: this repo must be cloned at an absolute path (no relative invocation from elsewhere).
#
# IMPORTANT: settings.json contains enabledPlugins that may be machine-specific.
# If a plugin is only needed on one machine, comment it out in settings.json with a note
# indicating which machine it applies to, and keep a local override at ~/.claude/settings.local.json
# if Claude Code supports it — otherwise remove the per-machine plugin entry after syncing.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  echo "[dry-run] No changes will be made."
  echo ""
fi

# Guard: verify repo is reachable
if [[ ! -d "$REPO_DIR" ]]; then
  echo "WARNING: Repo directory not found at '$REPO_DIR'. Aborting." >&2
  exit 1
fi

# Guard: warn if repo is on a removable/network volume
if ! df "$REPO_DIR" 2>/dev/null | grep -qv "tmpfs\|overlay\|aufs"; then
  # Best-effort check: if the path starts with /Volumes, warn
  if [[ "$REPO_DIR" == /Volumes/* ]]; then
    echo "WARNING: Repo is on a mounted volume ($REPO_DIR). Make sure it is mounted before running Claude Code." >&2
    echo "         Symlinks will be created now but will be broken if the volume is unmounted." >&2
    echo ""
  fi
fi

# Create ~/.claude if it doesn't exist
if [[ ! -d "$CLAUDE_DIR" ]]; then
  if [[ $DRY_RUN -eq 0 ]]; then
    mkdir -p "$CLAUDE_DIR"
    echo "Created $CLAUDE_DIR"
  else
    echo "[dry-run] Would create: $CLAUDE_DIR"
  fi
fi

# symlink TARGET SOURCE_IN_REPO
# Creates or updates a symlink at TARGET pointing to SOURCE_IN_REPO.
# Idempotent: skips if symlink already points to the right place.
# Warns and skips if TARGET exists and is NOT a symlink (would overwrite real data).
symlink() {
  local target="$1"
  local source="$2"

  if [[ ! -e "$source" && ! -L "$source" ]]; then
    echo "WARNING: Source does not exist: $source (skipping $target)" >&2
    return
  fi

  if [[ -L "$target" ]]; then
    local current
    current="$(readlink "$target")"
    if [[ "$current" == "$source" ]]; then
      echo "[ok]     $target → $source  (already correct)"
      return
    else
      if [[ $DRY_RUN -eq 0 ]]; then
        rm "$target"
        ln -s "$source" "$target"
        echo "[update] $target → $source  (was → $current)"
      else
        echo "[dry-run] Would update: $target → $source  (currently → $current)"
      fi
    fi
  elif [[ -e "$target" ]]; then
    echo "WARNING: $target exists and is NOT a symlink. Skipping to avoid data loss." >&2
    echo "         To migrate, manually back it up and remove it, then re-run bootstrap.sh." >&2
  else
    if [[ $DRY_RUN -eq 0 ]]; then
      ln -s "$source" "$target"
      echo "[create] $target → $source"
    else
      echo "[dry-run] Would create: $target → $source"
    fi
  fi
}

echo "Bootstrapping ~/.claude symlinks from: $REPO_DIR"
echo ""

symlink "$CLAUDE_DIR/CLAUDE.md"              "$REPO_DIR/CLAUDE.md"
symlink "$CLAUDE_DIR/memory"                 "$REPO_DIR/memory"
symlink "$CLAUDE_DIR/agents"                 "$REPO_DIR/agents"
symlink "$CLAUDE_DIR/hooks"                  "$REPO_DIR/hooks"
symlink "$CLAUDE_DIR/skills"                 "$REPO_DIR/skills"
symlink "$CLAUDE_DIR/statusline-command.sh"  "$REPO_DIR/statusline-command.sh"
symlink "$CLAUDE_DIR/settings.json"          "$REPO_DIR/settings.json"

echo ""
if [[ $DRY_RUN -eq 0 ]]; then
  echo "Done. Verify with: readlink ~/.claude/{CLAUDE.md,memory,agents,hooks,skills,statusline-command.sh,settings.json}"
else
  echo "[dry-run] Done. Run without --dry-run to apply."
fi
