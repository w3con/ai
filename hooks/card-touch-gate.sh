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
# What resets the count to zero: an Edit or Write tool call whose file_path is the one
#   task-card-shaped path (ai/timeline/tasks/*.md or ai/harness/tasks/*.md) this specific
#   agent_id has been seen touching. The FIRST time a given agent_id's calls mention such
#   a path at all — in an Edit/Write's file_path, a Read's file_path, or a Bash command's
#   text — that path is remembered as "this agent's own card" for the rest of its run; in
#   ordinary use this is the very first call an executor makes, because every executor's
#   own standing instructions require it to read its brief before doing anything else.
# What is NOT gated: the coordinator's own calls (no agent_id present), and a card edited
#   through Bash (a heredoc, sed, or similar) rather than through the Edit or Write tool —
#   a stated, known gap rather than a hidden one: every executor is separately instructed
#   to tick a checkpoint through the Edit tool, so a Bash-based card edit is not the
#   realistic path this project's own executors take, unlike the settings.json case
#   settings-write-guard.sh exists to close.
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

THRESHOLD=20

STDIN_DATA="$(cat)"

exec python3 - "$STDIN_DATA" <<'PYEOF'
import sys
import os
import re
import json
import tempfile

stdin_data = sys.argv[1]

THRESHOLD = 20

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

NO_CARD_IDENTIFIED = (
    "its own task card (not yet identified by this hook — its very first tool call "
    "should have been reading the exact brief path it was handed, which is what lets "
    "this hook learn which file is its card)"
)

# A task-card-shaped path: ai/timeline/tasks/<name>.md or ai/harness/tasks/<name>.md,
# with or without a leading directory portion, absolute or relative alike. Deliberately
# permissive about what comes before it, exactly as plan-gate.sh's own MD_PATH_RE is,
# because the interesting part is the fixed suffix a real card path always carries.
CARD_PATH_RE = re.compile(
    r'([~\w./\\-]*ai/(?:timeline|harness)/tasks/[\w.-]+\.md)'
)


def find_card_token(tool_input):
    """The first task-card-shaped path mentioned anywhere in this call's tool_input, or
    None. Checked across every field a path or a command could plausibly appear in,
    because different tools name their target differently (file_path for Edit/Write/Read,
    command for Bash, prompt/description for Task/Agent)."""
    for key in ("file_path", "command", "prompt", "description", "notebook_path"):
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            m = CARD_PATH_RE.search(v)
            if m:
                return m.group(1)
    return None


def touches_card(tool_name, tool_input, card_token):
    """True when this call is an Edit or Write whose file_path names the same card this
    agent has been tracked against — matched by suffix in either direction, since one side
    may be absolute and the other a shorter relative fragment picked up from a prompt."""
    if tool_name not in ("Edit", "Write"):
        return False
    fp = tool_input.get("file_path")
    if not isinstance(fp, str) or not fp:
        return False
    return fp.endswith(card_token) or card_token.endswith(fp)


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
        token = find_card_token(tool_input)
        if token:
            state["card"] = token

    touched = bool(state.get("card")) and touches_card(tool_name, tool_input, state["card"])
    if not touched and tool_name in ("Edit", "Write"):
        # An Edit/Write straight to a card-shaped path, before this agent's card was ever
        # otherwise identified, both establishes AND touches it in the same call — this is
        # the case of an executor whose very first tracked action is ticking its own box.
        fp = tool_input.get("file_path")
        if isinstance(fp, str):
            m = CARD_PATH_RE.search(fp)
            if m:
                state["card"] = m.group(1)
                touched = True

    if touched:
        state["count"] = 0
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f)
        allow_and_exit()

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
