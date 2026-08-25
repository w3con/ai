#!/usr/bin/env python3
"""skill-mcp-refs.py — SessionStart hook: name every skill, agent or slash command whose
text tells the reader to call a tool from an MCP server that this project does not have
configured.

A skill file that instructs "call mcp__brave-search__brave_web_search" when no brave-search
server exists does not announce itself. The instruction simply fails at the moment it is
followed, the fallback branch written into the same file catches it, an answer comes back
by a worse route, and nobody is told. That is how the Validité copy of the web-search skill
stayed broken from May to August 2026. This hook is the telling: at the start of a session
it reads the instruction files that are actually in force, extracts every MCP tool
identifier they name, and reports the ones whose server is not configured.

What it prints: one line per (file, missing server) pair. A machine whose skills all point
at configured servers prints nothing at all.
What it never does: fail the session, or touch the network. Every input is a file already
on disk.

An MCP tool identifier has the shape mcp__<server>__<tool>, where <server> is the server's
configured name with every character that is not a letter or a digit replaced by an
underscore. Both sides of the comparison are normalised that same way, so a server
configured as "brave-search" matches a reference to mcp__brave_search__foo.

Servers that come from the account rather than from a configuration file on this machine —
the claude.ai connectors, and the browser extension — are never reported, because no file
here lists them and their absence from one would prove nothing.

  SKILL_MCP_REFS_ROOTS    colon-separated directories to scan for instruction files;
                          default: the global ~/.claude tree plus the current project's
                          own .claude tree. Overridable so the test suite never reads the
                          real ones.
  SKILL_MCP_REFS_CONFIGS  colon-separated JSON files to read configured server names from;
                          default: ~/.claude.json, the project's .mcp.json, and the
                          project's two settings files. Overridable for the same reason.
  SKILL_MCP_REFS_KNOWN    space-separated extra server names to treat as configured.
  SKILL_MCP_REFS_PROJECT  the project key to read out of a configuration file's
                          "projects" map; default: the current working directory.
"""
import json
import os
import re
import sys

TOOL_REF = re.compile(r"mcp__([A-Za-z0-9_-]+)__[A-Za-z0-9_-]+")

# Servers that exist without any local configuration file naming them: the connectors
# attached to the account, and the browser extension Claude Code ships with.
EXEMPT_PREFIXES = ("claude_ai_", "claude_in_chrome")


def normalise(name):
    return re.sub(r"[^A-Za-z0-9]", "_", name)


def configured_servers(config_paths, project):
    """Every server name reachable from THIS project, normalised.

    A server listed under some other project's key in ~/.claude.json is deliberately not
    counted. That is not a nicety: the servers behind the original defect were still
    written down, under the project's own former path — the directory had been renamed
    from "Validité" to "Validite" — so they had simply stopped being loaded while looking,
    to any recursive reader, exactly like servers that were configured and fine.
    """
    found = set()

    def take(node):
        if isinstance(node, dict):
            servers = node.get("mcpServers")
            if isinstance(servers, dict):
                found.update(normalise(k) for k in servers)

    for path in config_paths:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        take(data)
        projects = data.get("projects")
        if isinstance(projects, dict):
            take(projects.get(project))
    return found


def instruction_files(roots):
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
            for name in filenames:
                if name.endswith(".md"):
                    yield os.path.join(dirpath, name)


def findings(roots, config_paths, extra_known, project):
    known = configured_servers(config_paths, project) | {normalise(n) for n in extra_known}
    seen = []
    for path in sorted(instruction_files(roots)):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except Exception:
            continue
        for server in sorted(set(TOOL_REF.findall(text))):
            server = normalise(server)
            if server in known or server.startswith(EXEMPT_PREFIXES):
                continue
            seen.append((path, server))
    return seen


def main():
    # The SessionStart payload carries nothing this hook needs; read and discard it so
    # Claude Code never sees a broken pipe.
    try:
        sys.stdin.read()
    except Exception:
        pass

    home = os.path.expanduser("~")
    project = os.environ.get("SKILL_MCP_REFS_PROJECT") or os.getcwd()

    roots_env = os.environ.get("SKILL_MCP_REFS_ROOTS")
    if roots_env:
        roots = [p for p in roots_env.split(":") if p]
    else:
        roots = [
            os.path.join(home, ".claude", "skills"),
            os.path.join(home, ".claude", "agents"),
            os.path.join(home, ".claude", "commands"),
            os.path.join(project, ".claude", "skills"),
            os.path.join(project, ".claude", "agents"),
            os.path.join(project, ".claude", "commands"),
        ]
    roots = [p for p in roots if os.path.isdir(p)]

    configs_env = os.environ.get("SKILL_MCP_REFS_CONFIGS")
    if configs_env:
        configs = [p for p in configs_env.split(":") if p]
    else:
        configs = [
            os.path.join(home, ".claude.json"),
            os.path.join(home, ".claude", "settings.json"),
            os.path.join(project, ".mcp.json"),
            os.path.join(project, ".claude", "settings.json"),
            os.path.join(project, ".claude", "settings.local.json"),
        ]

    extra = os.environ.get("SKILL_MCP_REFS_KNOWN", "").split()

    for path, server in findings(roots, configs, extra, project):
        print(
            'skill-mcp-refs: %s tells you to call the MCP server "%s", which is not '
            "configured for this project — following that instruction fails every time."
            % (path, server)
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
