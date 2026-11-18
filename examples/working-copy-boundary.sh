#!/usr/bin/env bash
# Exercise the real coordinator source boundary against synthetic paths/configuration.
set -euo pipefail

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/toolkit-boundary-example.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

SOURCE_ROOT="$TMP_ROOT/workspace/product/source"
mkdir -p "$SOURCE_ROOT" "$TMP_ROOT/workspace/docs"
printf '%s\n' '{"coordinator_source_roots":[]}' > "$TMP_ROOT/config.json"
python3 - "$TMP_ROOT/config.json" "$SOURCE_ROOT" <<'PY'
import json, sys
from pathlib import Path
config = Path(sys.argv[1])
value = json.loads(config.read_text(encoding="utf-8"))
value["coordinator_source_roots"] = [sys.argv[2]]
config.write_text(json.dumps(value), encoding="utf-8")
PY

call_gate() {
  local path="$1" expected="$2" agent_id="${3:-}" event decision
  event="$(python3 -c 'import json,sys; print(json.dumps({"tool_name":"Edit","tool_input":{"file_path":sys.argv[1]},"cwd":sys.argv[2], **({"agent_id":sys.argv[3]} if len(sys.argv)>3 and sys.argv[3] else {})}))' \
    "$path" "$TMP_ROOT/workspace" "$agent_id")"
  decision="$(printf '%s' "$event" | AI_TOOLKIT_CONFIG="$TMP_ROOT/config.json" \
    bash "$REPO_ROOT/hooks/coordinator-source-gate.sh" | \
    python3 -c 'import json,sys; print(json.load(sys.stdin)["hookSpecificOutput"]["permissionDecision"])')"
  [ "$decision" = "$expected" ] || {
    printf 'working-copy example failed: expected %s, got %s\n' "$expected" "$decision" >&2
    return 1
  }
}

call_gate "$SOURCE_ROOT/module.py" deny
call_gate "$TMP_ROOT/workspace/docs/overview.md" allow
call_gate "$SOURCE_ROOT/module.py" allow synthetic-executor
printf '%s\n' 'working-copy example: configured source writes denied for coordinator and allowed for executor.'
