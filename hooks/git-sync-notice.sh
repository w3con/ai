#!/usr/bin/env bash
# Compare configured repositories with their already-fetched upstream refs, report drift,
# and launch a rate-limited detached fetch for later sessions. Optional clean-tree fast-
# forwards are allowed only for repositories explicitly listed in private configuration.
# Defaults watch only this toolkit checkout and never pull any repository. Missing or
# invalid repositories are ignored; this notice never blocks session startup.
#
# Environment overrides are intended for isolated tests:
# GIT_SYNC_NOTICE_REPOS, GIT_SYNC_NOTICE_STATE_DIR, GIT_SYNC_NOTICE_FETCH_INTERVAL,
# GIT_SYNC_NOTICE_PULL_REPOS, and GIT_SYNC_NOTICE_STALE_DAYS.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MIGRATION_PAUSE_FILE="$(dirname "$REPO_ROOT")/.$(basename "$REPO_ROOT").migration/sync.paused"
if [ -f "$MIGRATION_PAUSE_FILE" ]; then
  # The migrator owns this sibling marker for the complete switch interval. The old
  # installation is also paused in settings before the first directory rename; this
  # check makes every newly installed hook honor the same external maintenance window.
  cat >/dev/null 2>&1 || true
  exit 0
fi
SYNC_CONFIG="$(python3 - "$REPO_ROOT" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
try:
    from lib.private_config import load
    print(json.dumps(load(sys.argv[1]).get("sync", {})))
except Exception:
    print("{}")
PY
)"
SYNC_REPOS="$(python3 -c 'import json,sys; print(" ".join(json.loads(sys.argv[1]).get("repositories", [])))' "$SYNC_CONFIG")"
SYNC_PULL="$(python3 -c 'import json,sys; print(" ".join(json.loads(sys.argv[1]).get("pull_repositories", [])))' "$SYNC_CONFIG")"
SYNC_INTERVAL="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("fetch_interval", 14400))' "$SYNC_CONFIG")"
REPOS="${GIT_SYNC_NOTICE_REPOS:-${SYNC_REPOS:-$REPO_ROOT}}"
STATE_DIR="${GIT_SYNC_NOTICE_STATE_DIR:-$HOME/.cache/ai-toolkit/git-sync}"
FETCH_INTERVAL="${GIT_SYNC_NOTICE_FETCH_INTERVAL:-$SYNC_INTERVAL}"
PULL_REPOS="${GIT_SYNC_NOTICE_PULL_REPOS-$SYNC_PULL}"
STALE_DAYS="${GIT_SYNC_NOTICE_STALE_DAYS:-7}"

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

may_pull() {
  local repo="$1" candidate
  for candidate in $PULL_REPOS; do
    [ "$candidate" = "$repo" ] && return 0
  done
  return 1
}

maybe_pull() {
  local repo="$1"

  may_pull "$repo" || return 0
  [ -e "$repo/.git" ] || return 0
  git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
  git -C "$repo" symbolic-ref -q HEAD >/dev/null 2>&1 || return 0

  local upstream
  upstream="$(git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"
  [ -n "$upstream" ] || return 0

  # Any uncommitted change at all, tracked or untracked — leave the tree alone. Somebody is
  # working in it, and a fast-forward is never worth surprising them.
  [ -z "$(git -C "$repo" status --porcelain 2>/dev/null)" ] || return 0

  local counts ahead behind
  counts="$(git -C "$repo" rev-list --left-right --count "HEAD...@{upstream}" 2>/dev/null)" || return 0
  ahead="$(printf '%s' "$counts" | awk '{print $1}')"
  behind="$(printf '%s' "$counts" | awk '{print $2}')"
  [ -n "$ahead" ] && [ -n "$behind" ] || return 0

  # Nothing to move onto, or a history that has diverged — `--ff-only` would refuse the
  # second case anyway; refusing it here keeps the silence deliberate rather than incidental.
  [ "$behind" != "0" ] || return 0
  [ "$ahead" = "0" ] || return 0

  git -C "$repo" merge --ff-only --quiet "@{upstream}" >/dev/null 2>&1 || return 0
  echo "git-sync-notice: $repo fast-forwarded $behind commit(s) onto $upstream — ~/.claude reaches this checkout by symlink, so the new rules, hooks, agents and skills are already live."
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

# A clone nobody has fetched for a long time: the drift report above cannot see a single
# commit that arrived after the last fetch, so a badly stale clone reports "no drift" while
# being hundreds of commits behind. A clone that was never fetched at all is silent here —
# it is a fresh clone, and a fresh clone is current by construction.
report_stale_fetch() {
  local repo="$1" fetch_head age_days
  [ "$STALE_DAYS" != "0" ] || return 0
  [ -e "$repo/.git" ] || return 0
  git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
  fetch_head="$(git -C "$repo" rev-parse --absolute-git-dir 2>/dev/null)/FETCH_HEAD"
  [ -f "$fetch_head" ] || return 0
  fetch_mtime="$(python3 -c 'import os,sys; print(int(os.stat(sys.argv[1]).st_mtime))' \
    "$fetch_head" 2>/dev/null || echo 0)"
  age_days=$(( ( $(date +%s) - fetch_mtime ) / 86400 ))
  if [ "$age_days" -ge "$STALE_DAYS" ]; then
    echo "git-sync-notice: $repo was last fetched $age_days day(s) ago — the drift reported for it is only as fresh as that fetch."
  fi
}

# Two working copies of ONE repository, under two directory names. Git gives no sign of this
# on either side: each is a complete, valid, internally consistent repository. They are
# recognised by sharing a root commit while their origin URLs differ — which is what a
# renamed remote produces, since the old address keeps resolving to the same repository.
# Only network remotes are compared: a remote that is a local path is a fixture or a mirror,
# and two clones of one local bare repository are a normal, deliberate arrangement.
report_duplicate_clones() {
  local repo url root
  local -a paths=() urls=() roots=()
  for repo in $REPOS; do
    [ -e "$repo/.git" ] || continue
    git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || continue
    url="$(git -C "$repo" config --get remote.origin.url 2>/dev/null)"
    case "$url" in
      ""|/*|file://*|.*) continue ;;
    esac
    root="$(git -C "$repo" rev-list --max-parents=0 HEAD 2>/dev/null | tail -1)"
    [ -n "$root" ] || continue
    local i=0
    while [ "$i" -lt "${#paths[@]}" ]; do
      if [ "${roots[$i]}" = "$root" ] && [ "${urls[$i]}" != "$url" ]; then
        echo "git-sync-notice: ${paths[$i]} and $repo are two working copies of ONE repository — same history, different remote addresses (${urls[$i]} and $url). Whichever you open, the other holds its own copies of the same files and they drift apart in silence."
      fi
      i=$(( i + 1 ))
    done
    paths+=("$repo"); urls+=("$url"); roots+=("$root")
  done
}

# The fast-forward runs before the reporting, so the drift reported below is what remains
# after it rather than what it has just resolved.
for repo in $REPOS; do
  maybe_pull "$repo"
done

for repo in $REPOS; do
  report_repo "$repo"
done

for repo in $REPOS; do
  report_stale_fetch "$repo"
done

report_duplicate_clones

for repo in $REPOS; do
  maybe_fetch "$repo"
done

exit 0
