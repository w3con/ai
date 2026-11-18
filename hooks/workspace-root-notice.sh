#!/usr/bin/env bash
# SessionStart notice for optional workspace rules whose imports depend on the
# session opening at a configured workspace root. No workspace is assumed.
set -u
payload="$(cat 2>/dev/null || true)"
hook_path="${BASH_SOURCE[0]}"
exec python3 - "$hook_path" "$payload" <<'PY'
import json
import os
import sys
from pathlib import Path

hook_path, payload = sys.argv[1], sys.argv[2]
if os.environ.get("WORKSPACE_ROOT_NOTICE_OFF") == "1":
    raise SystemExit(0)

try:
    decoded_event = json.loads(payload) if payload.strip() else {}
    event = decoded_event if isinstance(decoded_event, dict) else {}
except json.JSONDecodeError:
    event = {}
repo = Path(hook_path).resolve().parent.parent
sys.path.insert(0, str(repo))
try:
    from lib.private_config import ConfigError, load, resolved_path
    config = load(repo)
except (ConfigError, OSError, ValueError):
    # Startup notices are advisory and must never prevent a session from opening.
    raise SystemExit(0)

workspaces = config.get("workspaces", [])
if not isinstance(workspaces, list):
    raise SystemExit(0)
for entry in workspaces:
    if isinstance(entry, dict):
        disable_environment = entry.get("disable_environment")
        if isinstance(disable_environment, str) and disable_environment and \
                os.environ.get(disable_environment):
            raise SystemExit(0)

def workspace_root(start: Path, markers: list[str]) -> Path | None:
    for candidate in (start, *start.parents):
        if markers and all((candidate / marker).is_dir() for marker in markers):
            return candidate
    return None

for entry in workspaces:
    if not isinstance(entry, dict):
        continue
    markers = entry.get("markers", [])
    pointer = entry.get("pointer")
    imports = entry.get("imports", [])
    rules_file = entry.get("rules_file")
    cwd_environment = entry.get("cwd_environment")
    disable_environment = entry.get("disable_environment")
    if (not isinstance(markers, list) or not all(isinstance(v, str) and v for v in markers)
            or not isinstance(pointer, str) or not pointer
            or not isinstance(imports, list) or not all(isinstance(v, str) for v in imports)
            or (cwd_environment is not None and (not isinstance(cwd_environment, str) or not cwd_environment))
            or (disable_environment is not None and
                (not isinstance(disable_environment, str) or not disable_environment))):
        continue
    cwd = (os.environ.get("WORKSPACE_ROOT_NOTICE_CWD") or
           (os.environ.get(cwd_environment) if cwd_environment else None) or
           event.get("cwd") or os.getcwd())
    try:
        cwd = Path(cwd).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise SystemExit(0)
    root = workspace_root(cwd, markers)
    if root is None:
        continue
    pointer_path = resolved_path(root, pointer)
    missing = []
    try:
        text = pointer_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        missing = imports
    else:
        missing = [line for line in imports if line not in text]
    if cwd != root:
        print(f"workspace-root-notice: This session is open in {cwd}, not the configured workspace root {root}; root-relative instructions may not have loaded.")
        print("Restart the session from the configured workspace root so its import entries are loaded.")
        if isinstance(rules_file, str) and rules_file:
            print(f"Read the configured rules file at {resolved_path(root, rules_file)} before continuing.")
    elif missing:
        print(f"workspace-root-notice: {pointer_path} is missing required import entries: {', '.join(missing)}.")
        print(f"Add the listed imports to {pointer_path}, then restart the session.")
    break
PY
