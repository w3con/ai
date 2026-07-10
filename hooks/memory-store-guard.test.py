#!/usr/bin/env python3
"""Test harness for hooks/memory-store-guard.sh.

Lives in a file for the same reason as settings-write-guard.test.py: this guard
inspects a file_path, and the point is to prove realpath resolution behaves
correctly for symlinks and `..` — easier to assert on directly in Python than
to reconstruct from shell.
"""
import json
import os
import subprocess
import sys

HOOK = "/Users/laptop/Dev/ai/hooks/memory-store-guard.sh"
HOME = os.path.expanduser("~")
SHARED_STORE = os.path.join(HOME, "Dev", "ai", "memory")
PROJECTS_ROOT = os.path.join(HOME, ".claude", "projects")

REAL_PROJECT_SLUG = "zz-guard-test"
REAL_PROJECT_DIR = os.path.join(PROJECTS_ROOT, REAL_PROJECT_SLUG, "memory")


def verdict(tool_name, file_path, env=None):
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"file_path": file_path}})
    r = subprocess.run(["bash", HOOK], input=payload, capture_output=True, text=True, env=env)
    try:
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]
    except Exception:
        return "PARSE_FAIL(" + r.stdout[:80] + ")"


fails = 0


def check(expected, label, tool_name, file_path, env=None):
    global fails
    got = verdict(tool_name, file_path, env=env)
    ok = got == expected
    fails += 0 if ok else 1
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  (ожидал {expected}, получил {got})"))


# --- setup: a REAL (non-symlink) project memory dir, to prove the deny path ---
os.makedirs(REAL_PROJECT_DIR, exist_ok=True)
assert not os.path.islink(REAL_PROJECT_DIR), "test setup bug: this must be a real dir, not a symlink"

try:
    check("allow", "запись в общий стор напрямую", "Write", os.path.join(SHARED_STORE, "x.md"))
    check("allow", "запись в MEMORY.md общего стора", "Write", os.path.join(SHARED_STORE, "MEMORY.md"))

    check("allow", "запись через симлинк проектной памяти (Dev-app)", "Write",
          os.path.join(PROJECTS_ROOT, "-Users-laptop-Dev-app", "memory", "x.md"))

    check("deny", "запись в настоящий (не-симлинк) проектный memory/", "Edit",
          os.path.join(REAL_PROJECT_DIR, "x.md"))

    check("allow", "запись в /tmp", "Write", "/tmp/x.md")

    check("allow", "запись в скиллы", "Write",
          os.path.join(HOME, "Dev", "ai", "skills", "web-search", "SKILL.md"))

    check("allow", "инструмент Bash не гейтится", "Bash", os.path.join(REAL_PROJECT_DIR, "x.md"))
    check("allow", "инструмент Read не гейтится", "Read", os.path.join(REAL_PROJECT_DIR, "x.md"))

    # CLAUDE_GATE_BYPASS=1 on what would otherwise be a deny
    bypass_env = dict(os.environ)
    bypass_env["CLAUDE_GATE_BYPASS"] = "1"
    check("allow", "CLAUDE_GATE_BYPASS=1 снимает deny", "Write",
          os.path.join(REAL_PROJECT_DIR, "x.md"), env=bypass_env)

    # ".." resolving into the real project dir — proves realpath, not string match
    dotdot_path = os.path.join(PROJECTS_ROOT, REAL_PROJECT_SLUG, "memory", "..", "memory", "x.md")
    check("deny", "путь с '..' ведущий в настоящий проектный каталог", "Write", dotdot_path)

    # nested file inside the real project memory dir
    check("deny", "вложенный файл внутри настоящего проектного memory/", "Write",
          os.path.join(REAL_PROJECT_DIR, "sub", "x.md"))

finally:
    # teardown: remove only what this test created
    for root, dirs, files in os.walk(REAL_PROJECT_DIR, topdown=False):
        for f in files:
            os.remove(os.path.join(root, f))
        for d in dirs:
            os.rmdir(os.path.join(root, d))
    os.rmdir(REAL_PROJECT_DIR)
    os.rmdir(os.path.join(PROJECTS_ROOT, REAL_PROJECT_SLUG))

# fail-closed on empty stdin
r = subprocess.run(["bash", HOOK], input="", capture_output=True, text=True)
ok = '"deny"' in r.stdout
fails += 0 if ok else 1
print(f"  {'PASS' if ok else 'FAIL'}  пустой ввод -> deny (fail-closed)")

print(f"\n  итог пройдено, провалов: {fails}")
sys.exit(1 if fails else 0)
