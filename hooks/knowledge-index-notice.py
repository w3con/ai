#!/usr/bin/env python3
"""Add an explicitly configured knowledge-base index to relevant tool calls."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ALLOW = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                "permissionDecision": "allow"}}
SEARCH_BINARIES = re.compile(r"(?:^|[|;&(`]|\s)(?:grep|egrep|fgrep|rg|ag|ack|find|fd)\b")
PREAMBLE = ("This is the configured knowledge-base index. Use the referenced local source "
            "documents before searching for another answer. Only the configured roots and "
            "commands are used by this notice.")


def plain_allow() -> None:
    print(json.dumps(ALLOW, ensure_ascii=False))
    raise SystemExit(0)


def workspace_root(start: Path, markers: list[str]) -> Path | None:
    for candidate in (start, *start.parents):
        if markers and all((candidate / marker).is_dir() for marker in markers):
            return candidate
    return None


def run_configured(argv: list[str], root: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    command = [part.replace("{root}", str(root)) for part in argv]
    for index in range(min(2, len(command))):
        item = Path(command[index]).expanduser()
        if not item.is_absolute() and "/" in command[index]:
            command[index] = str((root / item).resolve())
    return subprocess.run(command, cwd=root, capture_output=True, text=True,
                          timeout=timeout, check=False)


def build_index(root: Path, config: dict) -> str:
    command = config.get("index_command")
    if not isinstance(command, list) or not command:
        return ""
    try:
        result = run_configured(command, root)
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def dangling_paths_line(root: Path, config: dict) -> str:
    command = config.get("path_check_command")
    if not isinstance(command, list) or not command:
        return ""
    try:
        result = run_configured(command, root)
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    return (f"The configured knowledge base contains {count} unresolved links; "
            "review them with the configured path-check command.") if count > 0 else ""


def state_dir(config: dict) -> Path:
    override = os.environ.get("KNOWLEDGE_INDEX_NOTICE_STATE_DIR")
    configured = config.get("state_directory")
    base = Path(override or configured or
                (Path.home() / ".cache" / "ai-toolkit" / "knowledge-index"))
    base = base.expanduser()
    base.mkdir(parents=True, exist_ok=True)
    return base


def already_shown(key: str, config: dict) -> bool:
    if not key:
        return False
    try:
        marker = state_dir(config) / hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        if marker.exists():
            return True
        marker.write_text("", encoding="utf-8")
        return False
    except OSError:
        return False


def under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def searches_knowledge(tool_input: dict, cwd: Path, root: Path, config: dict) -> bool:
    pattern = tool_input.get("pattern") or ""
    if isinstance(pattern, str) and (any(ord(char) > 127 for char in pattern) or
                                     any(char.isspace() for char in pattern.strip())):
        return True
    raw = tool_input.get("path") or ""
    if not raw:
        return True
    target = Path(raw).expanduser()
    if not target.is_absolute():
        target = cwd / target
    if any(under(target, root / item) for item in config.get("code_roots", [])):
        return False
    if any(under(target, root / item) for item in config.get("knowledge_roots", [])):
        return True
    return under(target, root)


def wants_index(tool: str, tool_input: dict, cwd: Path, root: Path, config: dict) -> bool:
    if tool in ("Grep", "Glob"):
        return searches_knowledge(tool_input, cwd, root, config)
    if tool in ("Write", "Edit", "NotebookEdit"):
        path = (tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        pattern = config.get("card_path_pattern")
        return bool(isinstance(pattern, str) and re.search(pattern, path.replace(os.sep, "/")))
    if tool == "Bash":
        command = tool_input.get("command") or ""
        if any(name in command for name in config.get("work_commands", [])):
            return True
        if not SEARCH_BINARIES.search(command):
            return False
        if any(ord(char) > 127 for char in command):
            return True
        if any(marker in command for marker in config.get("knowledge_roots", [])):
            return True
        if any(marker in command for marker in config.get("code_roots", [])):
            return False
        return True
    return False


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0
    if os.environ.get("KNOWLEDGE_INDEX_NOTICE_OFF") == "1":
        return 0
    if os.environ.get("CLAUDE_GATE_BYPASS") == "1" or event.get("agent_id"):
        return 0
    try:
        cwd_value = os.environ.get("KNOWLEDGE_INDEX_NOTICE_CWD") or event.get("cwd") or os.getcwd()
        cwd = Path(cwd_value).expanduser().resolve()
        toolkit_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(toolkit_root))
        from lib.private_config import load
        private = load(toolkit_root)
        config = (private.get("knowledge_base") or {}).get("notice") or {}
        if not isinstance(config, dict):
            return 0
        markers = config.get("workspace_markers", [])
        if not isinstance(markers, list):
            return 0
        root = workspace_root(cwd, markers)
        if root is None:
            return 0
        event_name = event.get("hook_event_name") or ""
        if event_name == "SessionStart":
            text = build_index(root, config)
            if text:
                print(PREAMBLE)
                print()
                print(text)
            warning = dangling_paths_line(root, config)
            if warning:
                print("\n" + warning)
            return 0
        tool = event.get("tool_name") or ""
        tool_input = event.get("tool_input") or {}
        if not isinstance(tool_input, dict) or not wants_index(tool, tool_input, cwd, root, config):
            plain_allow()
        key = event.get("prompt_id") or event.get("session_id") or ""
        if already_shown(str(key), config):
            plain_allow()
        text = build_index(root, config)
        if not text:
            plain_allow()
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "allow",
            "additionalContext": PREAMBLE + "\n\n" + text,
        }}, ensure_ascii=False))
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
