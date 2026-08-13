#!/usr/bin/env bash
# git-sync-notice.sh — SessionStart hook: name every repository whose local branch has
# drifted from its remote-tracking ref, reading only the refs already on disk.
#
# HRN-155's own "Reasons to exist": two machines' checkouts of ~/Dev/ai were each
# internally consistent — the stamp compares a checkout against its OWN ~/.claude, never
# against the server — and still drifted 21 commits apart over a week, because nothing on
# either machine was told the other had moved. This hook is that telling: at the start of
# a session it reports, for each repository it is asked to watch, how many commits its
# local branch is ahead of and behind its remote-tracking branch, using whatever refs are
# already on disk — it never fetches inline, because a SessionStart hook that waited on
# the network would slow down or hang every single session start.
#
# What it prints: one line per repository whose local branch and remote-tracking branch
#   disagree, naming the repository path and both counts — "N ahead" and "M behind" —
#   even when one of the two is zero. A repository whose branch agrees with its remote
#   prints nothing at all.
# What it never does: fail the session. A repository that does not exist, is not a git
#   repository, has no remote-tracking branch configured (no remote, or a local branch
#   that tracks nothing), or is on a detached head is skipped in silence — none of those
#   is "drift", and this hook has no opinion about any of them. It also never fetches
#   (HRN-155.10 adds a separate, rate-limited, backgrounded fetch on top of this file,
#   through the ordinary candidate-and-install route — this founding version reports only).
#
# GIT_SYNC_NOTICE_REPOS   space-separated list of repository paths to check; default:
#                         "$HOME/Dev/ai $HOME/Dev/app". Overridable so the test suite
#                         never touches those two real checkouts.

set -u

REPOS="${GIT_SYNC_NOTICE_REPOS:-$HOME/Dev/ai $HOME/Dev/app}"

# The SessionStart payload on stdin carries nothing this hook needs; read and discard it
# so Claude Code never sees a broken pipe.
cat >/dev/null 2>&1 || true

report_repo() {
  local repo="$1"

  # Missing entirely, or not a git repository (no .git file or directory) — skip.
  [ -e "$repo/.git" ] || return 0
  git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0

  # Detached head — there is no local branch to compare, so there is nothing to report.
  git -C "$repo" symbolic-ref -q HEAD >/dev/null 2>&1 || return 0

  # No remote-tracking branch configured for the current branch (no remote at all, or a
  # local branch that was never set to track one) — nothing to compare against.
  local upstream
  upstream="$(git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"
  [ -n "$upstream" ] || return 0

  # --left-right --count HEAD...@{upstream} prints "<ahead> <behind>": commits reachable
  # only from HEAD (left) come first, commits reachable only from the upstream ref
  # (right) come second. This reads refs already fetched onto disk; it never talks to
  # the network itself.
  local counts ahead behind
  counts="$(git -C "$repo" rev-list --left-right --count "HEAD...@{upstream}" 2>/dev/null)" || return 0
  ahead="$(printf '%s' "$counts" | awk '{print $1}')"
  behind="$(printf '%s' "$counts" | awk '{print $2}')"
  [ -n "$ahead" ] && [ -n "$behind" ] || return 0

  if [ "$ahead" != "0" ] || [ "$behind" != "0" ]; then
    echo "git-sync-notice: $repo is $ahead commit(s) ahead and $behind commit(s) behind $upstream."
  fi
}

for repo in $REPOS; do
  report_repo "$repo"
done

exit 0
