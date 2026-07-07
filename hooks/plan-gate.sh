#!/usr/bin/env bash
# plan-gate.sh — PreToolUse hook: block build/implementation agent spawns unless
# an on-disk plan has a scope-agent PASS verdict (sentinel: <!-- scope:pass -->).
#
# What IS gated:   Task / Agent spawns (build and implementation agents).
# What is NOT gated: Bash commands of any kind (no longer gated — prior overreach removed).
#                    Read, Edit, Write, Grep, Glob, and all other non-spawn tools.
#
# Allowlisted agent types (always allowed, no sentinel check):
#   scope, Explore, Plan — gathering/checking agents that must run freely so
#   you can GET the scope verdict in the first place (no chicken-and-egg).
#
# For all other agent spawns: scan plans/*.md for the sentinel line
#   <!-- scope:pass -->
# If present in any plan → allow. If absent → deny with explanation.
#
# Bypass: set CLAUDE_GATE_BYPASS=1 to skip the gate entirely.
# Fail-closed: any parse error or unexpected exception → deny.
#
# Usage: Claude Code calls this automatically via hooks config.
#        Plan directories are discovered from $CLAUDE_PROJECT_DIR (set by Claude Code),
#        falling back to $PWD. Both <project>/plans and <project>/ai/plans are scanned
#        (projects following the ai/-tree convention keep plans in ai/plans — change
#        approved by Alex, 2026-07-07). Override with $PLAN_GATE_PLANS_DIR for testing
#        (colon-separated list of directories).

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
PLANS_DIR="${PLAN_GATE_PLANS_DIR:-${PROJECT_DIR}/plans:${PROJECT_DIR}/ai/plans}"

# Read stdin fully before passing to python3
STDIN_DATA="$(cat)"

exec python3 - "$PLANS_DIR" "$STDIN_DATA" <<'PYEOF'
import sys
import os
import json
import glob

plans_dir  = sys.argv[1]
stdin_data = sys.argv[2]

# --- output helpers ---

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    escaped = json.dumps(reason)
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + escaped + '}}')

DENY_NO_SENTINEL = (
    "Blocked by plan-gate: no scope PASS verdict found in any plan — "
    "run the scope agent on the plan first. "
    "The scope agent writes '<!-- scope:pass -->' into the plan file on PASS; "
    "that sentinel must be present before a build/implementation agent can be spawned."
)

DENY_ERROR = "Blocked by plan-gate: gate error, failing closed."

# --- parse stdin ---
try:
    if not stdin_data.strip():
        raise ValueError("empty stdin")
    data = json.loads(stdin_data)
except Exception:
    print(deny_json(DENY_ERROR))
    sys.exit(0)

# --- bypass ---
if os.environ.get("CLAUDE_GATE_BYPASS") == "1":
    print(ALLOW_JSON)
    sys.exit(0)

# --- classify tool ---
tool_name  = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

# Only Task/Agent spawns are gated. Everything else (Bash, Read, Edit, Write, etc.) is free.
if tool_name not in ("Task", "Agent"):
    print(ALLOW_JSON)
    sys.exit(0)

# --- allowlist: gathering/checking agent types never need a sentinel ---
# These agents must be spawnable to produce the verdict in the first place.
ALLOWLISTED_SUBTYPES = {"scope", "Explore", "Plan"}

subagent_type = (tool_input.get("subagent_type") or "").strip()
agent_name    = (tool_input.get("name") or "").strip().lower()

# Match by subagent_type field, or by name matching an allowlisted type
if subagent_type in ALLOWLISTED_SUBTYPES or agent_name in {s.lower() for s in ALLOWLISTED_SUBTYPES}:
    print(ALLOW_JSON)
    sys.exit(0)

# --- sentinel check: scan all plan files for <!-- scope:pass --> ---
SENTINEL = "<!-- scope:pass -->"

try:
    plan_files = []
    for d in plans_dir.split(":"):
        if d:
            plan_files.extend(glob.glob(os.path.join(d, "*.md")))
    sentinel_found = False
    for path in plan_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip() == SENTINEL:
                        sentinel_found = True
                        break
            if sentinel_found:
                break
        except OSError:
            continue
except Exception:
    print(deny_json(DENY_ERROR))
    sys.exit(0)

if sentinel_found:
    print(ALLOW_JSON)
else:
    print(deny_json(DENY_NO_SENTINEL))

sys.exit(0)
PYEOF
