#!/usr/bin/env bash
# plan-gate.sh — PreToolUse hook: block build/implementation agent spawns unless
# THE PLAN HANDED TO THAT AGENT carries a scope-agent PASS verdict
# (sentinel: <!-- scope:pass --> on a line of its own).
#
# If the plan's header carries the line "Type: feat", the gate additionally
# requires a ready-agent PASS verdict (sentinel: <!-- ready:pass --> on a line
# of its own). Plans without "Type: feat" in their header are unaffected.
#
# What IS gated:   Task / Agent spawns (build and implementation agents).
# What is NOT gated: Bash commands of any kind. Read, Edit, Write, Grep, Glob,
#                    and every other non-spawn tool.
#
# Allowlisted agent types (always allowed, no sentinel check):
#   scope, Explore, Plan — gathering/checking agents that must run freely so
#   you can GET the scope verdict in the first place (no chicken-and-egg).
#
# ---------------------------------------------------------------------------
# THE CONTRACT (changed 2026-07-10, approved by Alex — see "Why" below)
#
#   To spawn a build agent you MUST name the plan file in the agent's prompt,
#   as a path ending in .md. That named file must exist and must contain the
#   sentinel line. Nothing else is consulted.
#
#   Absolute paths are preferred and always work, including across repositories.
#   Relative paths are resolved against $CLAUDE_PROJECT_DIR, then $PWD, then
#   <root>/plans and <root>/ai/plans for each of those roots. A leading ~ is
#   expanded.
#
# Why it changed. The gate used to scan <project>/plans/*.md and allow the spawn
# if ANY file there held the sentinel. That is not the question worth asking.
# In Dev/app, 26 plans sat in ai/plans and 20 still carried a PASS from tasks
# closed long ago, so the gate was permanently open: any build agent passed,
# for any task, approved or not. It had stopped protecting anything and only
# looked like it did. It also could not see a plan living in a different
# repository (the shared tooling repo, ~/Dev/ai/plans), so legitimate work
# there was blocked while unapproved work in Dev/app sailed through — exactly
# backwards. Binding the check to the plan actually handed to the executor
# fixes both at once, and needs no directory scanning at all.
#
# The cost, stated plainly: a build agent spawned without naming its plan is
# now denied. That is the point, not a side effect.
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

# Read stdin fully before passing to python3
STDIN_DATA="$(cat)"

exec python3 - "$SEARCH_ROOTS" "$STDIN_DATA" <<'PYEOF'
import sys
import os
import re
import json

search_roots = sys.argv[1]
stdin_data   = sys.argv[2]

# --- output helpers ---

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    escaped = json.dumps(reason)
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + escaped + '}}')

DENY_NO_PLAN_NAMED = (
    "Blocked by plan-gate: the agent prompt names no plan file. "
    "A build agent must be handed the plan it implements: include the path to "
    "the approved plan (a .md file, absolute path preferred) in the agent's "
    "prompt. The gate then checks that THAT file carries the scope PASS "
    "sentinel '<!-- scope:pass -->'. Read-only agents (scope, Explore, Plan) "
    "are exempt and need no plan."
)

DENY_NO_SENTINEL = (
    "Blocked by plan-gate: the plan named in the agent prompt carries no scope "
    "PASS verdict. Run the scope agent on it first — on PASS it writes the "
    "sentinel line '<!-- scope:pass -->' into the plan file. "
    "Plans examined: {}"
)

DENY_FEAT_GATES = (
    "Blocked by plan-gate: the plan named in the agent prompt has 'Type: feat' in its header, "
    "which requires BOTH gate sentinels before a build agent may spawn — "
    "'<!-- ready:pass -->' (ready agent) and '<!-- scope:pass -->' (scope agent). "
    "Missing: {}. Run the missing agent(s) on this plan first; each writes its own sentinel "
    "into the plan file on a genuine PASS. Plans examined: {}"
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

# --- allowlist: gathering/checking agent types never need a plan ---
# These agents must be spawnable to produce the verdict in the first place.
ALLOWLISTED_SUBTYPES = {"scope", "Explore", "Plan"}

subagent_type = (tool_input.get("subagent_type") or "").strip()
agent_name    = (tool_input.get("name") or "").strip().lower()

if subagent_type in ALLOWLISTED_SUBTYPES or agent_name in {s.lower() for s in ALLOWLISTED_SUBTYPES}:
    print(ALLOW_JSON)
    sys.exit(0)

# --- find the plan(s) the agent was handed ---
SENTINEL_SCOPE = "<!-- scope:pass -->"
SENTINEL_READY = "<!-- ready:pass -->"
MAX_PLAN_BYTES = 2 * 1024 * 1024   # a plan is prose; anything larger is not one

# A plan's header carries "Type: feat" (optionally wrapped in markdown bold,
# e.g. "**Type:** feat"); only the first HEADER_MAX_LINES lines count as header.
TYPE_FEAT_RE = re.compile(r'^\s*\*{0,2}Type:\*{0,2}\s*feat\b', re.IGNORECASE)
HEADER_MAX_LINES = 40

# Any token that ends in .md. Deliberately permissive about the leading part so
# that ~, $HOME-style absolutes, ./ and bare names all get picked up; each
# candidate is then resolved and must exist on disk to matter.
MD_PATH_RE = re.compile(r'[~\w./\\-]*[\w-]\.md\b')

def candidate_texts(ti):
    for key in ("prompt", "description"):
        v = ti.get(key)
        if isinstance(v, str) and v:
            yield v

def resolve(token, roots):
    """Every plausible on-disk location for a path token, most specific first."""
    t = os.path.expanduser(token)
    if os.path.isabs(t):
        return [os.path.normpath(t)]
    out = []
    for root in roots:
        if not root:
            continue
        out.append(os.path.normpath(os.path.join(root, t)))
        # Convention: plans live in <root>/plans or <root>/ai/plans.
        if not t.startswith(("plans/", "ai/plans/", "./plans/", "./ai/plans/")):
            out.append(os.path.normpath(os.path.join(root, "plans", t)))
            out.append(os.path.normpath(os.path.join(root, "ai", "plans", t)))
    return out

def is_type_feat(path):
    try:
        if os.path.getsize(path) > MAX_PLAN_BYTES:
            return False
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= HEADER_MAX_LINES:
                    break
                if TYPE_FEAT_RE.match(line):
                    return True
    except OSError:
        return False
    return False

def found_sentinels(path):
    """Which of {'scope', 'ready'} sentinels are present in this plan file."""
    found = set()
    try:
        if os.path.getsize(path) > MAX_PLAN_BYTES:
            return found
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if s == SENTINEL_SCOPE:
                    found.add("scope")
                elif s == SENTINEL_READY:
                    found.add("ready")
    except OSError:
        pass
    return found

try:
    roots = [r for r in search_roots.split(":") if r]

    tokens = []
    for text in candidate_texts(tool_input):
        tokens.extend(MD_PATH_RE.findall(text))

    # De-duplicate, preserving order.
    seen = set()
    tokens = [t for t in tokens if not (t in seen or seen.add(t))]

    if not tokens:
        print(deny_json(DENY_NO_PLAN_NAMED))
        sys.exit(0)

    existing = []       # named .md files that actually exist — reported on denial
    best = None         # (path, is_feat, missing_gates) for the most informative denial
    for token in tokens:
        for path in resolve(token, roots):
            if os.path.isfile(path):
                if path not in existing:
                    existing.append(path)
                feat = is_type_feat(path)
                required = ["scope", "ready"] if feat else ["scope"]
                found = found_sentinels(path)
                missing = [g for g in required if g not in found]
                if not missing:
                    print(ALLOW_JSON)
                    sys.exit(0)
                if best is None:
                    best = (path, feat, missing)

    if not existing:
        print(deny_json(DENY_NO_PLAN_NAMED))
        sys.exit(0)

    shown = ", ".join(existing[:5])
    if len(existing) > 5:
        shown += ", … (+%d more)" % (len(existing) - 5)

    _, best_feat, best_missing = best
    if best_feat:
        print(deny_json(DENY_FEAT_GATES.format(", ".join(best_missing), shown)))
    else:
        print(deny_json(DENY_NO_SENTINEL.format(shown)))
    sys.exit(0)

except Exception:
    print(deny_json(DENY_ERROR))
    sys.exit(0)
PYEOF
