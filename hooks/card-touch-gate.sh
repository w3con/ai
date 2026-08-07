#!/usr/bin/env bash
# card-touch-gate.sh — PreToolUse hook: refuse an executor's next tool call once it has
# made more than a threshold number of calls without editing its own task card.
#
# Built for ai/harness/tasks/HRN-49_an-executor-that-has-not-touched-its-card-in-twenty-
# tool-calls-is-refused-until-it-does.md in the app repository (Dev/app). Read that card
# for the full "why"; this header states only what the script does and the safety
# decisions specific to running it live in Alex's global settings.json.
#
# What IS gated: every tool call made by a subagent (an executor) — the hook fires on any
#   tool name, because an executor's own working pace is measured in tool calls of every
#   kind, not only Edit/Write. A call is identified as the coordinator's own, and left
#   completely uncounted, by the ABSENCE of an "agent_id" key in the hook payload — the
#   same discriminator HRN-46 measured and confirmed: present and non-empty means a
#   subagent made the call, absent means the coordinator did.
# What resets the count to zero: an Edit or Write tool call whose file_path is the run's
#   own card — the ONE task-card-shaped path (ai/timeline/tasks/*.md or
#   ai/harness/tasks/*.md) named in the brief this agent_id was actually spawned with, read
#   through hooks/brief_reader.py (HRN-109), never guessed from any tool call the agent
#   makes on its own. That brief is recovered from the coordinator's own durable session
#   transcript (transcript_path in this hook's own payload), which records every Task/Agent
#   spawn as a toolUseResult object carrying the spawned agent's agentId, prompt and
#   description — the very same prompt hooks/plan-gate.sh already read at spawn time, run
#   through the very same brief_tokens()/canonical_card() pair, so the two gates cannot
#   disagree about which file is a run's brief. This is established once, on whichever call
#   is the first one this hook processes for a given agent_id, and never re-derived or
#   replaced afterwards (see the "once established, never replaced" state-handling note
#   below), so a run that reads, greps or edits some unrelated card along the way is never
#   mistaken for owning that card, and is never asked to edit it.
# What is NOT gated: the coordinator's own calls (no agent_id present), any run whose brief
#   cannot be recovered at all (no readable transcript record for its agent_id, or a brief
#   that names no task-card-shaped path — see "Fail open when the brief can't be read"
#   below), and a card edited through Bash (a heredoc, sed, or similar) rather than through
#   the Edit or Write tool — a stated, known gap rather than a hidden one: every executor is
#   separately instructed to tick a checkpoint through the Edit tool, so a Bash-based card
#   edit is not the realistic path this project's own executors take, unlike the
#   settings.json case settings-write-guard.sh exists to close.
#
# Fail open when the brief can't be read: an agent whose card this hook could never
# recover — the transcript record for its agent_id is missing, unreadable, or names no
# task-card-shaped path at all — is allowed past the threshold indefinitely, the same way an
# agent that has never been identified as one of this project's executors always has been.
# Refusing a run this hook cannot name a card for would tell it to edit a card it does not
# have and cannot produce, which is a permanent freeze with no way out, not a nudge — the
# one thing this hook's own header already says it must never do.
#
# Why this hook fails OPEN (allows) rather than closed on any internal error, unlike
# plan-gate.sh, settings-write-guard.sh and memory-store-guard.sh, which all fail closed.
# Those three hooks each protect one file or one narrow action, so a bug that makes one of
# them deny everything freezes one thing in one repository. This hook is registered with a
# wildcard matcher against EVERY tool call, in Alex's global settings.json, which is
# shared — not scoped to one project — by every Claude Code session on this machine. A
# parse bug here that failed closed would deny every tool call for every agent in every
# project the moment it hit a payload shape nobody tested for, which is a strictly worse
# outcome than the one this hook exists to prevent: an executor going twenty calls without
# touching its card is a wasted run to replace; every agent everywhere refusing every call
# is the whole machine down until a human notices and edits settings.json by hand. A missed
# nudge costs one run; a frozen machine costs every run. This asymmetry is deliberate and
# was decided directly by the executor building HRN-49 rather than by the coordinator, per
# "Decide technical details yourself."
#
# State: one small JSON file per agent_id under $TMPDIR/claude-card-touch-gate/, holding
# the card path this agent has been seen touching and its running call count since the
# last touch. Never cleaned up automatically — a stray handful of small JSON files per
# executor run is an accepted, stated cost, not an oversight. agent_id values are treated
# as unique on their own, with no session_id folded in, matching how HRN-46 already found
# them used (a fresh, effectively-random id per spawned subagent); a same-day collision
# between two entirely unrelated agents is possible in principle and would only ever cause
# one run's own count to be read by another, which is a minor mixed count, never a refusal
# of a call that should have been allowed outright or an allowance of one that should not.
#
# Bypass: CLAUDE_GATE_BYPASS=1 (shared with the other hooks in this directory).
# Threshold: 20 tool calls since the card was last touched. Set against this project's own
# archive, read by bin/spend-stats over every card carrying a measured spend line: the
# middle card spends about 15.2 tool calls per checkpoint, a quarter of cards sit below 12
# and a quarter above 19. Twenty calls with no card edit at all is therefore already more
# than a whole checkpoint's worth of work with nothing recorded, on the ordinary pace of
# this project — see HRN-49's own "Reasons to exist" and its Comments section for the full
# figure.

# The fail-open promise made above lives INSIDE the Python program below, and therefore
# cannot cover the one case where that program never starts at all. A missing helper module
# or a syntax error makes Python exit before a single line of it runs: it prints a traceback
# and no decision, and a PreToolUse hook that emits no decision is read as a REFUSAL rather
# than as an allowance. The safety posture inverts in exactly the situation nobody tests for,
# and on 2026-08-07 it did: while one executor was rewriting this very file in place, the
# helper it had begun importing did not yet exist on disk, and for that window every tool
# call by every agent on this machine was refused. Two executors were frozen outright, and
# the coordinator froze itself the same way an hour later while repairing it.
#
# So the Python program's output is captured to a file rather than written straight to
# standard output, and anything that is not a real decision — a traceback, an empty file, a
# program that never ran — is replaced here, in the shell, by an explicit allowance. Its
# standard error is kept, in the same directory as the per-agent state, so that a hook which
# has silently stopped gating can still be diagnosed rather than merely noticed.
#
# This is also why this file must never be edited in place while any agent is running: a
# shell reads a script incrementally, so a half-written file is a half-written program. A new
# version is built elsewhere, tested there, and moved onto this path in one atomic step.

THRESHOLD=20

ALLOW_DECISION='{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

STDIN_DATA="$(cat)"
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

GATE_TMP="${CARD_TOUCH_GATE_STATE_DIR:-${TMPDIR:-/tmp}/claude-card-touch-gate}"
mkdir -p "$GATE_TMP" 2>/dev/null
DECISION_FILE="$GATE_TMP/.decision.$$"

python3 - "$STDIN_DATA" "$HOOKS_DIR" > "$DECISION_FILE" 2>>"$GATE_TMP/.stderr.log" <<'PYEOF'
import sys
import os
import re
import json
import tempfile

stdin_data = sys.argv[1]
hooks_dir  = sys.argv[2]

sys.path.insert(0, hooks_dir)
import brief_reader  # HRN-109: the brief-path reading shared with plan-gate.sh

THRESHOLD = 20

# The hard ceiling on a whole run, counted across every tool call the agent makes and never
# reset by anything. THRESHOLD above limits the gap between two card edits, which a run that
# ticks its card often never trips however long it goes on; this one limits the run itself.
# It exists because cost here is dominated by re-reading: every call re-reads the whole
# accumulated conversation, so a run's price grows faster than its length, and nothing in
# this project measured or capped that until now. 80 calls is set against bin/spend-stats:
# the middle card spends about 15.2 calls per checkpoint, so 80 is roughly five checkpoints,
# which is a whole phase. Past it the run is refused everything EXCEPT editing its own card,
# so it can always record its Working state and stop; the remaining work is a fresh
# executor's, exactly as a declared phase boundary already is.
HARD_CAP = 80

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

def allow_and_exit():
    print(ALLOW_JSON)
    sys.exit(0)

DENY_TEMPLATE = (
    "Blocked by card-touch-gate: this run has made more than {threshold} tool calls "
    "without editing its own card, {card}. Before any further call, edit that exact "
    "file: tick the checkbox of the checkpoint you just finished (change '- [ ]' to "
    "'- [x]') and add a short sentence saying what you actually did, and overwrite the "
    "card's own '## Working state' section — never append to it — with what this run "
    "has established so far, which checks have already passed, what turned out to be a "
    "dead end, and where to look next. A checkpoint is not finished until both its box "
    "and that section are current. The threshold is {threshold} tool calls, set against "
    "this project's own archive (bin/spend-stats): the middle card spends about 15.2 "
    "tool calls per checkpoint, so {threshold} calls with no card edit at all is already "
    "more than a whole checkpoint's worth of unrecorded work. Any Edit or Write to that "
    "file resets this count to zero."
)

HARD_STOP_TEMPLATE = (
    "Blocked by card-touch-gate: this run has made {total} tool calls, past the hard "
    "ceiling of {cap} for a single run. Stop here — do not continue, do not start the "
    "next checkpoint, and do not try to finish what you were in the middle of. Editing "
    "your own card, {card}, is still allowed and is the only thing that is: tick the box "
    "of every checkpoint you actually finished, and overwrite that card's '## Working "
    "state' section with what this run established, which checks have passed, what turned "
    "out to be a dead end, and exactly where the next executor should pick up. Then reply "
    "saying you have reached the run ceiling, naming the last finished checkpoint. The "
    "rest of this card is a fresh executor's work, not a continuation of yours, because "
    "every further call re-reads this entire conversation and that is what the cost of "
    "this project actually is."
)

NO_CARD_IDENTIFIED = (
    "its own task card (not yet identified by this hook — the brief this agent was "
    "spawned with, recovered from the coordinator's own transcript, is what lets this "
    "hook learn which file is its card; see establish_card() in this script)"
)


def establish_card(transcript_path, agent_id):
    """The run's own card — the one task-card-shaped path named in the brief this agent_id
    was actually spawned with (HRN-109), read through brief_reader.find_spawn_prompt() and
    reduced to its canonical form. Returns None, never raises, when the brief cannot be
    recovered at all: no transcript record yet for this agent_id (the transcript is written
    asynchronously and may lag), a record naming no .md path, or one naming only a legacy
    plan (plans/*.md, ai/plans/*.md) rather than a task card. None is exactly the signal
    that makes this hook allow the call rather than gate it — see "Fail open when the
    brief can't be read" in this script's own header."""
    spawn = brief_reader.find_spawn_prompt(transcript_path, agent_id)
    if not spawn:
        return None
    for token in brief_reader.brief_tokens(spawn):
        m = brief_reader.CARD_PATH_RE.search(token)
        if m:
            return m.group(1)
    return None


def touches_card(tool_name, tool_input, card_token):
    """True when this call is an Edit or Write whose file_path names the same card this
    agent has been tracked against, compared on the identifying part of each path alone, so
    that the shared checkout's copy and an executor's own copy of one card count as the
    same card."""
    if tool_name not in ("Edit", "Write"):
        return False
    fp = tool_input.get("file_path")
    if not isinstance(fp, str) or not fp:
        return False
    return brief_reader.canonical_card(fp) == brief_reader.canonical_card(card_token)


try:
    if not stdin_data.strip():
        allow_and_exit()
    data = json.loads(stdin_data)
except Exception:
    # Fail OPEN here, deliberately unlike the other hooks in this directory — see this
    # script's own header comment for why a global, every-tool, every-project hook cannot
    # afford to fail closed the way a single-file guard can.
    allow_and_exit()

if os.environ.get("CLAUDE_GATE_BYPASS") == "1":
    allow_and_exit()

agent_id = data.get("agent_id")
if not agent_id:
    # No agent_id at all means this call is the coordinator's own (HRN-46's own finding):
    # the coordinator is never counted, never gated, by design (HRN-49 acceptance
    # criterion 4).
    allow_and_exit()

tool_name = data.get("tool_name") or ""
tool_input = data.get("tool_input") or {}
transcript_path = data.get("transcript_path")

try:
    # CARD_TOUCH_GATE_STATE_DIR overrides where per-agent state is kept — used by this
    # script's own test suite so a run of the tests never reads or writes the same state
    # a real, concurrently-running executor is using.
    state_dir = os.environ.get("CARD_TOUCH_GATE_STATE_DIR") or \
        os.path.join(tempfile.gettempdir(), "claude-card-touch-gate")
    os.makedirs(state_dir, exist_ok=True)
    # agent_id is already a filesystem-safe token in every instance HRN-46 observed (a
    # bare hex string); strip anything that is not, defensively, rather than trust that.
    safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', agent_id)
    state_path = os.path.join(state_dir, safe_id + ".json")

    state = {"card": None, "count": 0}
    if os.path.isfile(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception:
            pass  # a corrupt state file is treated as a fresh start, not an error to deny on

    if not state.get("card"):
        # Identified through brief_reader alone — the brief this agent_id was actually
        # spawned with, recovered from the coordinator's transcript — and through nothing
        # else: never from this call's own file_path, command, prompt or description,
        # which is precisely the "first card-shaped path it happens to see" guess HRN-109
        # replaces. Once set here, this branch never runs again for this agent_id: a card
        # established for a run is never replaced, which is what stops the tracked card
        # drifting to whichever card the run happens to touch last (repaired 2026-08-07,
        # commit cfbd25d, kept unchanged by this restructuring).
        card = establish_card(transcript_path, agent_id)
        if card:
            state["card"] = card

    touched = bool(state.get("card")) and touches_card(tool_name, tool_input, state["card"])

    state["total"] = state.get("total", 0) + 1

    if touched:
        state["count"] = 0
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f)
        allow_and_exit()

    if state["total"] > HARD_CAP and state.get("card"):
        # Never refuses a card edit: the touched branch above has already returned for one,
        # so a run past the ceiling can always record its state and stop, which is the whole
        # point of stopping it here rather than letting it run to exhaustion.
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f)
        print(deny_json(HARD_STOP_TEMPLATE.format(
            total=state["total"], cap=HARD_CAP, card=state["card"])))
        sys.exit(0)

    new_count = state.get("count", 0) + 1
    if new_count > THRESHOLD and state.get("card"):
        # Only ever refuse an agent this hook has actually seen working on a task card.
        # An agent that has never mentioned a card-shaped path is, as far as this hook can
        # tell, not one of this project's executors at all — it may be an agent in another
        # repository entirely, since this hook is registered globally against every tool
        # call on the machine. Refusing it would tell it to edit a card it does not have
        # and cannot produce, which is not a nudge but a permanent freeze with no way out.
        # The coordinator (Alex's, 2026-08-07) made this the one condition on the refusal.
        print(deny_json(DENY_TEMPLATE.format(threshold=THRESHOLD, card=state["card"])))
        sys.exit(0)

    state["count"] = new_count
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
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
