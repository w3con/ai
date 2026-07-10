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

# ---------------------------------------------------------------------------
# Per-project memory symlinks
#
# Why this exists: the harness gives every project its own real directory at
# ~/.claude/projects/<slug>/memory the first time it needs one. But there is
# only ONE memory store for all projects — $CLAUDE_DIR/memory, symlinked to
# $REPO_DIR/memory above — because a lesson learned in one project (how
# Claude should behave, where Alex corrected it) is not project-specific and
# should be visible everywhere. So every <slug>/memory directory must itself
# be a symlink to that same store, not a separate real directory. This also
# matters for the memory-store-guard.sh PreToolUse hook: it only allows
# writes whose real path resolves inside $REPO_DIR/memory, so a project
# whose memory/ is still a real directory would have every write to it
# rejected until this symlink is in place.
#
# We only ever repair two known-safe cases here: a real directory that is
# already empty (nothing to lose), and a symlink pointing at the wrong
# place (e.g. a stale/broken path from before a project was renamed — this
# happened for Validité, whose old symlink pointed at a since-abandoned
# path). A real, non-empty memory/ directory is deliberately left alone: we
# don't know whether its contents are safe to discard or need a human to
# merge them by hand, so we hand it to symlink()'s own "exists and is not a
# symlink" branch, which warns and skips rather than guessing.
# ---------------------------------------------------------------------------
link_project_memories() {
  local projects_dir="$CLAUDE_DIR/projects"
  local shared_memory="$REPO_DIR/memory"

  if [[ ! -d "$projects_dir" ]]; then
    return
  fi

  shopt -s nullglob
  local mem_dir
  for mem_dir in "$projects_dir"/*/memory; do
    # A real (non-symlink) directory with nothing in it can be safely
    # cleared out of the way so that symlink() below takes its normal
    # "target doesn't exist yet -> create" path, instead of its "target
    # exists and is not a symlink -> warn and skip" path. This emptiness
    # check is new logic symlink() doesn't have; the actual protective
    # decision (touch it or not) is still made entirely inside symlink()
    # itself, not duplicated here.
    if [[ -d "$mem_dir" && ! -L "$mem_dir" && -z "$(ls -A "$mem_dir" 2>/dev/null)" ]]; then
      if [[ $DRY_RUN -eq 0 ]]; then
        rmdir "$mem_dir"
      else
        echo "[dry-run] Would replace empty dir with symlink: $mem_dir -> $shared_memory"
        continue
      fi
    fi
    symlink "$mem_dir" "$shared_memory"
  done
  shopt -u nullglob
}

link_project_memories

echo ""
if [[ $DRY_RUN -eq 0 ]]; then
  echo "Done. Verify with: readlink ~/.claude/{CLAUDE.md,memory,agents,hooks,skills,statusline-command.sh,settings.json}"
else
  echo "[dry-run] Done. Run without --dry-run to apply."
fi
