#!/usr/bin/env bash
# git-sync-notice.sh — SessionStart hook: name every repository whose local branch has
# drifted from its remote-tracking ref, reading only the refs already on disk, and kick
# off a rate-limited background fetch so a LATER session sees fresher refs than this one.
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
# What it never does: fail the session, or wait on the network. A repository that does
#   not exist, is not a git repository, has no remote-tracking branch configured (no
#   remote, or a local branch that tracks nothing), or is on a detached head is skipped in
#   silence for the reporting step — none of those is "drift", and this hook has no
#   opinion about any of them.
#
# The background fetch (HRN-155.10): after reporting, this hook considers, for each
# repository that HAS a remote configured, whether it is time to refresh that repository's
# own remote-tracking refs. It records the UNIX timestamp of its last fetch ATTEMPT (not
# completion — a fetch that never returns must not be retried forever, and this hook never
# waits to find out whether one succeeded) in one JSON file per repository under
# GIT_SYNC_NOTICE_STATE_DIR, keyed on a sanitised form of the repository's own path. When
# the last recorded attempt is more recent than GIT_SYNC_NOTICE_FETCH_INTERVAL seconds ago,
# nothing happens. Otherwise the timestamp is written FIRST, synchronously, in the
# foreground — so two sessions starting close together never both decide to fetch the same
# repository — and only then is the actual `git fetch` launched, detached from this
# process (`nohup … & disown`) so this hook can exit immediately without waiting for it.
# Its result becomes visible only through the on-disk refs it updates, which the reporting
# step above always reads fresh on its own next run — in a LATER session, never this one.
#
# GIT_SYNC_NOTICE_REPOS            space-separated list of repository paths to check;
#                                  default: "$HOME/Dev/ai $HOME/Dev/app". Overridable so
#                                  the test suite never touches those two real checkouts.
# GIT_SYNC_NOTICE_STATE_DIR        directory the per-repository last-fetch-attempt
#                                  timestamps are recorded under; default: ~/.claude.
#                                  Overridable so the test suite never touches the real
#                                  ~/.claude.
# GIT_SYNC_NOTICE_FETCH_INTERVAL   seconds between background fetch attempts for the same
#                                  repository; default: 14400 (four hours). Overridable so
#                                  the test suite can prove the interval without waiting
#                                  four hours.

set -u

# 2026-08-13: the project checkout is not at the same path on both machines, so it is
# named by AI_APP_REPO where that is set and otherwise resolved to the first known
# checkout location that actually exists here, rather than assumed to be $HOME/Dev/app.
_app_repo="${AI_APP_REPO:-}"
if [ -z "$_app_repo" ]; then
  for _candidate in "$HOME/Dev/app" "$HOME/Dev/validite/validite-app" \
                    "/Volumes/SSD/Dev/validite/validite-app"; do
    if [ -d "$_candidate/.git" ]; then _app_repo="$_candidate"; break; fi
  done
fi
REPOS="${GIT_SYNC_NOTICE_REPOS:-$HOME/Dev/ai${_app_repo:+ $_app_repo}}"
STATE_DIR="${GIT_SYNC_NOTICE_STATE_DIR:-$HOME/.claude}"
FETCH_INTERVAL="${GIT_SYNC_NOTICE_FETCH_INTERVAL:-14400}"

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

# The per-repository state-file name: every character that is not a letter, digit,
# underscore or hyphen becomes an underscore, so an arbitrary absolute path turns into one
# safe filename component. hooks/git-sync-notice.test.py computes this exact same name
# independently, to seed and read back one repository's own record directly.
state_file_for() {
  local repo="$1" key
  key="$(printf '%s' "$repo" | tr -c 'A-Za-z0-9_-' '_')"
  printf '%s/git-sync-notice-%s.json' "$STATE_DIR" "$key"
}

maybe_fetch() {
  local repo="$1"

  [ -e "$repo/.git" ] || return 0
  git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
  # No remote configured at all — nothing this step could ever fetch.
  git -C "$repo" remote 2>/dev/null | grep -q . || return 0

  mkdir -p "$STATE_DIR" >/dev/null 2>&1 || return 0

  local state_file now last
  state_file="$(state_file_for "$repo")"
  now="$(date +%s)"
  last="$(python3 -c '
import json, sys
try:
    print(int(float(json.load(open(sys.argv[1])).get("last_attempt", 0))))
except Exception:
    print(0)
' "$state_file" 2>/dev/null)"
  [ -n "$last" ] || last=0

  if [ $(( now - last )) -lt "$FETCH_INTERVAL" ]; then
    return 0
  fi

  # Record the attempt FIRST, in the foreground, before anything is backgrounded — this
  # is what makes the interval race-free between sessions starting close together, and
  # what lets the test suite check this file immediately after the hook process exits
  # rather than racing a detached child it never waits for.
  printf '{"last_attempt": %s}\n' "$now" > "$state_file" 2>/dev/null

  # Detach the actual fetch completely: a subshell backgrounds it and exits immediately
  # without waiting, nohup keeps it alive past this process's own exit, and disown drops
  # it from this shell's job table so no later `wait` or shell exit touches it.
  ( nohup git -C "$repo" fetch --quiet >/dev/null 2>&1 & disown ) >/dev/null 2>&1
}

for repo in $REPOS; do
  report_repo "$repo"
done

for repo in $REPOS; do
  maybe_fetch "$repo"
done

exit 0
