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
# THE SECOND RULE (HRN-203, added 2026-08-16): one conversation runs one task.
# This rule only ever runs once the marker check above has already decided to
# allow a spawn, and it can only turn that allow into a deny — it never grants
# an allow of its own. On the FIRST spawn a conversation is allowed, the
# canonical form of the one token whose file actually carried the marker is
# written into a small per-conversation state file, keyed on a sanitized
# transcript_path exactly the way hooks/card-touch-gate.sh's own COORD rule
# already keys its per-session ceiling. A later spawn in the SAME conversation
# naming a DIFFERENT card is refused, naming both cards, /clear, /parallel and
# CLAUDE_GATE_BYPASS=1. A later spawn naming the SAME card is allowed every
# time, without limit — that is what an ordinary relay after a pace stop looks
# like. A token that is not card-shaped at all (a legacy plan file, most
# obviously) is never remembered, because remembering it would refuse the next
# spawn on a real card in the same conversation. This rule carries its own
# try/except, falling through to an allowance on any internal error of its
# own, unlike the marker check above, which fails closed.
#
# $PLAN_GATE_STATE_DIR overrides where this rule's per-conversation state is
# kept — its own variable, distinct from $CARD_TOUCH_GATE_STATE_DIR, so a run
# of this file's test suite never touches a live session's real state.
# ---------------------------------------------------------------------------
#
# Bypass: set CLAUDE_GATE_BYPASS=1 to skip the gate entirely.
# Fail-closed: any parse error or unexpected exception → deny (the marker check
#              only; the second rule above fails OPEN on its own internal error).
#
# Usage: Claude Code calls this automatically via hooks config.
#        $PLAN_GATE_SEARCH_ROOTS (colon-separated) overrides the roots used to
#        resolve relative paths; used by the test suite.
#        $PLAN_GATE_STATE_DIR overrides where the second rule keeps its
#        per-conversation state; used by the test suite.

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
# 2026-08-13: this default used to be the literal /Users/laptop/Dev/ai/hooks — one machine's
# home directory written into a file both machines run, so on any machine whose user is not
# "laptop" it named a directory that does not exist. It is now derived from where this file
# itself sits, falling back to this machine's own $HOME rather than another machine's.
_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${_SELF_DIR}/brief_reader.py" ]; then
  _HOOKS_DEFAULT="$_SELF_DIR"
elif [ -d "${_SELF_DIR}/../hooks" ]; then
  _HOOKS_DEFAULT="$(cd "${_SELF_DIR}/../hooks" && pwd)"
else
  _HOOKS_DEFAULT="${HOME}/Dev/ai/hooks"
fi
HOOKS_DIR="${HOOK_INSTALL_HOOKS_DIR:-$_HOOKS_DEFAULT}"

# Read stdin fully before passing to python3
STDIN_DATA="$(cat)"

exec python3 - "$SEARCH_ROOTS" "$STDIN_DATA" "$HOOKS_DIR" <<'PYEOF'
import sys
import os
import json
import re
import tempfile

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

# --- HRN-203: one conversation runs one task ---------------------------------------------
# Added alongside the marker check above, never in place of it: this rule only ever runs
# once the marker check has already decided to allow a spawn, and it can only turn that one
# allow into a deny — it never manufactures an allow of its own. On the FIRST spawn a
# conversation is allowed, the canonical form of the one token whose file actually carried
# the marker is written into a small per-conversation state file, keyed on a sanitized
# transcript_path exactly the way hooks/card-touch-gate.sh's own COORD rule already keys its
# per-session ceiling. A later spawn in the same conversation naming a different card is
# refused; a later spawn naming the SAME card is allowed every time, without limit, because
# that is what an ordinary relay after a pace stop looks like (a run the PACE rule in
# card-touch-gate.sh sent back to be resumed by a fresh executor on the same card).
#
# A token that is not card-shaped at all — most notably a legacy ai/plans/*.md file, which
# canonical_card() returns unchanged — is never remembered, because remembering it would
# refuse the next spawn on a real card in the very same conversation; canonical_card()
# returning its input unchanged is exactly how "not card-shaped" is recognised (see its own
# docstring in brief_reader.py).
#
# This block carries its own try/except, falling through to "allow, record nothing" on any
# internal error of its own. That is deliberate and differs from the rest of this file: the
# code path this rule is inserted into is wrapped in an outer try/except that fails CLOSED
# (see DENY_ERROR above), which is the right posture for the marker check itself but the
# wrong one for this rule — a bug in this new code must never turn into every spawn on the
# machine being refused, which is a failure this family of hooks has already lived through
# once (see hooks/card-touch-gate.sh's own header comment on why it fails open).
#
# $PLAN_GATE_STATE_DIR overrides where this rule's per-conversation state is kept — its own
# variable, distinct from $CARD_TOUCH_GATE_STATE_DIR, so a run of this file's test suite
# never reads or writes the coordinator's own live session state, and never collides with
# card-touch-gate.sh's own state files either.

SECOND_TASK_TEMPLATE = (
    "Blocked by plan-gate: this conversation already started an executor on {owned}, and "
    "this spawn names a different card, {attempted}. One conversation runs one task: finish "
    "the current task and close this conversation with /clear before starting the next one, "
    "or, when the two pieces of work genuinely must run at the same time, open a separate "
    "session with /parallel instead of spawning a second executor here. Set "
    "CLAUDE_GATE_BYPASS=1 only for a deliberate, known exception to this rule."
)


def _session_state_path(transcript_path):
    """The per-conversation state file for this rule, or None when no transcript_path was
    given at all — mirrors hooks/card-touch-gate.sh's own COORD rule, which fails open the
    same way when it cannot establish a session identifier to key state on."""
    if not transcript_path:
        return None
    state_dir = os.environ.get("PLAN_GATE_STATE_DIR") or \
        os.path.join(tempfile.gettempdir(), "claude-plan-gate")
    os.makedirs(state_dir, exist_ok=True)
    safe_session = re.sub(r'[^A-Za-z0-9_-]', '_', os.path.basename(str(transcript_path)))
    return os.path.join(state_dir, safe_session + ".json")


def second_task_deny_reason(token, transcript_path):
    """None to allow (recording the card as needed); otherwise the deny reason string for
    this rule. Never raises — every failure mode falls through to None, since the marker
    check has already decided to allow by the time this runs, and this rule must never turn
    an internal bug of its own into an unrelated denial."""
    try:
        card = brief_reader.canonical_card(token)
        if card == token:
            return None  # not card-shaped (e.g. a legacy plan file) — never tracked
        state_path = _session_state_path(transcript_path)
        if not state_path:
            return None  # no session identifier to key state on
        owned = None
        if os.path.isfile(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    owned = loaded.get("card")
            except Exception:
                owned = None  # a corrupt state file is a fresh start, not an error to deny on
        if owned is None:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"card": card}, f)
            return None
        if owned == card:
            return None
        return SECOND_TASK_TEMPLATE.format(owned=owned, attempted=card)
    except Exception:
        return None
# --- end HRN-203 -----------------------------------------------------------------------

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
transcript_path = data.get("transcript_path")

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
                    # HRN-203: the marker check has decided to allow; the second-task rule
                    # can only turn this into a deny, never an allow of its own.
                    second_reason = second_task_deny_reason(token, transcript_path)
                    if second_reason is not None:
                        print(deny_json(second_reason))
                        sys.exit(0)
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
