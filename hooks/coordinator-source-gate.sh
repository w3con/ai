#!/usr/bin/env bash
# coordinator-source-gate.sh — PreToolUse hook: refuse the coordinator's own Edit, Write or
# NotebookEdit of a file under one of this project's three product source directories.
#
# Built for ai/harness/tasks/HRN-117_the-coordinator-cannot-edit-product-source-code-with-
# its-own-hand-because-only-an-executor-may.md in the app repository (Dev/app). Read that
# card for the full "why" — the short version is that on 2026-08-07 the coordinator
# diagnosed a rendering bug, then edited dpp_frontend/src/vendor/qrcode.js with its own
# hand instead of founding a card and handing the fix to an executor, and nothing in the
# machine objected until the owner typed a message to stop it. This hook is that objection,
# built into the machine instead of depending on the owner noticing in time.
#
# What IS blocked: an Edit, Write or NotebookEdit tool call whose target path — file_path
#   for Edit/Write, notebook_path for NotebookEdit — lies inside one of three directories,
#   checked as a path segment anywhere in the normalized path so that the same checkout, a
#   linked git worktree, or a relative path given from the repository root are all
#   recognised alike, exactly the way hooks/brief_reader.py's canonical_card() already
#   ignores whatever directory prefix comes before the part that actually identifies the
#   target:
#     - dpp_demo/app        (the whole Go backend module)
#     - dpp_frontend/src    (the manager UI's own source, not its build output in
#                             dpp_frontend/dist)
#     - dpp-vldt/src         (the public viewer's own source)
#   and whose call carries NO agent_id in the hook's own payload — the same discriminator
#   hooks/card-touch-gate.sh already relies on and that HRN-46 confirmed reliable: present
#   and non-empty means a subagent (an executor) made the call, absent means the
#   coordinator did.
# What is NOT blocked: any call carrying an agent_id, whatever path it names — an executor
#   is never affected by this hook, because building product source code by hand is
#   exactly an executor's own legitimate work. Any tool other than Edit, Write or
#   NotebookEdit. Any path outside the three directories above, for the coordinator or an
#   executor alike — task cards, epics, feature pages, anything under ai/, kb/, bin/,
#   .githooks/ and the hooks directory itself all stay writable by the coordinator, because
#   founding and maintaining those documents is exactly the coordinator's own legitimate
#   work. Any session working in a project other than this one, because none of its paths
#   will ever contain one of the three markers above.
#
# What a deny means: found a task card describing the work and hand it to an executor —
# the coordinator's hand does not touch product source code, ever, no matter how small or
# how urgent the fix looks.
#
# Bypass: CLAUDE_GATE_BYPASS=1 — the same shared, deliberately-named override the other
# hooks in this directory already carry (plan-gate.sh, settings-write-guard.sh,
# memory-store-guard.sh, card-touch-gate.sh), so a genuine emergency has one well-known way
# through that nobody sets by accident, rather than this hook inventing a second bypass
# name for the same idea.
#
# Why this hook fails OPEN (allows) rather than closed on any internal error, exactly like
# card-touch-gate.sh and for the same reason stated at length in that script's own header:
# a hook that governs real work and can be reached from a payload shape nobody has tested
# yet must not turn a bug in itself into a frozen machine. A missed refusal costs, at worst,
# one coordinator edit that a later review catches; a hook that fails closed on a bug
# refuses every Edit, Write and NotebookEdit call on the machine, coordinator and executor
# alike, the moment it hits anything it does not expect. That asymmetry is why this file
# also captures its Python program's output to a file rather than trusting standard output
# directly, and replaces anything that is not a real decision — a traceback, an empty
# file, a program that never started — with an explicit allowance, precisely the defence
# card-touch-gate.sh's own header explains was missing on 2026-08-07 and cost two frozen
# executors and a frozen coordinator in one evening.
#
# This file must never be edited in place while any agent is running, for the same reason:
# a shell reads a script incrementally, so a half-written file is a half-written program.
# A new version is built elsewhere (in this project, under Dev/ai/candidates/), tested
# there with coordinator-source-gate.test.py, and only then installed onto the live path by
# bin/hook-install, which writes under a temporary name and renames onto the live path in
# one atomic step.

ALLOW_DECISION='{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

STDIN_DATA="$(cat)"

GATE_TMP="${COORDINATOR_SOURCE_GATE_STATE_DIR:-${TMPDIR:-/tmp}/claude-coordinator-source-gate}"
mkdir -p "$GATE_TMP" 2>/dev/null
DECISION_FILE="$GATE_TMP/.decision.$$"

python3 - "$STDIN_DATA" > "$DECISION_FILE" 2>>"$GATE_TMP/.stderr.log" <<'PYEOF'
import sys
import os
import json

stdin_data = sys.argv[1]

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

def allow_and_exit():
    print(ALLOW_JSON)
    sys.exit(0)

# The three product source directories this hook protects, checked as a path segment
# anywhere in the normalized target path — never anchored to one particular checkout, so
# the shared checkout, a linked git worktree cut under .claude/worktrees/, and a relative
# path given from a repository root are all recognised the same way. dpp_frontend and
# dpp-vldt are scoped to their own src/ subdirectory alone, deliberately narrower than the
# whole package, so a build artifact such as dpp_frontend/dist/index.html — which is
# committed, generated output, not hand-written source — is left untouched by this hook.
GUARDED_MARKERS = ("dpp_demo/app", "dpp_frontend/src", "dpp-vldt/src")

DENY_TEMPLATE = (
    "Blocked by coordinator-source-gate: this call would have the coordinator write {path} "
    "with its own hand, and that path lies inside this project's product source; found a "
    "task card describing the work and hand it to an executor instead — the coordinator "
    "never edits product source code directly."
)


def guarded_path(path):
    """True when `path`, once normalized, carries one of GUARDED_MARKERS as a path segment
    of its own — matched as a whole directory-name component so that, for instance,
    dpp_demo/app never matches a sibling directory that merely starts with the same
    letters. Works the same whether `path` is absolute (the ordinary case for every tool
    call this hook actually sees) or relative."""
    if not isinstance(path, str) or not path:
        return False
    norm = os.path.normpath(os.path.expanduser(path)).replace(os.sep, "/")
    for marker in GUARDED_MARKERS:
        if norm == marker or norm.startswith(marker + "/") or \
                norm.endswith("/" + marker) or ("/" + marker + "/") in norm:
            return True
    return False


def target_path(tool_name, tool_input):
    """The path this call actually names, read from whichever key the tool in question
    uses for it: file_path for Edit and Write, notebook_path for NotebookEdit. A
    defensive fallback to a bare "path" key is kept in case a future tool version ever
    uses that name instead — it costs nothing and only ever widens what this hook can
    recognise, never what it blocks, since an unrecognised path still falls through to
    allow_and_exit() below."""
    if tool_name == "NotebookEdit":
        return tool_input.get("notebook_path") or tool_input.get("file_path") or tool_input.get("path")
    return tool_input.get("file_path") or tool_input.get("path")


try:
    if not stdin_data.strip():
        allow_and_exit()
    data = json.loads(stdin_data)
except Exception:
    # Fail OPEN, deliberately, exactly as card-touch-gate.sh does and for the same reason
    # stated in this script's own header comment.
    allow_and_exit()

if os.environ.get("CLAUDE_GATE_BYPASS") == "1":
    allow_and_exit()

agent_id = data.get("agent_id")
if agent_id:
    # A call carrying an agent_id is an executor's own call, never the coordinator's — an
    # executor building product source code by hand is exactly its legitimate work, and
    # this hook has no business in its way (HRN-117 acceptance criterion 3).
    allow_and_exit()

tool_name = data.get("tool_name") or ""
if tool_name not in ("Edit", "Write", "NotebookEdit"):
    allow_and_exit()

tool_input = data.get("tool_input") or {}

try:
    path = target_path(tool_name, tool_input)
    if guarded_path(path):
        print(deny_json(DENY_TEMPLATE.format(path=path)))
        sys.exit(0)
    allow_and_exit()
except Exception:
    # Same fail-open decision as the JSON-parse case above, and for the same reason.
    allow_and_exit()
PYEOF

DECISION="$(cat "$DECISION_FILE" 2>/dev/null)"
rm -f "$DECISION_FILE"

case "$DECISION" in
  *permissionDecision*) printf '%s\n' "$DECISION" ;;
  *)                    printf '%s\n' "$ALLOW_DECISION" ;;
esac
exit 0
