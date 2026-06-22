#!/usr/bin/env bash
# session-write-gate.sh — Stop hook.
# Blocks finishing the turn unless the active session's current.md changed since
# the turn began (snapshot taken by session-snapshot.sh on UserPromptSubmit).
# This makes it impossible to answer in chat without writing to current.md.
#
# exit 0 = allow stop. exit 2 = block (stderr is fed back as the reason, the
# model continues and must act). Loop-safe: if already in a stop-hook
# continuation (stop_hook_active), allow, so we never wedge the session.
#
# Bypass: set CLAUDE_GATE_BYPASS=1.

[ "${CLAUDE_GATE_BYPASS:-}" = "1" ] && exit 0

STATE_DIR="${TMPDIR:-/tmp}/claude-session-write-gate"
STDIN_DATA="$(cat)"

# Parse session_id and stop_hook_active in one pass (single-quoted python: no shell
# interpolation, so nothing in the JSON or the keys can corrupt the program).
PARSED="$(printf '%s' "$STDIN_DATA" | python3 -c 'import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print(d.get("session_id", "nosid"))
print(d.get("stop_hook_active", False))' 2>/dev/null)"
SID="$(printf '%s\n' "$PARSED" | sed -n 1p)"
ACTIVE="$(printf '%s\n' "$PARSED" | sed -n 2p)"
[ -n "$SID" ] || SID="nosid"

# Already inside a stop-hook continuation → don't loop.
[ "$ACTIVE" = "True" ] && exit 0

SNAP="$STATE_DIR/$SID.snap"
# No snapshot, or empty (no active session this turn) → nothing to enforce.
[ -s "$SNAP" ] || exit 0

FILE="$(sed -n 1p "$SNAP")"
OLD="$(sed -n 2p "$SNAP")"
[ -f "$FILE" ] || exit 0

NEW="$(shasum -a 256 "$FILE" | awk '{print $1}')"

if [ "$NEW" = "$OLD" ]; then
  echo "BLOCKED by session-write-gate: current.md was not updated this turn ($FILE). Every answer must be written into current.md before you finish — update the status line and the relevant section (Findings / Open Questions / Decisions), then respond." >&2
  exit 2
fi

exit 0
