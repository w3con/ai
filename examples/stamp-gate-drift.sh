#!/usr/bin/env bash
# Demonstrate the real settings renderer and stamp gate on a disposable checkout.
set -euo pipefail

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/toolkit-stamp-example.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

HOME_DIR="$TMP_ROOT/ho""me"
HOME_CONFIG="$HOME_DIR/.claude"
mkdir -p "$TMP_ROOT/toolkit/bin" "$TMP_ROOT/toolkit/hooks" "$TMP_ROOT/toolkit/lib" "$HOME_CONFIG"
HOME_ROOT="$(CDPATH= cd -- "$HOME_DIR" && pwd -P)"
cp "$REPO_ROOT/bin/settings-render" "$TMP_ROOT/toolkit/bin/settings-render"
cp "$REPO_ROOT/lib/__init__.py" "$REPO_ROOT/lib/private_config.py" "$TMP_ROOT/toolkit/lib/"
cp "$REPO_ROOT/hooks/harness-stamp-gate.sh" "$TMP_ROOT/toolkit/hooks/"
printf '%s\n' '{"path":"__HOME__/toolkit","hooks":{"PreToolUse":[]}}' > "$TMP_ROOT/toolkit/settings.json.template"

python3 "$TMP_ROOT/toolkit/bin/settings-render" \
  --template "$TMP_ROOT/toolkit/settings.json.template" \
  --home "$HOME_ROOT" \
  --output "$HOME_CONFIG/settings.json" \
  --digest > "$HOME_CONFIG/.harness-stamp"

call_gate() {
  local tool="$1" expected="$2" event decision
  event="$(python3 -c 'import json,sys; print(json.dumps({"tool_name":sys.argv[1],"tool_input":{}}))' "$tool")"
  decision="$(printf '%s' "$event" | HOME="$HOME_ROOT" \
    HARNESS_STAMP_GATE_REPO_DIR="$TMP_ROOT/toolkit" \
    HARNESS_STAMP_GATE_STAMP_FILE="$HOME_CONFIG/.harness-stamp" \
    bash "$TMP_ROOT/toolkit/hooks/harness-stamp-gate.sh" | \
    python3 -c 'import json,sys; print(json.load(sys.stdin)["hookSpecificOutput"]["permissionDecision"])')"
  [ "$decision" = "$expected" ] || {
    printf 'stamp-gate example failed: %s expected %s, got %s\n' "$tool" "$expected" "$decision" >&2
    return 1
  }
}

call_gate Bash allow
python3 - "$HOME_CONFIG/settings.json" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
settings = json.loads(path.read_text(encoding="utf-8"))
settings["example_drift"] = True
path.write_text(json.dumps(settings, sort_keys=True, indent=2) + "\n", encoding="utf-8")
PY
call_gate Bash deny
call_gate Read allow
printf '%s\n' 'stamp-gate example: installed-settings drift denied; read-only recovery remained available.'
