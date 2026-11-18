#!/usr/bin/env bash
# Prevent coordinator-side file edits inside source roots explicitly configured
# by the optional private layer. Executor calls remain allowed.
set -u
payload="$(cat 2>/dev/null || true)"
hook_path="${BASH_SOURCE[0]}"
exec python3 - "$hook_path" "$payload" <<'PY'
import json
import os
import sys
from pathlib import Path

hook_path, payload = sys.argv[1], sys.argv[2]
ALLOW = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def result(decision: str, reason: str = "") -> str:
    body = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "permissionDecision": decision}}
    if reason:
        body["hookSpecificOutput"]["permissionDecisionReason"] = reason
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))

def finish(output: str) -> None:
    print(output)
    raise SystemExit(0)

if os.environ.get("CLAUDE_GATE_BYPASS") == "1":
    finish(ALLOW)
try:
    event = json.loads(payload) if payload.strip() else {}
except Exception:
    finish(ALLOW)
if not isinstance(event, dict):
    finish(ALLOW)

agent_id = event.get("agent_id")
tool = event.get("tool_name") or ""
tool_input = event.get("tool_input") or {}
if not isinstance(tool_input, dict):
    finish(ALLOW)
hook = Path(hook_path).resolve()
root = hook.parent.parent
sys.path.insert(0, str(root))
try:
    from lib.private_config import ConfigError, load, resolved_path
    config = load(root)
    marker_name = config.get("executor_marker_environment", "TOOLKIT_EXECUTOR")
    source_roots = [resolved_path(root, value).resolve()
                    for value in config.get("coordinator_source_roots", [])]
except Exception:
    # This guard is advisory on malformed/unavailable local configuration.
    finish(ALLOW)

if agent_id or os.environ.get(marker_name):
    finish(ALLOW)
if tool not in {"Edit", "Write", "NotebookEdit"}:
    finish(ALLOW)
path_value = (tool_input.get("notebook_path") if tool == "NotebookEdit" else
              tool_input.get("file_path")) or tool_input.get("path")
if not isinstance(path_value, str) or not path_value:
    finish(ALLOW)
try:
    target = Path(path_value).expanduser()
    if not target.is_absolute():
        target = Path(event.get("cwd") or os.getcwd()) / target
    target = target.resolve()
except (OSError, RuntimeError):
    finish(ALLOW)

for source_root in source_roots:
    try:
        target.relative_to(source_root)
    except ValueError:
        continue
    finish(result(
        "deny",
        f"Blocked by coordinator-source-gate: this edit targets configured product source "
        f"{target}. Record the change in a task and hand it to an executor instead."
    ))
finish(ALLOW)
PY
