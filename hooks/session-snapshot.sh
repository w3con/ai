#!/usr/bin/env bash
# session-snapshot.sh — UserPromptSubmit hook.
# Snapshots the active session's current.md (sha256) at the start of a turn, so
# the Stop gate (session-write-gate.sh) can tell whether this turn changed it.
#
# Finds the active current.md under either layout: <project>/session/*/current.md
# or <project>/ai/session/*/current.md, picking the one with "Status: active".
# If none is found, writes an empty snapshot so the gate stays inert (no session
# to enforce). Always exits 0 (never blocks prompt submission).

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
STATE_DIR="${TMPDIR:-/tmp}/claude-session-write-gate"
mkdir -p "$STATE_DIR"

STDIN_DATA="$(cat)"
SID="$(printf '%s' "$STDIN_DATA" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("session_id","nosid"))
except Exception: print("nosid")' 2>/dev/null || echo nosid)"

FILE=""
for f in "$PROJECT_DIR"/session/*/current.md "$PROJECT_DIR"/ai/session/*/current.md; do
  [ -f "$f" ] || continue
  if grep -qiE '^Status:[[:space:]]*active' "$f"; then FILE="$f"; fi
done

SNAP="$STATE_DIR/$SID.snap"
if [ -n "$FILE" ]; then
  { printf '%s\n' "$FILE"; shasum -a 256 "$FILE" | awk '{print $1}'; } > "$SNAP"
else
  : > "$SNAP"   # no active session → empty snapshot → gate stays inert
fi

exit 0
