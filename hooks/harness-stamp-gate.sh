#!/usr/bin/env bash
# Gate tool calls until installed settings match this checkout's shared template
# and optional ignored machine-local overlay.
set -u
payload="$(cat 2>/dev/null || true)"
exec python3 - "${BASH_SOURCE[0]}" "$payload" <<'PY'
import json
import hashlib
import os
import re
import subprocess
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
command = [sys.executable, str(renderer), "--template", str(template),
           "--home", str(home), "--digest"]
try:
    sys.path.insert(0, str(repo))
    from lib.private_config import load, resolved_path
    config = load(repo)
    overlay_value = config.get("settings_overlay", ".private/settings.json")
    overlay = resolved_path(repo, overlay_value)
    if overlay.exists():
        command.extend(("--overlay", str(overlay)))
    result = subprocess.run(command, capture_output=True, text=True, timeout=5)
except Exception as exc:
    expected = None
    error = str(exc)
else:
    expected = result.stdout.strip() if result.returncode == 0 else None
    error = result.stderr.strip() or "settings renderer failed"

settings_error = None
installed_digest = None
try:
    if settings.is_symlink():
        settings_error = "installed settings path is a symlink"
    elif not settings.is_file():
        settings_error = "installed settings file is missing or not a regular file"
    else:
        settings_bytes = settings.read_bytes()
        parsed_settings = json.loads(settings_bytes)
        if not isinstance(parsed_settings, dict):
            settings_error = "installed settings root is not a JSON object"
        else:
            installed_digest = hashlib.sha256(settings_bytes).hexdigest()
except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    settings_error = "installed settings are unreadable or malformed: " + str(exc)

try:
    if stamp.is_symlink():
        stamp_value = None
        stamp_error = "settings stamp path is a symlink"
    elif not stamp.is_file():
        stamp_value = None
        stamp_error = "no settings stamp is installed"
    else:
        stamp_value = stamp.read_text(encoding="utf-8").strip()
        stamp_error = None if re.fullmatch(r"[0-9a-f]{64}", stamp_value) else "settings stamp is malformed"
except (OSError, UnicodeError):
    stamp_value = None
    stamp_error = "settings stamp is unreadable"

if (expected is not None and settings_error is None and stamp_error is None and
        installed_digest == expected and stamp_value == expected):
    finish(ALLOW)

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

if expected is None:
    problem = "settings renderer failed: " + error
elif settings_error is not None:
    problem = settings_error
elif stamp_error is not None:
    problem = stamp_error
elif installed_digest != expected:
    problem = "installed settings bytes do not match the shared template and private overlay"
else:
    problem = "installed settings stamp does not match the installed settings bytes"
reason = (
    "CLAUDE_HARNESS_BYPASS=1 disables this gate. Run bash " + str(repo / "bootstrap.sh") +
    " to deploy settings before retrying. Blocked by harness-stamp-gate: " + problem +
    ". Read-only diagnostics and the deployment command remain allowed."
)
print(deny(reason))
PY
