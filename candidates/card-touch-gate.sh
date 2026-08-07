#!/usr/bin/env bash
# card-touch-gate.sh — PreToolUse hook: watch an executor's tool calls and refuse the next
# one when either of TWO INDEPENDENT rules says so.
#
# Built for ai/harness/tasks/HRN-49_an-executor-that-has-not-touched-its-card-in-twenty-
# tool-calls-is-refused-until-it-does.md (the TOUCH rule, below) and extended by
# ai/harness/tasks/HRN-47_an-executor-is-refused-every-further-tool-call-once-it-reaches-
# the-ceiling-written-on-its-card.md (the PACE rule, below), both in the app repository
# (Dev/app). Read those cards for the full "why"; this header states only what the script
# does and the safety decisions specific to running it live in Alex's global settings.json.
#
# THE TWO RULES, kept deliberately separate rather than folded into one comparison, because
# they measure two different things and can each fire while the other does not:
#
#   THE TOUCH RULE (HRN-49, unchanged by this extension): refuses a call once this run has
#   made more than TOUCH_THRESHOLD (20) tool calls WITHOUT editing its own card — a call
#   that DOES edit the card resets this rule's own count to zero. It knows nothing about
#   checkpoints or how much of the card is done; it only asks "how long since you last
#   wrote anything down."
#
#   THE PACE RULE (HRN-47, new): refuses (at the RELAY tier) or refuses outright (at the
#   REFUSE tier) once this run's TOTAL tool-call count — which a card touch does NOT reset,
#   unlike the touch rule's own count — exceeds a budget computed from how much of the card
#   is actually finished: rate * (ticked checkpoint boxes + 1). It knows nothing about how
#   recently the card was last touched; it only asks "how many calls has this run made
#   relative to how much work it has recorded." Two rates apply: RELAY (20 calls per
#   checkpoint by default) tells the run to finish its current checkpoint, write its
#   working state, and stop — a relay, not a failure, because a fresh executor reading that
#   section pays nothing to continue. REFUSE (28 by default) is a harder ceiling: a run
#   still going that far above the ordinary pace is refused outright. A card may override
#   the RELAY rate with its own `rate:` frontmatter field (a plain number, on a line of its
#   own inside the --- ... --- block at the top of the file); the REFUSE rate then scales
#   with it, keeping the same 28/20 = 1.4 ratio the archive settled on. Both PACE tiers
#   still let an Edit or Write to the tracked card itself through, for the same reason the
#   touch rule's own reset exists: a run that cannot write down where it stopped cannot be
#   resumed from anything but scratch.
#
#   A THIRD, unrelated mechanism (also HRN-47, AC7) bounds a read-only search agent's own
#   calls — identified by agent_type being one of the read-only types
#   hooks/plan-gate.sh already allowlists (Explore, Plan, trace-audit) — at a flat ceiling,
#   independent of any card, because such an agent is never handed a task card to begin
#   with. This is not a third card-relative rule; it is a separate, much simpler cap that
#   exists only so a delegated search is bounded too, the same way the executor that
#   spawned it already is.
#
#   Both the touch rule and the pace rule are evaluated on every non-card-touching call an
#   agent with an established card makes; either one denying is enough to refuse the call.
#   The touch rule is checked first and, on the exact same terms as before this extension,
#   denies without persisting its own count — an intentional quirk carried over unchanged so
#   this extension truly never weakens what HRN-49 already proved. The pace rule's own
#   bookkeeping (its total-call counter) always advances and is always saved, on every call,
#   whether the touch rule denies first or not, because it counts every attempt this run
#   makes, not only the ones the touch rule happens to let through.
#
# What IS gated: every tool call made by a subagent (an executor) — the hook fires on any
#   tool name, because an executor's own working pace is measured in tool calls of every
#   kind, not only Edit/Write. A call is identified as the coordinator's own, and left
#   completely uncounted by every rule above, by the ABSENCE of an "agent_id" key in the
#   hook payload — the same discriminator HRN-46 measured and confirmed: present and
#   non-empty means a subagent made the call, absent means the coordinator did.
# What resets the TOUCH rule's own count to zero (and nothing else — see above): an Edit or
#   Write tool call whose file_path names the run's own card — the ONE task-card-shaped path
#   (ai/timeline/tasks/*.md or ai/harness/tasks/*.md) named in the brief this agent_id was
#   actually spawned with, read through hooks/brief_reader.py (HRN-109), never guessed from
#   any tool call the agent makes on its own. That brief is recovered from the coordinator's
#   own durable session transcript (transcript_path in this hook's own payload), which
#   records every Task/Agent spawn as a toolUseResult object carrying the spawned agent's
#   agentId, prompt and description — the very same prompt hooks/plan-gate.sh already read
#   at spawn time, run through the very same brief_tokens()/canonical_card() pair, so the
#   two gates cannot disagree about which file is a run's brief. This is established once,
#   on whichever call is the first one this hook processes for a given agent_id, and never
#   re-derived or replaced afterwards, so a run that reads, greps or edits some unrelated
#   card along the way is never mistaken for owning that card, and is never asked to edit
#   it.
# What is NOT gated: the coordinator's own calls (no agent_id present), any run whose brief
#   cannot be recovered at all (no readable transcript record for its agent_id, or a brief
#   that names no task-card-shaped path — see "Fail open when the brief can't be read"
#   below), and a card edited through Bash (a heredoc, sed, or similar) rather than through
#   the Edit or Write tool — a stated, known gap rather than a hidden one: every executor is
#   separately instructed to tick a checkpoint through the Edit tool, so a Bash-based card
#   edit is not the realistic path this project's own executors take, unlike the
#   settings.json case settings-write-guard.sh exists to close. The PACE rule additionally
#   does not gate a run whose card CAN be established but whose on-disk file cannot be
#   opened to read its ticked-box count (moved, deleted, or a path the resolver cannot
#   reach) — that run is left to the touch rule alone, on the same fail-open reasoning.
#
# Fail open when the brief can't be read: an agent whose card this hook could never
# recover — the transcript record for its agent_id is missing, unreadable, or names no
# task-card-shaped path at all — is allowed past both the touch rule and the pace rule
# indefinitely, the same way an agent that has never been identified as one of this
# project's executors always has been. Refusing a run this hook cannot name a card for would
# tell it to edit a card it does not have and cannot produce, which is a permanent freeze
# with no way out, not a nudge — the one thing this hook's own header already says it must
# never do.
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
# THREE fields now instead of two — {"card": ..., "count": ..., "total_count": ...} — all
# three in the one file, so the touch rule and the pace rule share the same per-agent record
# rather than each keeping a counter of its own on disk. "card" and "count" are exactly
# HRN-49's original fields, read and written on exactly the same terms as before. "total_count"
# is new: a plain running tally of every non-card-touching call this agent_id has made,
# which a card touch never resets, unlike "count". A read-only search agent (the third,
# card-independent mechanism above) uses a fourth field, "search_count", in the same file,
# so that if an agent_id were ever somehow seen under both roles the two tallies still never
# collide. Never cleaned up automatically — a stray handful of small JSON files per executor
# run is an accepted, stated cost, not an oversight. agent_id values are treated as unique
# on their own, with no session_id folded in, matching how HRN-46 already found them used (a
# fresh, effectively-random id per spawned subagent); a same-day collision between two
# entirely unrelated agents is possible in principle and would only ever cause one run's own
# counts to be read by another, which is a minor mixed count, never a refusal of a call that
# should have been allowed outright or an allowance of one that should not.
#
# Bypass: CLAUDE_GATE_BYPASS=1 (shared with the other hooks in this directory).
# TOUCH_THRESHOLD: 20 tool calls since the card was last touched — unchanged from HRN-49.
# PACE rates: RELAY 20, REFUSE 28 calls per checkpoint, both set against this project's own
# archive (bin/spend-stats --ceiling): the middle card spends about 15.0-15.2 tool calls per
# checkpoint, a quarter of cards sit below ~11-12 and a quarter above ~19; RELAY (20) sits
# just above that top-quartile boundary and REFUSE (28) is reached by only a small extreme
# tail of the archive. Full figures in HRN-47's own card, checkpoint HRN-47.3.

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
# version is built elsewhere, tested there, and moved onto this path in one atomic step
# (bin/hook-install).

ALLOW_DECISION='{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

STDIN_DATA="$(cat)"
# HRN-121: a hook's shared helper modules (brief_reader.py, importable only from the real
# hooks/ directory) are found at one fixed location, HOOK_INSTALL_HOOKS_DIR — the exact env
# var bin/hook-install itself already reads for "the real hooks directory", defaulting to
# the same literal path — rather than derived from where THIS script file happens to sit.
# That derivation ("beside itself", via BASH_SOURCE) is correct once installed, because an
# installed hook and brief_reader.py sit in the same directory, but wrong for a candidate
# under test, which sits in candidates/ instead. HRN-121 replaces the per-candidate
# try/import/fallback workaround this file used to carry (HRN-47.8) with this one fixed
# arrangement, shared verbatim with hooks/plan-gate.sh, so a hook finds its helpers the same
# way whether it is running installed or as a candidate.
HOOKS_DIR="${HOOK_INSTALL_HOOKS_DIR:-/Users/laptop/Dev/ai/hooks}"

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
try:
    import brief_reader  # HRN-109: the brief-path reading shared with plan-gate.sh
except ImportError as exc:
    # HRN-121, AC2: a helper that cannot be loaded is reported plainly rather than being
    # absorbed into a silent allow. The decision below is still "allow" — this hook fails
    # open by design (see the file header) and that posture is not what this card changes —
    # but the reason is no longer empty the way the shell's own last-resort ALLOW_DECISION
    # fallback would leave it: it names the helper, the directory it was sought in, and the
    # underlying error, so a test run that expected a refusal and got this instead shows the
    # real cause in the very same line rather than looking like an unrelated logic bug.
    print(f"card-touch-gate: HELPER LOAD FAILURE — could not import 'brief_reader' from "
          f"'{hooks_dir}': {exc}. Falling open (allow) rather than blocking every call.",
          file=sys.stderr)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": (
                "card-touch-gate: internal error — could not load its shared helper "
                f"module 'brief_reader' from '{hooks_dir}' ({exc}); falling open (allow) "
                "rather than blocking every call on this machine. This decision reflects "
                "no TOUCH or PACE rule and must not be trusted as one."
            ),
        }
    }))
    sys.exit(0)

# --- the TOUCH rule (HRN-49, unchanged) ---
TOUCH_THRESHOLD = 20

# --- the PACE rule (HRN-47, new) ---
DEFAULT_RELAY_RATE = 20.0
DEFAULT_REFUSE_RATE = 28.0
REFUSE_RATIO = DEFAULT_REFUSE_RATE / DEFAULT_RELAY_RATE  # 1.4, preserved when a card overrides the relay rate

# --- the SEARCH-AGENT mechanism (HRN-47 AC7, card-independent) ---
# The same three read-only agent types hooks/plan-gate.sh already allowlists, because those
# are this project's own definition of "reads and reports, never writes" — kept in sync with
# that file's own ALLOWLISTED_SUBTYPES by hand, since the two hooks share no importable
# constant for it.
SEARCH_AGENT_TYPES = {"Explore", "Plan", "trace-audit"}
SEARCH_AGENT_CEILING = int(DEFAULT_REFUSE_RATE)  # 28: one checkpoint's worth at the REFUSE rate

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

def allow_and_exit():
    print(ALLOW_JSON)
    sys.exit(0)

def fmt_num(x):
    """20.0 -> '20', 5.5 -> '5.5' — for messages, not for comparisons."""
    xf = float(x)
    if xf == int(xf):
        return str(int(xf))
    return ("%.2f" % xf).rstrip('0').rstrip('.')

TOUCH_RULE_TEMPLATE = (
    "Blocked by card-touch-gate's TOUCH rule: this run has made more than {threshold} tool "
    "calls without editing its own card, {card}. Before any further call, edit that exact "
    "file: tick the checkbox of the checkpoint you just finished (change '- [ ]' to "
    "'- [x]') and add a short sentence saying what you actually did, and overwrite the "
    "card's own '## Working state' section — never append to it — with what this run "
    "has established so far, which checks have already passed, what turned out to be a "
    "dead end, and where to look next. A checkpoint is not finished until both its box "
    "and that section are current. The threshold is {threshold} tool calls, set against "
    "this project's own archive (bin/spend-stats): the middle card spends about 15.2 "
    "tool calls per checkpoint, so {threshold} calls with no card edit at all is already "
    "more than a whole checkpoint's worth of unrecorded work. Any Edit or Write to that "
    "file resets this rule's own count to zero. (This is the TOUCH rule — it does not "
    "care how much of the card is done, only how long since you last wrote anything down. "
    "A separate PACE rule on the same card judges that instead.)"
)

PACE_RELAY_TEMPLATE = (
    "Blocked by card-touch-gate's PACE rule (relay tier): this run has made {count} tool "
    "calls in total against a relay budget of {budget} on {card} — {rate} calls per "
    "checkpoint x ({ticked}+1) checkpoint boxes ticked so far. This is a relay, not a "
    "failure: finish the checkpoint you are on, tick its box (change '- [ ]' to '- [x]') "
    "and add a short sentence saying what you actually did, and overwrite the card's own "
    "'## Working state' section — never append to it — with what this run has "
    "established so far. Then stop: a fresh executor will read that section and continue "
    "from there with an empty context, which is exactly what resets this rule's own pace. "
    "Stopping here is the expected outcome, not a fault. Any Edit or Write to {card} "
    "itself is allowed through this message. (This is the PACE rule's relay tier — it "
    "does not care how recently you last touched the card, only how many calls you have "
    "made relative to how much of the card is actually finished. A separate TOUCH rule on "
    "the same card judges that instead.)"
)

PACE_REFUSE_TEMPLATE = (
    "Blocked by card-touch-gate's PACE rule (refuse tier): this run has made {count} tool "
    "calls in total against a refuse ceiling of {budget} on {card} — {rate} calls per "
    "checkpoint x ({ticked}+1) checkpoint boxes ticked so far — well past its own relay "
    "point. Every further call is refused outright, because a run this far above the "
    "ordinary pace is doing something nobody has noticed. The only calls still allowed "
    "are an Edit or Write to {card} itself: tick the checkpoint you are on and overwrite "
    "'## Working state' with where this run actually stands, then stop. (This is the "
    "PACE rule's refuse tier, distinct from the TOUCH rule on the same card, which judges "
    "only how long since your last card edit.)"
)

SEARCH_AGENT_TEMPLATE = (
    "Blocked by card-touch-gate's SEARCH-AGENT rule: this read-only agent "
    "(agent_type={agent_type}) has made {count} tool calls against its own bounded "
    "budget of {ceiling}, tracked separately from whichever executor spawned it and "
    "unrelated to either the TOUCH rule or the PACE rule, which apply only to an agent "
    "with its own task card. A delegated search is meant to be cheap and bounded; "
    "stopping here and reporting back with whatever has been found so far is the "
    "expected outcome, not a fault."
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


def resolve_card_path(card_token):
    """The on-disk file for a card token, reusing brief_reader.resolve() exactly the way
    hooks/plan-gate.sh already turns a relative brief path into a real file — an absolute
    token is tried as itself, a relative one under $CLAUDE_PROJECT_DIR (then the process's
    own cwd), including the BRIEF_DIRS fallback for a bare filename. Returns None, never
    raises, when nothing on disk matches; that is the PACE rule's own fail-open signal,
    independent of whatever the TOUCH rule decides."""
    roots = []
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        roots.append(proj)
    cwd = os.getcwd()
    if cwd not in roots:
        roots.append(cwd)
    try:
        for path in brief_reader.resolve(card_token, roots):
            if os.path.isfile(path):
                return path
    except Exception:
        return None
    return None


def read_ticked_boxes(path):
    """How many '- [x]' (or '- [X]') checkpoint lines the card at `path` carries right now,
    read live off disk on every call rather than cached, so a box ticked by this run's own
    previous call already widens the very next call's PACE budget. Whole-file scan, matched
    against HRN-47.1's own feasibility measurement (ground truth via `grep -c`, confirmed
    exact). Returns None, never raises, when the file cannot be opened."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    ticked = 0
    for line in text.splitlines():
        m = re.match(r'\s*-\s*\[([ xX])\]', line)
        if m and m.group(1) in ("x", "X"):
            ticked += 1
    return ticked


def read_card_rate(path):
    """The card's own optional `rate:` frontmatter field — a plain number on a line of its
    own inside the leading --- ... --- block — or None when the card carries none, in which
    case the caller falls back to DEFAULT_RELAY_RATE. This field is not yet part of the
    task-card template (that is HRN-47.9, a later checkpoint); reading it here is forward
    compatible with a template that does not carry it at all. Returns None, never raises, on
    any read or parse problem."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    frontmatter = parts[1]
    m = re.search(r'^rate:\s*([0-9]+(?:\.[0-9]+)?)\s*$', frontmatter, re.MULTILINE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


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
    # the coordinator is never counted, never gated, by design — untouched by every rule
    # in this file, old or new.
    allow_and_exit()

tool_name = data.get("tool_name") or ""
tool_input = data.get("tool_input") or {}
transcript_path = data.get("transcript_path")
agent_type = data.get("agent_type") or ""

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

    state = {"card": None, "count": 0, "total_count": 0, "search_count": 0}
    if os.path.isfile(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception:
            pass  # a corrupt state file is treated as a fresh start, not an error to deny on

    def save_state():
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f)

    # --- the SEARCH-AGENT mechanism: a flat, card-independent ceiling for a read-only
    # agent, checked before anything about cards at all, and never mixed into either the
    # TOUCH rule's or the PACE rule's own fields. ---
    if agent_type in SEARCH_AGENT_TYPES:
        new_search_count = state.get("search_count", 0) + 1
        state["search_count"] = new_search_count
        save_state()
        if new_search_count > SEARCH_AGENT_CEILING:
            print(deny_json(SEARCH_AGENT_TEMPLATE.format(
                agent_type=agent_type, count=new_search_count,
                ceiling=SEARCH_AGENT_CEILING)))
            sys.exit(0)
        allow_and_exit()

    if not state.get("card"):
        # Identified through brief_reader alone — the brief this agent_id was actually
        # spawned with, recovered from the coordinator's transcript — and through nothing
        # else: never from this call's own file_path, command, prompt or description,
        # which is precisely the "first card-shaped path it happens to see" guess HRN-109
        # replaces. Once set here, this branch never runs again for this agent_id: a card
        # established for a run is never replaced.
        card = establish_card(transcript_path, agent_id)
        if card:
            state["card"] = card

    touched = bool(state.get("card")) and touches_card(tool_name, tool_input, state["card"])

    if touched:
        # Resets the TOUCH rule's own count (unchanged from HRN-49) and advances the PACE
        # rule's own total — a card edit is still a call the PACE rule counts, it is just
        # never one either rule denies.
        state["count"] = 0
        state["total_count"] = state.get("total_count", 0) + 1
        save_state()
        allow_and_exit()

    # --- neither rule fires for a call whose card was never established at all: fail open,
    # exactly as HRN-49 always has. ---
    if not state.get("card"):
        allow_and_exit()

    # --- Rule 1: the TOUCH rule (HRN-49, unchanged in every particular, including the
    # quirk that a denying call does not persist its own incremented count) ---
    touch_new_count = state.get("count", 0) + 1

    # The PACE rule's own tally advances and is saved on every non-touching call this run
    # makes, regardless of what either rule decides below — it counts every attempt, not
    # only the ones the TOUCH rule happens to let through.
    total_new_count = state.get("total_count", 0) + 1
    state["total_count"] = total_new_count
    save_state()

    if touch_new_count > TOUCH_THRESHOLD:
        # Only ever refuse an agent this hook has actually seen working on a task card —
        # state.get("card") is already known truthy at this point (checked just above).
        print(deny_json(TOUCH_RULE_TEMPLATE.format(threshold=TOUCH_THRESHOLD, card=state["card"])))
        sys.exit(0)

    state["count"] = touch_new_count
    save_state()

    # --- Rule 2: the PACE rule (HRN-47, new) — only evaluated once the TOUCH rule has
    # already allowed the call. Fails open, independently of the TOUCH rule, whenever the
    # card's on-disk file cannot be found or read. ---
    card_path = resolve_card_path(state["card"])
    if card_path is not None:
        ticked = read_ticked_boxes(card_path)
        if ticked is not None:
            relay_rate = read_card_rate(card_path)
            if relay_rate is None:
                relay_rate = DEFAULT_RELAY_RATE
            refuse_rate = relay_rate * REFUSE_RATIO
            budget_relay = relay_rate * (ticked + 1)
            budget_refuse = refuse_rate * (ticked + 1)

            if total_new_count > budget_refuse:
                print(deny_json(PACE_REFUSE_TEMPLATE.format(
                    count=total_new_count, budget=fmt_num(budget_refuse),
                    card=state["card"], rate=fmt_num(refuse_rate), ticked=ticked)))
                sys.exit(0)
            if total_new_count > budget_relay:
                print(deny_json(PACE_RELAY_TEMPLATE.format(
                    count=total_new_count, budget=fmt_num(budget_relay),
                    card=state["card"], rate=fmt_num(relay_rate), ticked=ticked)))
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
