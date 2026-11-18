#!/usr/bin/env python3
"""Scratch-only contract tests for hooks/skill-mcp-refs.py."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

_AI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_AI_ROOT, "hooks", "skill-mcp-refs.py")


def run(root, skills, config, known="", project="/this/project"):
    """Write one scratch tree, run the hook against it, return its stdout."""
    skills_dir = os.path.join(root, "skills")
    for name, text in skills.items():
        path = os.path.join(skills_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    config_path = os.path.join(root, "claude.json")
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config, fh)

    env = dict(os.environ)
    env["SKILL_MCP_REFS_ROOTS"] = skills_dir
    env["SKILL_MCP_REFS_CONFIGS"] = config_path
    env["SKILL_MCP_REFS_KNOWN"] = known
    env["SKILL_MCP_REFS_PROJECT"] = project
    r = subprocess.run(
        [sys.executable, HOOK], input="{}", capture_output=True, text=True, env=env
    )
    if r.returncode != 0:
        return "NONZERO_EXIT(%s): %s" % (r.returncode, r.stderr[:200])
    return r.stdout


CASES = []


def case(label, fn):
    CASES.append((label, fn))


def _dead_server_is_reported(root):
    out = run(
        root,
        {"web-search/SKILL.md": "Call `mcp__brave-search__brave_web_search` with the query."},
        {"mcpServers": {"n8n": {}}},
    )
    return "brave_search" in out and "web-search/SKILL.md" in out


def _configured_server_is_silent(root):
    out = run(
        root,
        {"a/SKILL.md": "Call `mcp__n8n__run_workflow`."},
        {"mcpServers": {"n8n": {}}},
    )
    return out.strip() == ""


def _hyphen_and_underscore_are_the_same_server(root):
    out = run(
        root,
        {"a/SKILL.md": "Call `mcp__brave_search__go`."},
        {"mcpServers": {"brave-search": {}}},
    )
    return out.strip() == ""


def _this_projects_own_config_counts(root):
    out = run(
        root,
        {"a/SKILL.md": "Call `mcp__sentry__list_issues`."},
        {"projects": {"/this/project": {"mcpServers": {"sentry": {}}}}},
    )
    return out.strip() == ""


def _another_projects_config_does_not_count(root):
    """A server configured for a different project is not active here."""
    out = run(
        root,
        {"web-search/SKILL.md": "Call `mcp__brave-search__brave_web_search`."},
        {"projects": {"/this/project/renamed-away": {"mcpServers": {"brave-search": {}}}}},
    )
    return "brave_search" in out


def _account_connectors_are_never_reported(root):
    out = run(
        root,
        {"a/SKILL.md": "Call `mcp__claude_ai_Gmail__send_message` and "
                       "`mcp__claude_in_chrome__navigate`."},
        {"mcpServers": {}},
    )
    return out.strip() == ""


def _skill_turned_off_is_never_reported(root):
    out = run(
        root,
        {"synced/bucket/import-memory/SKILL.md": "Call `mcp__memory__memory_write`.",
         "own/SKILL.md": "Call `mcp__ghost__go`."},
        {"mcpServers": {}, "skillOverrides": {"anthropic-skills:import-memory": "off"}},
    )
    return "memory" not in out and "ghost" in out


def _known_override_silences(root):
    out = run(
        root,
        {"a/SKILL.md": "Call `mcp__brave-search__go`."},
        {"mcpServers": {}},
        known="brave-search",
    )
    return out.strip() == ""


def _unreadable_config_does_not_crash(root):
    skills_dir = os.path.join(root, "skills")
    os.makedirs(skills_dir, exist_ok=True)
    with open(os.path.join(skills_dir, "a.md"), "w", encoding="utf-8") as fh:
        fh.write("Call `mcp__ghost__go`.")
    env = dict(os.environ)
    env["SKILL_MCP_REFS_ROOTS"] = skills_dir
    env["SKILL_MCP_REFS_CONFIGS"] = os.path.join(root, "does-not-exist.json")
    env["SKILL_MCP_REFS_KNOWN"] = ""
    r = subprocess.run(
        [sys.executable, HOOK], input="{}", capture_output=True, text=True, env=env
    )
    return r.returncode == 0 and "ghost" in r.stdout


def _missing_root_is_silent(root):
    env = dict(os.environ)
    env["SKILL_MCP_REFS_ROOTS"] = os.path.join(root, "nothing-here")
    env["SKILL_MCP_REFS_CONFIGS"] = os.path.join(root, "nothing.json")
    env["SKILL_MCP_REFS_KNOWN"] = ""
    r = subprocess.run(
        [sys.executable, HOOK], input="{}", capture_output=True, text=True, env=env
    )
    return r.returncode == 0 and r.stdout.strip() == ""


case("an unavailable server is reported", _dead_server_is_reported)
case("a configured server is not reported", _configured_server_is_silent)
case("hyphens and underscores normalize equally", _hyphen_and_underscore_are_the_same_server)
case("the current project's server configuration is counted", _this_projects_own_config_counts)
case("another project's server configuration is not counted", _another_projects_config_does_not_count)
case("account-provided connectors are exempt", _account_connectors_are_never_reported)
case("disabled skills are ignored", _skill_turned_off_is_never_reported)
case("explicitly known servers are ignored", _known_override_silences)
case("unreadable configuration does not crash", _unreadable_config_does_not_crash)
case("missing roots are silent", _missing_root_is_silent)


def main():
    failures = 0
    for label, fn in CASES:
        root = tempfile.mkdtemp(prefix="skill-mcp-refs-test-")
        try:
            ok = fn(root)
        except Exception as exc:  # a crash is a failure, not an error in the harness
            ok = False
            label = "%s [raised %s]" % (label, exc)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        print("%s %s" % ("ok  " if ok else "FAIL", label))
        if not ok:
            failures += 1
    print("%d case(s), %d failure(s)" % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
