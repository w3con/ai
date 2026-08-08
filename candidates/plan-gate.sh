#!/usr/bin/env bash
# plan-gate.sh — PreToolUse hook: block build/implementation agent spawns unless
# THE BRIEF HANDED TO THAT AGENT carries a pass marker.
#
# Accepted markers, each on a line of its own:
#   <!-- card:ready -->   the task card passed validation by bin/card-context
#   <!-- scope:pass -->   legacy: a plan file in ai/plans/ signed by the (now
#                         deleted) scope agent; kept only so the fifteen frozen
#                         plans still work, and removed when they are retired
#
# What IS gated:   Task / Agent spawns (build and implementation agents).
# What is NOT gated: Bash commands of any kind. Read, Edit, Write, Grep, Glob,
#                    and every other non-spawn tool.
#
# Allowlisted agent types (always allowed, no marker check):
#   Explore, Plan, trace-audit, card-critic — read-only agents that gather or
#   review and never write, so gating them protects nothing. card-critic
#   (HRN-94, 2026-08-08) reads one task card alone, looking for planning
#   faults no script can check, and is the recorded standing exception to the
#   rule that every other agent runs only on the owner's word — spawned only
#   by the coordinator, as part of signing a card with bin/economy-sign.
#
# ---------------------------------------------------------------------------
# THE CONTRACT (path binding set 2026-07-10; marker changed 2026-08-01, both
# approved by Alex — see "Why" below)
#
#   To spawn a build agent you MUST name its brief in the agent's prompt, as a
#   path ending in .md. For new work that brief is the task card under
#   ai/timeline/tasks/ or ai/harness/tasks/; for the frozen legacy work it is a
#   plan file. That named file must exist and must contain one of the accepted
#   marker lines. Nothing else is consulted.
#
#   Absolute paths are preferred and always work, including across repositories.
#   Relative paths are resolved against $CLAUDE_PROJECT_DIR, then $PWD, and for
#   each of those roots also against ai/timeline/tasks, ai/harness/tasks, plans
#   and ai/plans. A leading ~ is expanded.
#
# Why the path binding. The gate used to scan <project>/plans/*.md and allow the
# spawn if ANY file there held the marker. That is not the question worth
# asking. In Dev/app, 26 plans sat in ai/plans and 20 still carried a PASS from
# tasks closed long ago, so the gate was permanently open: any build agent
# passed, for any task, approved or not. It had stopped protecting anything and
# only looked like it did. Binding the check to the file actually handed to the
# executor fixes that, and needs no directory scanning at all.
#
# Why the marker changed. The scope and ready agents are deleted (PLT-22). The
# work they did mechanically — required fields present, links resolving, the
# out-of-scope list and acceptance criteria and checkpoints non-empty — moves
# into bin/card-context, which writes <!-- card:ready --> only when every one of
# those checks passes. A script that costs nothing replaces two agents that cost
# a great deal, and the gate keeps working unchanged in shape: something checked
# the brief, and left a signature saying so.
#
# The cost, stated plainly: a build agent spawned without naming its brief is
# denied. That is the point, not a side effect.
# ---------------------------------------------------------------------------
#
# Bypass: set CLAUDE_GATE_BYPASS=1 to skip the gate entirely.
# Fail-closed: any parse error or unexpected exception → deny.
#
# Usage: Claude Code calls this automatically via hooks config.
#        $PLAN_GATE_SEARCH_ROOTS (colon-separated) overrides the roots used to
#        resolve relative paths; used by the test suite.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
SEARCH_ROOTS="${PLAN_GATE_SEARCH_ROOTS:-${PROJECT_DIR}:${PWD}}"
# HRN-121: the shared helper module brief_reader.py is importable only from the real
# hooks/ directory, so it is found at one fixed location, HOOK_INSTALL_HOOKS_DIR — the
# exact env var bin/hook-install itself already reads for "the real hooks directory",
# defaulting to the same literal path — rather than derived from where THIS script file
# happens to sit. That derivation ("beside itself", via BASH_SOURCE) is correct once
# installed, because an installed hook and brief_reader.py sit in the same directory, but
# wrong for a candidate under test, which sits in candidates/ instead. Shared verbatim
# with hooks/card-touch-gate.sh.
HOOKS_DIR="${HOOK_INSTALL_HOOKS_DIR:-/Users/laptop/Dev/ai/hooks}"

# Read stdin fully before passing to python3
STDIN_DATA="$(cat)"

exec python3 - "$SEARCH_ROOTS" "$STDIN_DATA" "$HOOKS_DIR" <<'PYEOF'
import sys
import os
import json

search_roots = sys.argv[1]
stdin_data   = sys.argv[2]
hooks_dir    = sys.argv[3]

sys.path.insert(0, hooks_dir)
try:
    import brief_reader  # HRN-109: the brief-path reading shared with card-touch-gate.sh
except ImportError as exc:
    # HRN-121, AC2: a helper that cannot be loaded is reported plainly rather than being
    # absorbed into a silent decision. plan-gate.sh fails CLOSED on any other unexpected
    # error (see the file header), so this follows the same posture: an explicit deny,
    # naming the helper, the directory it was sought in, and the underlying error, rather
    # than an uncaught traceback that leaves the caller with no valid decision at all.
    print(f"plan-gate: HELPER LOAD FAILURE — could not import 'brief_reader' from "
          f"'{hooks_dir}': {exc}. Failing closed (deny) rather than an uncaught crash.",
          file=sys.stderr)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Blocked by plan-gate: internal error — could not load its shared "
                f"helper module 'brief_reader' from '{hooks_dir}' ({exc}); failing "
                "closed rather than deciding with no working brief-resolution logic."
            ),
        }
    }))
    sys.exit(0)

# --- output helpers ---

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    escaped = json.dumps(reason)
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + escaped + '}}')

DENY_NO_BRIEF_NAMED = (
    "Blocked by plan-gate: the agent prompt names no brief. "
    "A build agent must be handed the document it implements: include the path "
    "to the task card (a .md file under ai/timeline/tasks/ or ai/harness/tasks/, "
    "absolute path preferred) in the agent's prompt. The gate then checks that "
    "THAT file carries the marker '<!-- card:ready -->', which bin/card-context "
    "writes only when the card validates. Read-only agents (Explore, Plan, "
    "trace-audit, card-critic) are exempt and need no brief."
)

DENY_NO_MARKER = (
    "Blocked by plan-gate: the brief named in the agent prompt carries no pass "
    "marker. Run bin/card-context on the card first — when every required field "
    "is filled, every link resolves, and the out-of-scope list, acceptance "
    "criteria and checkpoints are all non-empty, it writes the line "
    "'<!-- card:ready -->' into the card. If it refuses, it names what is "
    "missing; fill that in rather than writing the marker by hand. "
    "Files examined: {}"
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

# Only Task/Agent spawns are gated. Everything else is free.
if tool_name not in ("Task", "Agent"):
    print(ALLOW_JSON)
    sys.exit(0)

# --- allowlist: read-only agent types never need a brief ---
# They gather or review and never write, so gating them protects nothing.
ALLOWLISTED_SUBTYPES = {"Explore", "Plan", "trace-audit", "card-critic"}

subagent_type = (tool_input.get("subagent_type") or "").strip()
agent_name    = (tool_input.get("name") or "").strip().lower()

if subagent_type in ALLOWLISTED_SUBTYPES or agent_name in {s.lower() for s in ALLOWLISTED_SUBTYPES}:
    print(ALLOW_JSON)
    sys.exit(0)

# --- find the brief(s) the agent was handed ---
MARKER_CARD   = "<!-- card:ready -->"    # written by bin/card-context
MARKER_LEGACY = "<!-- scope:pass -->"    # frozen plans in ai/plans/ only
MAX_BRIEF_BYTES = 2 * 1024 * 1024        # a brief is prose; anything larger is not one

def has_marker(path):
    """True when the file carries an accepted pass marker on a line of its own."""
    try:
        if os.path.getsize(path) > MAX_BRIEF_BYTES:
            return False
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip() in (MARKER_CARD, MARKER_LEGACY):
                    return True
    except OSError:
        return False
    return False

try:
    roots = [r for r in search_roots.split(":") if r]

    tokens = brief_reader.brief_tokens(tool_input)

    if not tokens:
        print(deny_json(DENY_NO_BRIEF_NAMED))
        sys.exit(0)

    existing = []       # named .md files that actually exist — reported on denial
    for token in tokens:
        for path in brief_reader.resolve(token, roots):
            if os.path.isfile(path):
                if has_marker(path):
                    print(ALLOW_JSON)
                    sys.exit(0)
                if path not in existing:
                    existing.append(path)

    if not existing:
        print(deny_json(DENY_NO_BRIEF_NAMED))
        sys.exit(0)

    shown = ", ".join(existing[:5])
    if len(existing) > 5:
        shown += ", … (+%d more)" % (len(existing) - 5)

    print(deny_json(DENY_NO_MARKER.format(shown)))
    sys.exit(0)

except Exception:
    print(deny_json(DENY_ERROR))
    sys.exit(0)
PYEOF
