#!/usr/bin/env bash
# plan-gate.sh — PreToolUse hook: block execution actions unless an APPROVED plan exists.
#
# Usage: Claude Code calls this automatically via hooks config.
#        Set CLAUDE_GATE_BYPASS=1 to skip the gate (anti-recursion / manual escape).
#
# Reads PreToolUse JSON from stdin. Outputs Claude Code PreToolUse JSON to stdout, exit 0.
# Fail-closed: any error → deny.

# Plans live in the current project's ./plans/ folder, discovered via the project root
# Claude Code exports to hooks ($CLAUDE_PROJECT_DIR); fall back to cwd.
PLANS_DIR="${PLAN_GATE_PLANS_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}/plans}"

# Read stdin fully before passing to python3 (heredoc would eat it otherwise)
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

DENY_NO_PLAN = ("Blocked by plan-gate: no APPROVED plan on disk. "
                "Write a plan, get the user's explicit approval "
                "(set \"Status: APPROVED\" in the plan file), then retry this action.")

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

# Subagent spawns — always gated
if tool_name in ("Task", "Agent"):
    gated = True

elif tool_name == "Bash":
    command   = (tool_input.get("command") or "").strip()
    parts     = command.split()
    first_word = parts[0] if parts else ""

    # Read-only allowlist
    READ_ONLY_WORDS = {
        "ls", "cat", "head", "tail", "grep", "rg", "find",
        "pwd", "echo", "which", "file", "stat", "wc",
        "realpath", "readlink",
    }
    GIT_READ_PREFIXES = (
        "git status", "git diff", "git log", "git show", "git branch",
    )

    is_read_only = (
        first_word in READ_ONLY_WORDS
        or any(command == g or command.startswith(g + " ") for g in GIT_READ_PREFIXES)
    )

    if is_read_only:
        gated = False
    else:
        # Denylist-only: gate explicit mutations; ambiguous (tests, scripts) → free
        MUTATING_WORDS = {"mv", "rm", "cp"}
        MUTATING_SUBSTRINGS = (
            "npm install", "pip install", "brew install",
            "git commit", "git push",
            "npm run build", "deploy",
        )

        is_mutating = (
            first_word in MUTATING_WORDS
            or first_word == "make"
            or any(s in command for s in MUTATING_SUBSTRINGS)
        )

        # only explicit mutations gated; ambiguous/everything else → free
        gated = is_mutating

else:
    # Read, Grep, Glob, Edit, Write, and everything else → FREE
    gated = False

# --- if not gated, allow immediately ---
if not gated:
    print(ALLOW_JSON)
    sys.exit(0)

# --- check for an approved plan ---
try:
    plan_files = glob.glob(os.path.join(plans_dir, "*.md"))
    approved = False
    for path in plan_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip().lstrip("*").lstrip().lstrip("*").strip()
                    if stripped.lower().startswith("status:") and "approved" in stripped.lower():
                        approved = True
                        break
            if approved:
                break
        except OSError:
            continue
except Exception:
    print(deny_json(DENY_ERROR))
    sys.exit(0)

if approved:
    print(ALLOW_JSON)
else:
    print(deny_json(DENY_NO_PLAN))

sys.exit(0)
PYEOF
