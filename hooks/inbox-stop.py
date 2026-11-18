#!/usr/bin/env python3
"""Deliver configured session-inbox messages without project-specific defaults.

An optional ``inbox`` object in the ignored private configuration declares a root
and argv list. Missing configuration, malformed hook input or command failures are
fail-open so an unavailable inbox cannot prevent a session from ending.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def format_line(raw: str) -> str:
    try:
        entry = json.loads(raw)
    except ValueError:
        return raw
    text = (entry.get("text") or "").strip()
    card = (entry.get("card") or "").strip()
    if not text:
        return ""
    return f"[{card}] {text}" if card else text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        cwd_value = payload.get("cwd") or ""
        if not cwd_value:
            return 0
        cwd = Path(cwd_value).expanduser().resolve(strict=True)
    except Exception:
        return 0

    source = Path(__file__).resolve()
    toolkit_root = source.parents[1]
    sys.path.insert(0, str(toolkit_root))
    try:
        from lib.private_config import ConfigError, load, resolved_path
        config = load(toolkit_root)
    except (ConfigError, OSError, ValueError):
        return 0
    inbox = config.get("inbox")
    if not isinstance(inbox, dict):
        return 0
    try:
        root = resolved_path(toolkit_root, inbox["root"]).resolve(strict=True)
        if os.path.commonpath((str(root), str(cwd))) != str(root):
            return 0
        argv = [part.replace("{root}", str(root)) for part in inbox["command"]]
        if not argv:
            return 0
        path_indexes = [0]
        if Path(argv[0]).name in {"python", "python3"} and len(argv) > 1:
            path_indexes.append(1)
        for index in path_indexes:
            if not os.path.isabs(argv[index]) and "/" in argv[index]:
                argv[index] = str(resolved_path(root, argv[index]))
        result = subprocess.run(argv, cwd=root, capture_output=True,
                                text=True, timeout=10, check=False)
    except (KeyError, OSError, subprocess.SubprocessError, ValueError):
        return 0
    if result.returncode != 0:
        return 0

    messages = [message for message in map(format_line, result.stdout.splitlines()) if message]
    if messages:
        reason = ("A message was submitted through the configured session inbox. "
                  "Respond to it before ending this turn.\n\n" + "\n\n".join(messages))
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
