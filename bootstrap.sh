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

# Every target this run failed to deploy. The script exits non-zero when this is
# not empty, because a bootstrap that leaves a target undeployed and still reports
# success is the exact failure this machine lived with for three weeks: the old
# script warned about ~/.claude/hooks and ~/.claude/agents, skipped them, and
# exited 0, so nobody ever learned that the hooks in force were months stale.
FAILURES=()
BACKUP_SUFFIX="backup-$(date +%Y%m%d-%H%M%S)"

fail() {
  echo "FAILED:  $1" >&2
  FAILURES+=("$1")
}

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

# symlink TARGET SOURCE_IN_REPO [preserve]
# Creates or updates a symlink at TARGET pointing to SOURCE_IN_REPO.
# Idempotent: does nothing if the symlink already points to the right place.
#
# A real file or directory sitting at TARGET is moved aside to a timestamped
# backup next to it, and the symlink then takes its place. That is a change from
# the original behaviour, which warned and skipped: skipping is what silently
# froze this machine's hooks and agents at whatever had been hand-placed there,
# because the pre-existing real directories meant the deploy never once ran.
#
# Pass the third argument "preserve" for a target whose contents cannot be
# reconstructed from the repository — the per-project memory directories. Those
# are never moved: a non-empty real one is recorded as a failure for a human to
# resolve, because merging memory is a judgement no script should make.
symlink() {
  local target="$1"
  local source="$2"
  local mode="${3:-replace}"

  if [[ ! -e "$source" && ! -L "$source" ]]; then
    fail "$target — source does not exist in the repository: $source"
    return
  fi

  if [[ -L "$target" ]]; then
    local current
    current="$(readlink "$target")"
    if [[ "$current" == "$source" ]]; then
      echo "[ok]     $target → $source  (already correct)"
      return
    fi
    if [[ $DRY_RUN -eq 0 ]]; then
      rm "$target"
      ln -s "$source" "$target"
      echo "[update] $target → $source  (was → $current)"
    else
      echo "[dry-run] Would update: $target → $source  (currently → $current)"
    fi
    return
  fi

  if [[ -e "$target" ]]; then
    if [[ "$mode" == "preserve" ]]; then
      fail "$target exists, is not a symlink, and holds contents this script must not move. Back it up and remove it by hand, then re-run."
      return
    fi
    local backup="${target}.${BACKUP_SUFFIX}"
    if [[ $DRY_RUN -eq 0 ]]; then
      mv "$target" "$backup"
      ln -s "$source" "$target"
      echo "[replace] $target → $source  (previous contents moved to $backup)"
    else
      echo "[dry-run] Would move $target to $backup, then link it → $source"
    fi
    return
  fi

  if [[ $DRY_RUN -eq 0 ]]; then
    ln -s "$source" "$target"
    echo "[create] $target → $source"
  else
    echo "[dry-run] Would create: $target → $source"
  fi
}

echo "Bootstrapping ~/.claude symlinks from: $REPO_DIR"
echo ""

symlink "$CLAUDE_DIR/CLAUDE.md"              "$REPO_DIR/CLAUDE.md"
symlink "$CLAUDE_DIR/memory"                 "$REPO_DIR/memory"           preserve
symlink "$CLAUDE_DIR/agents"                 "$REPO_DIR/agents"
symlink "$CLAUDE_DIR/hooks"                  "$REPO_DIR/hooks"
symlink "$CLAUDE_DIR/skills"                 "$REPO_DIR/skills"
symlink "$CLAUDE_DIR/statusline-command.sh"  "$REPO_DIR/statusline-command.sh"

# ---------------------------------------------------------------------------
# settings.json is RENDERED, not symlinked.
#
# It is the one deployed file that cannot be identical on both machines: it
# carries absolute paths, and the two machines have different home directories.
# A single committed settings.json is therefore always wrong on at least one of
# them — which is how "Bash(/Users/laptop/Dev/ai/bin/websearch:*)" came to sit
# in the permissions of a machine whose user is not "laptop", silently granting
# nothing. The template holds __HOME__ where the home directory belongs, and
# this step writes the real file. Never hand-edit ~/.claude/settings.json.
# ---------------------------------------------------------------------------
render_settings() {
  local template="$REPO_DIR/settings.json.template"
  local target="$CLAUDE_DIR/settings.json"

  if [[ ! -f "$template" ]]; then
    fail "$target — template not found at $template"
    return
  fi

  local rendered
  rendered="$(sed "s|__HOME__|${HOME}|g" "$template")"

  if [[ "$rendered" == *"__HOME__"* ]]; then
    fail "$target — placeholder __HOME__ survived rendering"
    return
  fi

  if [[ -L "$target" ]]; then
    # An earlier bootstrap symlinked this file into the repo. Writing through
    # the link would edit the committed template's neighbour, so drop the link.
    if [[ $DRY_RUN -eq 0 ]]; then
      rm "$target"
    else
      echo "[dry-run] Would remove the symlink at $target before rendering"
    fi
  elif [[ -f "$target" ]]; then
    if [[ "$rendered" == "$(cat "$target")" ]]; then
      echo "[ok]     $target  (rendered from template, already current)"
      return
    fi
    # A real settings.json that differs from the render is either hand-edited or
    # left by an older harness. It is replaced, but never without a copy: the
    # machine-specific choices it carries are the only record of themselves.
    if [[ $DRY_RUN -eq 0 ]]; then
      cp "$target" "${target}.${BACKUP_SUFFIX}"
      echo "[backup] ${target}.${BACKUP_SUFFIX}"
    else
      echo "[dry-run] Would back up the existing $target before overwriting it"
    fi
  fi

  if [[ $DRY_RUN -eq 0 ]]; then
    printf '%s\n' "$rendered" > "$target"
    echo "[render] $target  (from settings.json.template, __HOME__ → $HOME)"
  else
    echo "[dry-run] Would render: $target from settings.json.template, __HOME__ → $HOME"
  fi
}

render_settings

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
    symlink "$mem_dir" "$shared_memory" preserve
  done
  shopt -u nullglob
}

link_project_memories

# ---------------------------------------------------------------------------
# VALIDITE_VAULT_ROOT — where the business knowledge base lives on THIS machine
#
# The business vault is a separate git repository (git@github.com:validite-eu/org.git)
# checked out at a different absolute path on each of Alex's two machines, and
# bin/card-context in the app repo needs to find it. Rather than guess from the
# machine's name — which changes whenever the machine is renamed or reinstalled —
# this looks for the vault by its own contents: a directory is the vault when it
# holds both kb/CustDev and kb/Strategy. That signature also tells it apart from
# the app repository, which has its own kb/ but none of those collections.
#
# The discovered path is exported from ~/.zshenv, NOT ~/.zshrc. zsh reads .zshrc
# only for interactive shells, and the shells that actually need this variable —
# the ones Claude Code's Bash tool spawns to run bin/card-context — are not
# interactive, so a .zshrc export is invisible to exactly the caller it exists
# for (measured 2026-08-01: `zsh -c` saw nothing, `zsh -i -c` saw the path).
# .zshenv is read by every zsh invocation. The block is delimited by sentinels so
# re-running bootstrap replaces it in place instead of appending a second copy,
# and a block left in .zshrc by an earlier run of this script is removed.
# ---------------------------------------------------------------------------
VAULT_MARKERS=("kb/CustDev" "kb/Strategy")
VAULT_BEGIN="# >>> validite vault root (managed by bootstrap.sh — do not edit by hand) >>>"
VAULT_END="# <<< validite vault root <<<"

is_vault() {
  local dir="$1" marker
  [[ -n "$dir" && -d "$dir" ]] || return 1
  for marker in "${VAULT_MARKERS[@]}"; do
    [[ -d "$dir/$marker" ]] || return 1
  done
  return 0
}

find_vault() {
  local candidates=(
    "${VALIDITE_VAULT_ROOT:-}"
    "$HOME/Documents/Validite"
    "$HOME/Documents/Validité"
    "$HOME/Dev/Validite"
    "$HOME/Dev/Validité"
    "$HOME/Validite"
    "/Volumes/Documents/startup/Validite"
    "/Volumes/Documents/startup/Validité"
  )
  local c
  for c in "${candidates[@]}"; do
    if is_vault "$c"; then printf '%s\n' "$c"; return 0; fi
  done

  # Nothing at a known address: look for the signature itself, shallowly, in the
  # few places a checkout plausibly lives. Depth 3 covers $HOME/<dir>/kb/CustDev.
  local base hit dir
  for base in "$HOME/Documents" "$HOME/Dev" "$HOME" "/Volumes/Documents" "/Volumes/Documents/startup"; do
    [[ -d "$base" ]] || continue
    while IFS= read -r hit; do
      dir="$(dirname "$(dirname "$hit")")"
      if is_vault "$dir"; then printf '%s\n' "$dir"; return 0; fi
    done < <(find "$base" -maxdepth 3 -type d -path '*/kb/CustDev' 2>/dev/null)
  done
  return 1
}

strip_vault_block() {   # remove the sentinel block from a file that should no longer carry it
  local profile="$1"
  [[ -f "$profile" ]] && grep -qF "$VAULT_BEGIN" "$profile" || return 0
  if [[ $DRY_RUN -eq 0 ]]; then
    local tmp
    tmp="$(mktemp)"
    awk -v b="$VAULT_BEGIN" -v e="$VAULT_END" '$0==b{f=1;next} $0==e{f=0;next} !f{print}' "$profile" > "$tmp"
    mv "$tmp" "$profile"
    echo "[update] removed the VALIDITE_VAULT_ROOT block from $profile (it belongs in ~/.zshenv)"
  else
    echo "[dry-run] Would remove the VALIDITE_VAULT_ROOT block from $profile"
  fi
}

write_vault_export() {
  local vault="$1"
  local profile="$HOME/.zshenv"
  local desired="${VAULT_BEGIN}
export VALIDITE_VAULT_ROOT=\"${vault}\"
${VAULT_END}"

  if [[ -f "$profile" ]] && grep -qF "$VAULT_BEGIN" "$profile"; then
    local current
    current="$(awk -v b="$VAULT_BEGIN" -v e="$VAULT_END" '$0==b{f=1} f{print} $0==e{f=0}' "$profile")"
    if [[ "$current" == "$desired" ]]; then
      echo "[ok]     $profile already exports VALIDITE_VAULT_ROOT=$vault"
      return
    fi
    if [[ $DRY_RUN -eq 0 ]]; then
      local tmp
      tmp="$(mktemp)"
      awk -v b="$VAULT_BEGIN" -v e="$VAULT_END" '$0==b{f=1;next} $0==e{f=0;next} !f{print}' "$profile" > "$tmp"
      printf '%s\n' "$desired" >> "$tmp"
      mv "$tmp" "$profile"
      echo "[update] $profile now exports VALIDITE_VAULT_ROOT=$vault"
    else
      echo "[dry-run] Would replace the existing block in $profile with VALIDITE_VAULT_ROOT=$vault"
    fi
    return
  fi

  if [[ $DRY_RUN -eq 0 ]]; then
    printf '\n%s\n' "$desired" >> "$profile"
    echo "[create] $profile now exports VALIDITE_VAULT_ROOT=$vault"
  else
    echo "[dry-run] Would append to $profile: VALIDITE_VAULT_ROOT=$vault"
  fi
}

echo ""
if VAULT_PATH="$(find_vault)"; then
  strip_vault_block "$HOME/.zshrc"
  write_vault_export "$VAULT_PATH"
else
  fail "VALIDITE_VAULT_ROOT — the Validité business vault was not found. Looked for a directory holding both kb/CustDev and kb/Strategy under ~/Documents, ~/Dev, ~, /Volumes/Documents and /Volumes/Documents/startup (depth 3). Clone git@github.com:validite-eu/org.git and re-run, or export VALIDITE_VAULT_ROOT yourself."
fi

# ---------------------------------------------------------------------------
# The stamp is written last, and only on a clean run.
#
# harness-stamp-gate.sh compares this file against HARNESS_VERSION on every tool
# call and blocks the session when they differ, so writing it while any target
# failed would declare a machine deployed that is not. Raising HARNESS_VERSION in
# the repository is therefore what forces every machine to re-run this script.
# ---------------------------------------------------------------------------
write_stamp() {
  local version_file="$REPO_DIR/HARNESS_VERSION"
  local stamp_file="$CLAUDE_DIR/.harness-stamp"

  if [[ ! -f "$version_file" ]]; then
    fail "$stamp_file — no HARNESS_VERSION in the repository at $version_file"
    return
  fi

  local version
  version="$(head -n1 "$version_file" | tr -d '[:space:]')"
  if [[ -z "$version" ]]; then
    fail "$stamp_file — HARNESS_VERSION is empty"
    return
  fi

  if [[ $DRY_RUN -eq 0 ]]; then
    printf '%s\n' "$version" > "$stamp_file"
    echo "[stamp]  $stamp_file = $version"
  else
    echo "[dry-run] Would stamp $stamp_file = $version"
  fi
}

echo ""
if [[ ${#FAILURES[@]} -eq 0 ]]; then
  write_stamp
fi

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  echo "BOOTSTRAP FAILED — ${#FAILURES[@]} target(s) were not deployed:" >&2
  for f in "${FAILURES[@]}"; do
    echo "  - $f" >&2
  done
  echo "" >&2
  echo "Nothing is stamped and the harness stays blocked until every one of these is resolved." >&2
  exit 1
fi

if [[ $DRY_RUN -eq 0 ]]; then
  echo "Done. Verify with: readlink ~/.claude/{CLAUDE.md,memory,agents,hooks,skills,statusline-command.sh,settings.json}"
else
  echo "[dry-run] Done. Run without --dry-run to apply."
fi
