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
#   A FOURTH rule (HRN-123): the BRAKE rule refuses the Nth Edit or Write of one and the
#   same path within a single run — the single largest measured waste the archive showed
#   (ai/harness/spend-audit_2026-08-08.md §4: one file edited 34 separate times in one run,
#   each edit re-reading the whole conversation, when one rewrite would have done the same
#   work in one call). It tracks a per-path edit count in the same per-agent state file,
#   under its own field, and is evaluated on every Edit/Write call that does not touch the
#   run's own card — a card touch already returns before this rule is reached, so the
#   card itself is structurally exempt, never a special case inside the rule. On its own
#   terms the rule needs no established card to make sense — it is about one path being
#   edited too many times within one run, not about a run's own pace relative to its
#   checkpoints — but since HRN-139 it is reached only once a card HAS been established for
#   the run, exactly like the TOUCH and PACE rules: a run this hook could never name a card
#   for is not braked at all, on the same "cannot ask a run to edit a card it does not
#   have" reasoning that already governs the TOUCH and PACE rules (see "Fail open when the
#   brief can't be read" below). Before HRN-139 the no-card fail-open check sat only after
#   this rule, so an unidentified run's own repeated edits of any path — including its own
#   card, which is never recognised as "its own card" without an established state["card"]
#   to compare against — were counted and could still be denied outright. N (BRAKE_THRESHOLD,
#   9) was set from the measured per-path
#   edit-count distribution across archived EXECUTOR-run transcripts only, using the same
#   executor/coordinator discriminator bin/agent-spend already uses (HRN-123.1): p50=3,
#   p75=5, p90=9, p95=13, p99=26, p100=34 — a threshold at the p90 point catches only the
#   wasteful tail (about one run in ten) while leaving the other nine untouched, and it
#   would have refused the archive's own 34-, 31- and 28-edit cases well before they ran
#   their course.
#
#   HRN-148 (2026-08-09) corrected one fault in the BRAKE rule above: an Edit changes one
#   string inside a file, a Write replaces the file whole, and only the first is the
#   pathology the rule was measured against — but before this card both were refused
#   identically once the threshold was crossed, which meant the rule's own refusal
#   message ("rewrite the file in a single call") named a remedy that the very next call,
#   being that rewrite, would itself refuse. Measured first (HRN-148.3, over every
#   transcript on disk): of the 247 (transcript, path) pairs that reach the threshold at
#   all, 3648 of the 3727 calls within them (97.9%) are Edit and 79 (2.1%) are Write, and
#   every one of the 247 pairs is Edit-dominated — confirming that the archive's long
#   per-file tails are made of one-string patches, not whole-file rewrites, so exempting
#   one Write targets the actually-rare case rather than the pathology itself. Now: an
#   Edit is still refused unconditionally from the threshold onward, exactly as before
#   this card; a Write is let through exactly once past the threshold — tracked in the
#   same per-agent state file under a new "path_rewrites" field, {path: true} once that
#   path's own one exemption has been used — and a second or later Write of the same path
#   past the threshold is refused (BRAKE_REWRITE_USED_TEMPLATE), because a run that has
#   not consolidated after being given the one rewrite it asked for has not understood,
#   and the honest answer to that is to stop, not to be given another. A Write still adds
#   to the shared per-path count exactly like an Edit does, so the number any refusal or
#   warning reports stays the run's honest total of everything it has done to that path.
#   From the seventh call against a path onward, an allowed call now also carries a
#   warning (BRAKE_WARNING_TEMPLATE) through the permissionDecisionReason field an
#   "allow" decision can already carry — the same shape the HELPER LOAD FAILURE case
#   elsewhere in this file already uses — so a run nearing the ceiling can see it coming
#   and consolidate early, while a rewrite is still cheap and still available; whether
#   that reason is ever surfaced to the run reading it is not something this hook can
#   prove, only that its own JSON output carries it.
#
#   A correction to the PACE rule's own arithmetic (HRN-123 phase C, not a sixth rule): the
#   relay and refuse budgets now each carry a fixed STARTING ALLOWANCE on top of
#   rate * (ticked + 1), granted once per run rather than once per checkpoint, because the
#   cost it allows for — reading the card, finding a way around a copy of the repository
#   cut minutes earlier, locating the files a run was sent to change — is paid once, at the
#   start of a run, and never again. Before this correction, a run that had ticked nothing
#   was held to exactly the archive's own median for one checkpoint, and because that
#   figure is a median, roughly half of all first checkpoints exceeded it by construction,
#   before any judgement about whether the run was actually wasteful; on the night of
#   2026-08-08 three separate executors were relayed inside their very first checkpoint for
#   exactly this reason. START_ALLOWANCE (102) was measured (HRN-123.7) from how many tool
#   calls an archived executor run made before the first checkpoint-ticking edit it ever
#   made — the same tick-finding rule bin/agent-spend's own find_ticks() uses (an Edit
#   changing '- [ ]' to '- [x]' on a task-card file) and the same executor/coordinator
#   discriminator bin/agent-spend already uses (HRN-123.1/.4) — across 155 executor runs
#   that ticked at least one checkpoint (414 further executor runs that never ticked one at
#   all were excluded, as meaningless for this measurement): p50=39, p75=62, p90=102,
#   p95=130, p99=230, p100=1751. 102 sits at the p90 point, the same percentile the BRAKE
#   and COORD constants above already use, chosen here for the opposite reason: it is
#   generous enough that the ordinary cost of arriving is fully covered for roughly nine
#   runs in ten, leaving only the small tail of unusually expensive arrivals still exposed
#   to the archive's own median rate on their first checkpoint. (The single p100 outlier,
#   1751, sits inside a durable session transcript whose project directory names a path
#   under .claude/worktrees/ — the exact substring the executor/coordinator discriminator
#   reads as "this is an executor run"; bin/session-start (HRN-115) also cuts a fresh
#   worktree under that same directory for a second COORDINATOR session, which the
#   discriminator has no way to tell apart from an executor's own worktree, so this one
#   value may not be an executor run at all. It does not move the chosen p90 and is
#   recorded here rather than quietly dropped.) START_ALLOWANCE is a flat addition, the
#   same fixed number regardless of a card's own `rate:` override, because the cost it
#   covers — arriving in an unfamiliar copy of the repository — does not scale with how
#   many calls a card's own checkpoints are expected to cost; being a flat addition rather
#   than a multiple of rate is also exactly what makes it "spent once": the very next
#   checkpoint's own budget is still exactly rate higher than the one before it, never
#   rate + START_ALLOWANCE again.
#
#   A FIFTH rule (HRN-123 phase B): the COORD rule gives the coordinator's own session — a
#   call carrying no agent_id at all, the same absence that used to mean "left completely
#   uncounted by every rule in this file" — a ceiling of its own, tracked per SESSION
#   (keyed on transcript_path) rather than per run. COORD_CEILING (761) was set from the
#   measured per-session distribution of the coordinator's own calls across every durable
#   session transcript for this project (HRN-123.4): of 469 session files, 438 never made
#   a single tool call and are excluded as meaningless for a call-count ceiling; among the
#   31 that made at least one, p50=86, p75=188.5, p90=761, p95=888.5, p99=1517.7,
#   p100=1773 — 761 sits at the p90 point and at a natural gap in the data (the next
#   session down sits at 377, less than half), the same p90 reasoning the BRAKE rule above
#   already uses. Past the ceiling, every further coordinator call is refused except an
#   exemption list answering one question: what does a session need in order to land its
#   current milestone and hand off to a fresh one? Three kinds of call are exempt —
#   counted nowhere and always allowed regardless of the ceiling — coord_exempt() below:
#   any Bash call that is a git invocation (version control, this card's own stated
#   minimum); any Edit or Write under a directory literally called ai/ or kb/ (ai/ is the
#   stated minimum, kb/ is added because it is the coordinator's only other legitimate
#   writing surface — see coordinator-source-gate.sh's own allowlist, which draws exactly
#   this line between the coordinator's document trees and an executor's application
#   source); and any Bash call naming bin/session-start, the specific remedy this rule's
#   own refusal message prescribes, exempted so the way out stays usable from the very
#   session it is given to.
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
#   kind, not only Edit/Write — under the TOUCH, PACE, SEARCH-AGENT and BRAKE rules, and,
#   since HRN-123 phase B, every tool call made by the coordinator itself, under the
#   COORD rule alone (the fifth rule above), which is the only one of the five that ever
#   looks at a call carrying no agent_id. A call is identified as the coordinator's own by
#   the ABSENCE of an "agent_id" key in the hook payload — the same discriminator HRN-46
#   measured and confirmed: present and non-empty means a subagent made the call, absent
#   means the coordinator did.
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
# What is NOT gated: the coordinator's own calls that are either exempt under the COORD
#   rule — a git command, an Edit/Write under ai/ or kb/, or a bin/session-start call, see
#   coord_exempt() above — or made with no transcript_path at all to key a per-session
#   ceiling against (fail open, the same posture this whole file takes whenever it cannot
#   establish the state it needs); any run whose brief cannot be recovered at all (no
#   readable transcript record for its agent_id, or a brief that names no task-card-shaped
#   path — see "Fail open when the brief can't be read" below), and a card edited through Bash
#   (a heredoc, sed, or similar) rather than through
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
# task-card-shaped path at all — is allowed past the touch rule, the pace rule and, since
# HRN-139, the brake rule as well, indefinitely, the same way an agent that has never been
# identified as one of this project's executors always has been. Refusing a run this hook
# cannot name a card for would tell it to edit a card it does not have and cannot produce,
# which is a permanent freeze with no way out, not a nudge — the one thing this hook's own
# header already says it must never do. Before HRN-139 the brake rule was the one
# exception: it was evaluated regardless of whether a card had ever been established, so
# an unidentified run's own repeated edits of any one path — including, in effect, its own
# card, since a card can only be recognised as "its own" once state["card"] is set — could
# still be denied outright even though this same header already promised the opposite.
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
# SIX fields now instead of two — {"card": ..., "count": ..., "total_count": ...,
# "search_count": ..., "path_edits": ..., "path_rewrites": ...} — all six in the one file,
# so every rule shares the same per-agent record rather than each keeping a counter of its
# own on disk. "card" and "count" are exactly HRN-49's original fields, read and written
# on exactly the same terms as before. "total_count" is the PACE rule's running tally of
# every non-card-touching call this agent_id has made, which a card touch never resets,
# unlike "count". "search_count" is the read-only search agent's own flat budget, in the
# same file, so that if an agent_id were ever somehow seen under both roles the tallies
# still never collide. "path_edits" (HRN-123) is a small object mapping each distinct
# file_path this run has edited (through Edit or Write, excluding the run's own card) to
# how many times it has been edited so far in this run — the BRAKE rule's own count,
# compared against BRAKE_THRESHOLD on every further Edit/Write of that same path.
# "path_rewrites" (HRN-148) is a small object mapping each distinct file_path to whether
# that path's own one allowed whole-file rewrite past BRAKE_THRESHOLD has already been
# used, {path: true} once it has — see the HRN-148 paragraph above the FOURTH rule's own
# description for what changes once it is. Neither object is ever cleaned up
# automatically — a stray handful of small JSON files per executor run is an accepted,
# stated cost, not an oversight. agent_id values are treated as unique on their own, with
# no session_id folded in, matching how HRN-46 already found them used (a fresh,
# effectively-random id per spawned subagent); a same-day collision between two entirely
# unrelated agents is possible in principle and would only ever cause one run's own counts
# to be read by another, which is a minor mixed count, never a refusal of a call that
# should have been allowed outright or an allowance of one that should not.
#
# A SIXTH kind of state file, added by HRN-123 phase B and unrelated to the per-agent file
# above, tracks the COORD rule alone: one small JSON file per COORDINATOR SESSION — not per
# agent_id, which a coordinator call never carries — at
# $TMPDIR/claude-card-touch-gate/coord-<sanitized transcript_path basename>.json, holding a
# single field {"coord_count": ...}, the count of non-exempt coordinator calls this session
# has made. Kept in the same directory as the per-agent files but under its own "coord-"
# prefix, so the two families of state can never collide even though they are named from
# entirely different inputs (a sanitized transcript_path vs. a sanitized agent_id).
#
# Bypass: CLAUDE_GATE_BYPASS=1 (shared with the other hooks in this directory).
# TOUCH_THRESHOLD: 20 tool calls since the card was last touched — unchanged from HRN-49.
# PACE rates: RELAY 20, REFUSE 28 calls per checkpoint, both set against this project's own
# archive (bin/spend-stats --ceiling): the middle card spends about 15.0-15.2 tool calls per
# checkpoint, a quarter of cards sit below ~11-12 and a quarter above ~19; RELAY (20) sits
# just above that top-quartile boundary and REFUSE (28) is reached by only a small extreme
# tail of the archive. Full figures in HRN-47's own card, checkpoint HRN-47.3.
# START_ALLOWANCE: 102 calls (HRN-123.7/.8), added once per run — never once per checkpoint
# — to both the relay and the refuse budget, so a run's first checkpoint is not held to the
# archive's own median rate while it is still paying the one-time cost of arriving. See the
# "correction to the PACE rule's own arithmetic" paragraph above for the full measurement.
# COORD_CEILING: 761 tool calls in one coordinator session (HRN-123.4/.5) — the measured
# p90 of the per-session distribution of the coordinator's own calls, with an exemption
# list for version-control commands, ai/ or kb/ edits, and bin/session-start. See the
# fifth rule above for the full measurement and reasoning.

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
#
# 2026-08-13: that fixed location used to be the literal /Users/laptop/Dev/ai/hooks — one
# machine's home directory written into a file both machines run, so on a machine whose
# user is not "laptop" brief_reader was unimportable and this hook, which fails open by
# design, silently stopped enforcing anything at all. The default is now derived in the
# order the comment above already argues for: the directory this script itself sits in,
# but only when brief_reader.py is genuinely beside it, which is true for an installed
# hook and false for a candidate in candidates/; and otherwise this machine's own $HOME
# instead of another machine's. HOOK_INSTALL_HOOKS_DIR still overrides both, so
# bin/hook-install and the candidate suites behave exactly as before. Shared verbatim with
# hooks/plan-gate.sh.
HOOKS_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${HOOKS_SELF_DIR}/brief_reader.py" ]]; then
    HOOKS_DIR_DEFAULT="$HOOKS_SELF_DIR"
else
    HOOKS_DIR_DEFAULT="${HOME}/Dev/ai/hooks"
fi
HOOKS_DIR="${HOOK_INSTALL_HOOKS_DIR:-$HOOKS_DIR_DEFAULT}"

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

# --- the BRAKE rule (HRN-123, new) ---
# Set from the measured per-path edit-count distribution across archived executor-run
# transcripts only (HRN-123.1): p50=3, p75=5, p90=9, p95=13, p99=26, p100=34. 9 sits at the
# p90 point — it refuses only the wasteful tail (about one run in ten reaches it at all)
# while every run whose own worst same-path count stays at 8 or below is never touched by
# this rule.
BRAKE_THRESHOLD = 9

# --- the starting allowance (HRN-123 phase C, new) ---
# A fixed number of calls, granted once per run and added, unscaled, to both the relay and
# the refuse budget (never multiplied by the ticked-checkpoint count), so a run's very
# first checkpoint is not held to the archive's own median per-checkpoint rate while it is
# still paying the one-time cost of arriving: reading the card, finding a way around a
# copy of the repository cut minutes earlier, locating the files it was sent to change.
# Measured (HRN-123.7) as how many tool calls an archived executor run made before the
# first checkpoint-ticking edit it ever made, across 155 executor runs that ticked at
# least one checkpoint (414 further executor runs that never ticked one at all were
# excluded): p50=39, p75=62, p90=102, p95=130, p99=230, p100=1751. 102 sits at the p90
# point, the same percentile the BRAKE and COORD constants above already use.
START_ALLOWANCE = 102

# --- the COORD rule (HRN-123 phase B, new) ---
# Set from the measured per-session distribution of the coordinator's own tool calls
# across the durable session transcripts for this project (HRN-123.4): of 469 session
# files under ~/.claude/projects/-Users-laptop-Dev-app/, 438 never made a single tool
# call (short, tool-free conversations, excluded from the distribution below as
# meaningless for a call-count ceiling); among the 31 that made at least one call,
# p50=86, p75=188.5, p90=761, p95=888.5, p99=1517.7, p100=1773. 761 sits exactly at the
# p90 point and at a natural gap in the data (the next session down sits at 377, less
# than half) — it refuses only the small tail of unusually long coordinator sessions
# while leaving the other roughly 90% of working sessions untouched, the same p90
# reasoning the BRAKE rule above already uses.
COORD_CEILING = 761

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

def allow_and_exit(reason=None):
    # HRN-148: an "allow" decision can still carry a permissionDecisionReason — the same
    # shape the HELPER LOAD FAILURE case above already uses — so the BRAKE rule's own
    # from-the-seventh-call-onward warning (see BRAKE_WARNING_TEMPLATE below) can ride on
    # an allowing decision instead of needing a decision of its own. reason=None (every
    # caller of this function except the one call site that tracks the BRAKE rule's own
    # per-path count) reproduces the exact ALLOW_JSON string this function always printed
    # before this card, so no other allow point in this file changes shape.
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": reason,
            }
        }))
    else:
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
    "checkpoint x ({ticked}+1) checkpoint boxes ticked so far, plus a one-time starting "
    "allowance of {allowance} calls for this run's own cold start, granted once per run "
    "and never re-granted at a later checkpoint. This is a relay, not a "
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
    "checkpoint x ({ticked}+1) checkpoint boxes ticked so far, plus the same one-time "
    "starting allowance of {allowance} calls the relay tier above already carries — well "
    "past its own relay point. Every further call is refused outright, because a run this far above the "
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

BRAKE_TEMPLATE = (
    "Blocked by card-touch-gate's BRAKE rule: this run has now edited {path} {count} "
    "times within this one run, past the threshold of {threshold}; rewrite the file in a "
    "single call instead of continuing to edit it piece by piece. (This rule tracks one "
    "file path at a time and is independent of the TOUCH, PACE and SEARCH-AGENT rules on "
    "the same run; an edit of this run's own task card is never counted against it.)"
)

# HRN-148: a Write past BRAKE_THRESHOLD is the remedy BRAKE_TEMPLATE above asks for, so
# exactly one Write of a path is let through once the threshold is reached — never
# refused by BRAKE_TEMPLATE, which stays the Edit-only message it always was. A second
# Write of the same path past the threshold means the run has not consolidated what it
# was told to consolidate, and the honest answer to that is to stop rather than to keep
# rewriting the same file over and over by choosing a different tool each time.
BRAKE_REWRITE_USED_TEMPLATE = (
    "Blocked by card-touch-gate's BRAKE rule: this run has already used its one allowed "
    "whole-file rewrite of {path} past the threshold of {threshold} (this Write would be "
    "call number {count} against this one path within this run), and a further Write of "
    "the same path is refused. Record where this run has stopped — tick the checkpoint "
    "you finished and overwrite the card's own '## Working state' section with what this "
    "run has established so far — and stop there; a fresh executor can continue from "
    "that record. (This rule tracks one file path at a time and is independent of the "
    "TOUCH, PACE and SEARCH-AGENT rules on the same run; an edit of this run's own task "
    "card is never counted against it.)"
)

# HRN-148, AC4: attached to an ALLOWING decision, never a refusing one, from the seventh
# call against a path onward, so a run nearing the ceiling has a chance to consolidate
# into one Write while a Write is still exempt — see the "one Write past the ceiling"
# comment above BRAKE_REWRITE_USED_TEMPLATE. Whether this reason is ever surfaced to the
# run that receives it is not something this hook can prove or control; what is proved is
# only that the hook's own JSON output carries it (HRN-148 AC6).
BRAKE_WARNING_TEMPLATE = (
    "card-touch-gate's BRAKE rule: {path} has been edited or written {count} times in "
    "this run so far, against a ceiling of {threshold}. Consolidating what remains into "
    "one whole-file rewrite now, while a single rewrite is still allowed past that "
    "ceiling, keeps the ability to finish this file in one call."
)

COORD_TEMPLATE = (
    "Blocked by card-touch-gate's COORD rule: this coordinator session has made {count} "
    "tool calls against its own ceiling of {ceiling}; land the current milestone (commit "
    "and, if it is finished, push or merge what is done) and start a fresh session "
    "through bin/session-start. (Version-control commands, any Edit or Write under ai/ "
    "or kb/, and the bin/session-start call itself are exempt from this rule and from "
    "its own count, so a session past this ceiling can still commit, write its task "
    "cards and decisions, and hand off; every other call is refused until then. This "
    "rule counts only the coordinator's own calls — those carrying no agent_id at all — "
    "tracked per session rather than per run, and never touches an executor's own TOUCH, "
    "PACE, SEARCH-AGENT or BRAKE budget on the same or any other run.)"
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


def coord_exempt(tool_name, tool_input):
    """True for the calls the COORD rule (HRN-123 phase B) never counts and always
    allows, past its own ceiling or not — the answer to "what does a coordinator session
    need in order to land its current milestone and hand off to a fresh one", the exact
    question its own refusal message poses. Three kinds, each named in this card's own
    acceptance criteria or the refusal message itself: (1) a Bash call that is a git
    invocation — the tool name checked is literally "git" once any leading path (./git,
    /usr/bin/git) is stripped, covering every subcommand rather than a chosen few, because
    committing, pushing and merging are all "the version-control commands" the card names,
    and a coordinator composing the right commit needs the read-only ones (status, diff,
    log) too; (2) an Edit or Write whose path names a directory literally called ai/ or
    kb/ — ai/ is this card's own stated minimum, kb/ is added because it is the only other
    tree the coordinator legitimately writes directly (coordinator-source-gate.sh's own
    allowlist draws exactly this line: task cards, decisions and knowledge-base pages are
    the coordinator's, application source under dpp_demo/dpp_frontend/dpp-vldt is an
    executor's); and (3) a Bash call naming bin/session-start — the specific remedy this
    rule's own message prescribes, exempted so that prescription stays usable from the
    very session it is given to rather than becoming a way out this rule itself blocks."""
    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return False
        if "bin/session-start" in command:
            return True
        tokens = command.strip().split()
        if tokens and tokens[0].rsplit("/", 1)[-1] == "git":
            return True
        return False
    if tool_name in ("Edit", "Write"):
        fp = tool_input.get("file_path")
        if not isinstance(fp, str) or not fp:
            return False
        segments = [s for s in fp.replace("\\", "/").split("/") if s]
        return "ai" in segments or "kb" in segments
    return False


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

tool_name = data.get("tool_name") or ""
tool_input = data.get("tool_input") or {}
transcript_path = data.get("transcript_path")
agent_type = data.get("agent_type") or ""

agent_id = data.get("agent_id")
if not agent_id:
    # No agent_id at all means this call is the coordinator's own (HRN-46's own finding).
    # Until HRN-123 phase B this meant "never counted, never gated, by design" outright;
    # now it means "judged only by the COORD rule, in its own try/except, entirely
    # separate from the four agent-scoped rules below" — a coordinator call still never
    # touches the TOUCH, PACE, SEARCH-AGENT or BRAKE rules, which all require an agent_id
    # to key their own state on and none of which this branch ever reaches.
    try:
        if coord_exempt(tool_name, tool_input):
            allow_and_exit()
        if not transcript_path:
            # No session identifier at all to key a per-session ceiling on: fail open,
            # the same posture every other rule in this file takes when it cannot
            # establish the state it needs to judge anything.
            allow_and_exit()
        coord_state_dir = os.environ.get("CARD_TOUCH_GATE_STATE_DIR") or \
            os.path.join(tempfile.gettempdir(), "claude-card-touch-gate")
        os.makedirs(coord_state_dir, exist_ok=True)
        # Keyed on a sanitized transcript_path rather than on agent_id, which a
        # coordinator call never carries — the "coord-" prefix keeps this family of
        # state files from ever colliding with an agent's own <agent_id>.json file, even
        # though the two are named from entirely different inputs.
        safe_session = re.sub(r'[^A-Za-z0-9_-]', '_', os.path.basename(str(transcript_path)))
        coord_state_path = os.path.join(coord_state_dir, "coord-" + safe_session + ".json")
        coord_count = 0
        if os.path.isfile(coord_state_path):
            try:
                with open(coord_state_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    coord_count = loaded.get("coord_count", 0)
            except Exception:
                coord_count = 0  # a corrupt state file is a fresh start, not an error to deny on
        coord_count += 1
        with open(coord_state_path, "w", encoding="utf-8") as f:
            json.dump({"coord_count": coord_count}, f)
        if coord_count > COORD_CEILING:
            print(deny_json(COORD_TEMPLATE.format(count=coord_count, ceiling=COORD_CEILING)))
            sys.exit(0)
        allow_and_exit()
    except Exception:
        # Same fail-open decision the rest of this file makes on any internal error, and
        # for the same reason — see the file header.
        allow_and_exit()

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

    # HRN-148: "path_rewrites" tracks, per path, whether that path's own one allowed
    # whole-file rewrite past BRAKE_THRESHOLD has already been used — see
    # BRAKE_REWRITE_USED_TEMPLATE above for what happens once it has.
    state = {"card": None, "count": 0, "total_count": 0, "search_count": 0, "path_edits": {},
              "path_rewrites": {}}
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
        # never one either rule denies. An edit of the run's own card never reaches the
        # BRAKE rule below at all, by construction — this is the whole of how "the run's
        # own card is never braked" holds, rather than a special case inside that rule.
        state["count"] = 0
        state["total_count"] = state.get("total_count", 0) + 1
        save_state()
        allow_and_exit()

    # --- HRN-139: none of TOUCH, PACE or BRAKE fires for a run whose card was never
    # established at all: fail open, exactly as HRN-49 always has for TOUCH and PACE. This
    # check used to sit only after the BRAKE rule below, which let the BRAKE rule count and
    # deny an unidentified run's repeated edits of any path — including its own card, which
    # is never recognised as "its own card" without an established `state["card"]` to
    # compare against (see touches_card() above) — even though this hook's own header says
    # a card edit is always exempt from the brake. Moving this check ahead of the BRAKE
    # rule makes that exemption hold structurally for the one case it used to miss: a run
    # this hook could never name a card for is not merely un-braked on its own card, it is
    # not braked at all, on the same "cannot ask a run to edit a card it does not have"
    # reasoning the header already gives for the TOUCH and PACE rules. ---
    if not state.get("card"):
        allow_and_exit()

    # --- Rule: the BRAKE rule (HRN-123, extended by HRN-148) — refuses the Nth Edit/Write
    # of one and the same path within this run, EXCEPT that exactly one Write past the
    # threshold is let through: BRAKE_TEMPLATE's own advice is "rewrite the file in a
    # single call", so a Write is the remedy, not more of the pathology, and refusing it
    # too made that remedy permanently unreachable once the threshold was crossed. A
    # second Write of the same path past the threshold is refused (BRAKE_REWRITE_USED_
    # TEMPLATE) — the run has not consolidated what it was told to. An Edit is still
    # refused unconditionally from the threshold onward, with the same message as before
    # this card. Reached only once a card has been established for this run (the check
    # just above), even though the rule itself still needs no established card to make
    # sense on its own terms: it is about one path being rewritten piece by piece too many
    # times in a single run, not about a run's pace against its own checkpoints. A
    # malformed or missing file_path (not a string, or empty) is simply not trackable and
    # falls through untouched, same as every other malformed-payload case this hook
    # already fails open on. ---
    brake_warning_reason = None
    if tool_name in ("Edit", "Write"):
        fp = tool_input.get("file_path")
        if isinstance(fp, str) and fp:
            path_edits = state.get("path_edits")
            if not isinstance(path_edits, dict):
                path_edits = {}
            new_path_count = path_edits.get(fp, 0) + 1
            path_edits[fp] = new_path_count
            state["path_edits"] = path_edits
            save_state()
            if new_path_count >= BRAKE_THRESHOLD:
                if tool_name == "Write":
                    path_rewrites = state.get("path_rewrites")
                    if not isinstance(path_rewrites, dict):
                        path_rewrites = {}
                    if path_rewrites.get(fp):
                        print(deny_json(BRAKE_REWRITE_USED_TEMPLATE.format(
                            path=fp, count=new_path_count, threshold=BRAKE_THRESHOLD)))
                        sys.exit(0)
                    path_rewrites[fp] = True
                    state["path_rewrites"] = path_rewrites
                    save_state()
                    brake_warning_reason = BRAKE_WARNING_TEMPLATE.format(
                        path=fp, count=new_path_count, threshold=BRAKE_THRESHOLD)
                else:
                    print(deny_json(BRAKE_TEMPLATE.format(
                        path=fp, count=new_path_count, threshold=BRAKE_THRESHOLD)))
                    sys.exit(0)
            elif new_path_count >= 7:
                brake_warning_reason = BRAKE_WARNING_TEMPLATE.format(
                    path=fp, count=new_path_count, threshold=BRAKE_THRESHOLD)

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
            # HRN-123.8: START_ALLOWANCE is added flat, unscaled by (ticked + 1) — this is
            # the whole of how it is "spent once per run" rather than "once per
            # checkpoint": a flat additive term does not compound as ticked grows, so the
            # very next checkpoint's own budget is still exactly relay_rate (or
            # refuse_rate) higher than the one before it, never that plus START_ALLOWANCE
            # again.
            budget_relay = relay_rate * (ticked + 1) + START_ALLOWANCE
            budget_refuse = refuse_rate * (ticked + 1) + START_ALLOWANCE

            if total_new_count > budget_refuse:
                print(deny_json(PACE_REFUSE_TEMPLATE.format(
                    count=total_new_count, budget=fmt_num(budget_refuse),
                    card=state["card"], rate=fmt_num(refuse_rate), ticked=ticked,
                    allowance=fmt_num(START_ALLOWANCE))))
                sys.exit(0)
            if total_new_count > budget_relay:
                print(deny_json(PACE_RELAY_TEMPLATE.format(
                    count=total_new_count, budget=fmt_num(budget_relay),
                    card=state["card"], rate=fmt_num(relay_rate), ticked=ticked,
                    allowance=fmt_num(START_ALLOWANCE))))
                sys.exit(0)

    # HRN-148, AC4/AC5: brake_warning_reason is non-None only when the BRAKE rule itself
    # neither denied this call nor was even reached (in which case it stays the None it
    # was initialised to just above the BRAKE block) — every other allow point in this
    # file still calls allow_and_exit() with no argument and is unaffected.
    allow_and_exit(brake_warning_reason)

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
