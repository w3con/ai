#!/usr/bin/env bash
# memory-store-guard.sh — PreToolUse hook: refuse a Write/Edit whose target file
# resolves into a real (non-symlink) per-project memory directory, so memory
# cannot silently fork back into N copies after the 2026-07-10 merge into one
# shared store.
#
# What IS blocked: a Write or Edit whose file_path's PARENT directory, after
#                  os.path.realpath, is `~/.claude/projects/<anything>/memory`
#                  or lies inside such a directory. That is a real directory —
#                  not yet a symlink to the shared store — so a write there
#                  would recreate a project-local memory fork.
# What is NOT blocked: a Write/Edit whose parent resolves inside
#                      `~/Dev/ai/memory` itself, INCLUDING when reached through
#                      a project's `memory` symlink — realpath follows the
#                      symlink and lands inside the shared store, so it passes.
#                      Any other tool (Bash, Read, …) and any other path
#                      (`/tmp`, `~/Dev/ai/skills`, …) pass untouched.
#
# Why this exists. Plan `ai/plans/memory-one-store.md` (D2, D3) moved every
# project's memory into one shared store at `~/Dev/ai/memory` and replaced each
# `~/.claude/projects/<slug>/memory` with a symlink to it (Phase 1–2, done
# 2026-07-10). Without a hook, the very next session in a project would just
# write a fresh file into that path, and — since a plain directory write does
# not care whether the directory is a symlink — memory would fork right back
# into per-project silos with no error at all. D3 is explicit that the check
# must compare resolved paths, not match text: `settings-write-guard.sh`
# (the model this hook copies) went through three false positives today from
# exactly that mistake — see its own header for the specifics.
#
# What a deny means: the project directory is a real directory, not (yet) a
# symlink to the shared store. Run `~/Dev/ai/bootstrap.sh` to install it — that
# script's `symlink()` function refuses to clobber a non-empty directory, so it
# is safe to run at any time.
#
# Bypass: CLAUDE_GATE_BYPASS=1 (shared with plan-gate.sh and settings-write-guard.sh).
# Fail-closed: any parse error → deny.

STDIN_DATA="$(cat)"

exec python3 - "$STDIN_DATA" <<'PYEOF'
import sys
import os
import json

stdin_data = sys.argv[1]

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

DENY_PROJECT_MEMORY = (
    "Blocked by memory-store-guard: memory is a single shared store now, at "
    "~/Dev/ai/memory, visible from every project. This path is a real (non-symlink) "
    "project memory directory, not a link into that store, so writing here would "
    "recreate a project-local memory fork. Run ~/Dev/ai/bootstrap.sh to install the "
    "symlink for this project, then retry the write against the shared store."
)

DENY_ERROR = "Blocked by memory-store-guard: gate error, failing closed."

try:
    if not stdin_data.strip():
        raise ValueError("empty stdin")
    data = json.loads(stdin_data)
except Exception:
    print(deny_json(DENY_ERROR))
    sys.exit(0)

if os.environ.get("CLAUDE_GATE_BYPASS") == "1":
    print(ALLOW_JSON)
    sys.exit(0)

if data.get("tool_name") not in ("Write", "Edit"):
    print(ALLOW_JSON)
    sys.exit(0)

file_path = (data.get("tool_input") or {}).get("file_path") or ""
if not file_path:
    # No path to judge — nothing this guard is built to catch. Let the normal
    # tool-level validation (which will itself reject a missing path) handle it.
    print(ALLOW_JSON)
    sys.exit(0)

try:
    file_path = os.path.expanduser(file_path)
    parent_dir = os.path.dirname(file_path) or "."
    resolved_parent = os.path.realpath(parent_dir)
except Exception:
    print(deny_json(DENY_ERROR))
    sys.exit(0)

HOME = os.path.expanduser("~")
SHARED_STORE = os.path.realpath(os.path.join(HOME, "Dev", "ai", "memory"))
PROJECTS_ROOT = os.path.realpath(os.path.join(HOME, ".claude", "projects"))

def is_under(path, base):
    path = path.rstrip(os.sep)
    base = base.rstrip(os.sep)
    return path == base or path.startswith(base + os.sep)

# Symlinked project memory resolves straight into the shared store — allow.
# This also covers writes made directly against ~/Dev/ai/memory.
if is_under(resolved_parent, SHARED_STORE):
    print(ALLOW_JSON)
    sys.exit(0)

# A REAL (non-symlink) project memory directory: <PROJECTS_ROOT>/<slug>/memory,
# or anything nested inside it. Checked by path shape after realpath, not by
# string content of the original path — the ".." and "~" cases resolve to the
# same real directory and must be caught the same way.
if is_under(resolved_parent, PROJECTS_ROOT):
    rel = os.path.relpath(resolved_parent, PROJECTS_ROOT)
    parts = rel.split(os.sep)
    if len(parts) >= 2 and parts[1] == "memory":
        print(deny_json(DENY_PROJECT_MEMORY))
        sys.exit(0)

print(ALLOW_JSON)
sys.exit(0)
PYEOF
