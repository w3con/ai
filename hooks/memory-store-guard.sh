#!/usr/bin/env bash
# Prevent writes from silently creating a project-local memory store when the
# configured shared private memory root is in use.
set -u
hook_path="${BASH_SOURCE[0]}"
payload="$(cat 2>/dev/null || true)"
exec python3 - "$hook_path" "$payload" <<'PY'
import json
import os
import sys
from pathlib import Path

hook_path, payload = sys.argv[1], sys.argv[2]
ALLOW = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny(reason):
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}, ensure_ascii=False, separators=(",", ":"))

try:
    if not payload.strip():
        raise ValueError("empty payload")
    event = json.loads(payload)
except Exception:
    print(deny("Blocked by memory-store-guard: invalid hook input; writes are held until it can be checked."))
    raise SystemExit(0)

if os.environ.get("CLAUDE_GATE_BYPASS") == "1":
    print(ALLOW)
    raise SystemExit(0)
if event.get("tool_name") not in ("Write", "Edit"):
    print(ALLOW)
    raise SystemExit(0)

file_path = (event.get("tool_input") or {}).get("file_path") or ""
if not file_path:
    print(ALLOW)
    raise SystemExit(0)

try:
    hook = Path(hook_path).resolve()
    root = hook.parent.parent
    sys.path.insert(0, str(root))
    from lib.private_config import ConfigError, load, resolved_path
    config = load(root)
    home = Path.home().resolve()
    memory_setting = config.get("memory_root")
    memory_root = (resolved_path(root, memory_setting).resolve() if memory_setting else
                   (home / ".local" / "share" / "ai-toolkit" / "memory").resolve())
    projects_root = (home / ".claude" / "projects").resolve()
    destination = Path(os.path.expanduser(file_path)).resolve()
except Exception:
    print(deny("Blocked by memory-store-guard: private memory configuration could not be loaded."))
    raise SystemExit(0)

def is_under(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False

if is_under(destination.parent, memory_root):
    print(ALLOW)
    raise SystemExit(0)

if is_under(destination.parent, projects_root):
    relative = destination.parent.relative_to(projects_root)
    if len(relative.parts) >= 2 and relative.parts[1] == "memory":
        bootstrap = root / "bootstrap.sh"
        print(deny(
            "Blocked by memory-store-guard: this project memory path is not linked to the "
            f"configured private store at {memory_root}. Run bash {bootstrap} to install "
            "the configured private memory link, then retry."
        ))
        raise SystemExit(0)

print(ALLOW)
PY
