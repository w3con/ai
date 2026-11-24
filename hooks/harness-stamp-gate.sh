#!/usr/bin/env bash
# Gate tool calls until source-owned settings and hook entries match this checkout.
# Independent additional hooks remain outside this gate's integrity assurance.
set -u
payload="$(cat 2>/dev/null || true)"
exec python3 - "${BASH_SOURCE[0]}" "$payload" <<'PY'
import json
import os
import runpy
import sys
from pathlib import Path

hook_path, payload = sys.argv[1], sys.argv[2]
ALLOW = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny(reason):
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}, ensure_ascii=False, separators=(",", ":"))

def finish(result):
    print(result)
    raise SystemExit(0)

if os.environ.get("CLAUDE_HARNESS_BYPASS") == "1":
    finish(ALLOW)

repo = Path(os.environ.get("HARNESS_STAMP_GATE_REPO_DIR") or
            Path(hook_path).resolve().parent.parent)
template = repo / "settings.json.template"
if not template.is_file():
    finish(ALLOW)

home = Path.home().resolve()
settings = home / ".claude" / "settings.json"
stamp = Path(os.environ.get("HARNESS_STAMP_GATE_STAMP_FILE") or
             home / ".claude" / ".harness-stamp")
renderer = repo / "bin" / "settings-render"
problem = None
try:
    sys.path.insert(0, str(repo))
    from lib.private_config import load, resolved_path
    from lib import settings_policy as policy
    config = load(repo)
    overlay_value = config.get("settings_overlay", ".private/settings.json")
    if not isinstance(overlay_value, str) or not overlay_value.strip():
        raise ValueError("settings_overlay must be a non-empty path")
    overlay = resolved_path(repo, overlay_value)
    if overlay.is_symlink() and not overlay.exists():
        raise ValueError("settings overlay is a broken symlink")
    rendered = runpy.run_path(str(renderer))["render"](template, overlay, str(home))
    expected = policy.loads_object(rendered)
    policy.validate_preferences(expected)
    policy.hook_atoms(expected)
except Exception as exc:
    problem = "settings renderer failed: " + str(exc)
if problem is None:
    try:
        installed = policy.read_settings(settings)
        stamp_value = policy.read_stamp(stamp)
        if policy.current_stamp(stamp_value, installed, expected, rendered):
            finish(ALLOW)
        changes = policy.integrity_differences(expected, installed)
        problem = ("controlled settings differ: " + changes if changes else
                   "settings stamp is stale; controlled keys: " + policy.key_names(policy.controlled(expected)))
    except Exception as exc:
        problem = "installed settings or stamp are unreadable or malformed: " + str(exc)

try:
    event = json.loads(payload) if payload.strip() else {}
except json.JSONDecodeError:
    event = {}
tool = event.get("tool_name", "")
tool_input = event.get("tool_input", {}) or {}
if tool in {"Read", "Glob", "Grep", "NotebookRead", "TodoWrite"}:
    finish(ALLOW)
if tool == "Bash" and "bootstrap.sh" in (tool_input.get("command") or ""):
    finish(ALLOW)

import shlex
repair = "bash " + shlex.quote(str(repo / "bootstrap.sh"))
reason = (
    "Blocked by harness-stamp-gate: " + problem + ". Diagnose with " + repair +
    " --dry-run. The owner must review the private source and repair owned entries using a trusted "
    "baseline. Back up settings/stamp/baseline and use bin/settings-render for source-only "
    "comparison (see docs/settings.md), preserving independent hooks, "
    "then run " + repair + ". Read-only diagnostics and deployment remain allowed."
)
print(deny(reason))
PY
