#!/usr/bin/env python3
"""Shared helpers for finding Markdown briefs in prompts and session transcripts."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_ROOT_STR = str(_ROOT)
try:
    import sys
    sys.path.insert(0, _ROOT_STR)
    from lib.private_config import load
    _CONFIG = load(_ROOT)
except Exception:
    _CONFIG = {}
_CARD_PREFIXES = _CONFIG.get("brief_card_prefixes", ["tasks/"])
BRIEF_DIRS = tuple(_CONFIG.get("brief_directories", ["tasks", "plans"]))
MD_PATH_RE = re.compile(r"[~\w./\\-]*[\w-]\.md\b")


def candidate_texts(tool_input, keys=("prompt", "description")):
    """Yield non-empty prompt/description fields that may contain a brief path."""
    if not isinstance(tool_input, dict):
        return
    for key in keys:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            yield value


def brief_tokens(tool_input, keys=("prompt", "description")):
    """Return distinct Markdown path tokens in their first-seen order."""
    seen, result = set(), []
    for text in candidate_texts(tool_input, keys):
        for token in MD_PATH_RE.findall(text):
            if token not in seen:
                seen.add(token)
                result.append(token)
    return result


def resolve(token, roots):
    """Resolve absolute paths directly and relative paths against declared roots."""
    path = os.path.expanduser(token)
    if os.path.isabs(path):
        return [os.path.normpath(path)]
    result = []
    for root in roots:
        if not root:
            continue
        result.append(os.path.normpath(os.path.join(root, path)))
        stripped = path[2:] if path.startswith("./") else path
        if "/" not in stripped:
            result.extend(os.path.normpath(os.path.join(root, directory, stripped))
                          for directory in BRIEF_DIRS)
    return result


def canonical_card(token):
    """Return a configured task-card suffix without any checkout/worktree prefix."""
    normalized = (token or "").replace(os.sep, "/")
    matches = []
    for prefix in _CARD_PREFIXES:
        prefix = str(prefix).strip("/") + "/"
        index = normalized.find(prefix)
        if index >= 0:
            matches.append(normalized[index:])
    return min(matches, key=len) if matches else token


def find_spawn_prompt(transcript_path, agent_id):
    """Find the stored prompt/description for one spawned agent; never raises."""
    if not transcript_path or not agent_id:
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                if '"agentId"' not in line or agent_id not in line:
                    continue
                try:
                    record = json.loads(line)
                except (TypeError, ValueError):
                    continue
                result = record.get("toolUseResult") if isinstance(record, dict) else None
                if isinstance(result, dict) and result.get("agentId") == agent_id:
                    return {"prompt": result.get("prompt") or "",
                            "description": result.get("description") or ""}
    except OSError:
        return None
    return None
