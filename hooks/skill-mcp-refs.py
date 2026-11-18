#!/usr/bin/env python3
"""Report active instruction files that reference unconfigured MCP servers."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


TOOL_REF = re.compile(r"mcp__([A-Za-z0-9_-]+)__[A-Za-z0-9_-]+")
EXEMPT_PREFIXES = ("claude_ai_", "claude_in_chrome")


def normalise(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", name)


def configured_servers(config_paths: list[str], project: str) -> set[str]:
    found: set[str] = set()
    for path in config_paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        project_map = data.get("projects")
        project_node = project_map.get(project, {}) if isinstance(project_map, dict) else {}
        for node in (data, project_node):
            if not isinstance(node, dict):
                continue
            servers = node.get("mcpServers")
            if isinstance(servers, dict):
                found.update(normalise(name) for name in servers)
    return found


def disabled_skills(config_paths: list[str]) -> set[str]:
    disabled: set[str] = set()
    for path in config_paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        overrides = data.get("skillOverrides") if isinstance(data, dict) else None
        if isinstance(overrides, dict):
            disabled.update(name.rsplit(":", 1)[-1]
                            for name, value in overrides.items() if value == "off")
    return disabled


def instruction_files(roots: list[str]):
    for root in roots:
        for directory, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs
                       if name not in (".git", "node_modules", "__pycache__", ".private")]
            for name in files:
                if name.endswith(".md"):
                    yield os.path.join(directory, name)


def findings(roots: list[str], config_paths: list[str], extra_known: list[str], project: str):
    known = configured_servers(config_paths, project) | {normalise(name) for name in extra_known}
    disabled = disabled_skills(config_paths)
    result = []
    for path in sorted(instruction_files(roots)):
        if Path(path).parent.name in disabled:
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for server in sorted(set(TOOL_REF.findall(text))):
            server = normalise(server)
            if server not in known and not server.startswith(EXEMPT_PREFIXES):
                result.append((path, server))
    return result


def main() -> int:
    try:
        sys.stdin.read()
    except Exception:
        pass
    home = Path.home()
    project = os.environ.get("SKILL_MCP_REFS_PROJECT") or os.getcwd()
    toolkit_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(toolkit_root))
    try:
        from lib.private_config import load
        config = load(toolkit_root)
    except Exception:
        config = {}
    external = [str(Path(path).expanduser()) for path in config.get("external_roots", [])]

    roots_value = os.environ.get("SKILL_MCP_REFS_ROOTS")
    roots = ([path for path in roots_value.split(":") if path] if roots_value else [
        str(home / ".claude" / child)
        for child in ("skills", "agents", "commands")
    ] + [os.path.join(project, ".claude", child)
         for child in ("skills", "agents", "commands")])
    if not roots_value:
        roots.extend(os.path.join(path, ".claude", child) for path in external
                     for child in ("skills", "agents", "commands"))
    roots = [path for path in roots if os.path.isdir(path)]

    configs_value = os.environ.get("SKILL_MCP_REFS_CONFIGS")
    configs = ([path for path in configs_value.split(":") if path] if configs_value else [
        str(home / ".claude.json"), str(home / ".claude" / "settings.json"),
        os.path.join(project, ".mcp.json"), os.path.join(project, ".claude", "settings.json"),
        os.path.join(project, ".claude", "settings.local.json"),
    ])
    if not configs_value:
        configs.extend(os.path.join(path, suffix) for path in external
                       for suffix in (".mcp.json", ".claude/settings.json",
                                      ".claude/settings.local.json"))

    known = os.environ.get("SKILL_MCP_REFS_KNOWN", "").split()
    for path, server in findings(roots, configs, known, project):
        print(f'skill-mcp-refs: {path} references MCP server "{server}", which is not configured.')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
