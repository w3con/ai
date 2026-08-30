#!/usr/bin/env bash
# work-gate.sh — PreToolUse hook: the enforcement backbone of the new work-management
# system (HRN-2, ai/harness/system/project.md, "Хук на вызов инструмента", in the
# validite-app repository). A rule that used to live only in prose becomes a rule nobody can
# break by accident, because the tool call itself is refused.
#
# This file currently builds phases HRN-2.A (the fitness guard and caller identity),
# HRN-2.B (one-file-one-author and the log-write ceiling), HRN-2.D/F (the phase boundary,
# judged against the run's own named phase), HRN-2.E's own rewrite of closed_steps_for_phase
# to read a step's closure by its permanent name rather than only the older free-form "шаг N"
# convention, and HRN-2.C (the context/spend/pace ceilings, read from the run's own
# transcript, plus the file-edit brake).
#
# WHAT THIS FILE DOES, IN THE ORDER IT DOES IT
#
#  1. Bypass: CLAUDE_GATE_BYPASS=1 disables every rule below, the same escape hatch the
#     other hooks in this directory share (memory-store-guard.sh, plan-gate.sh,
#     card-touch-gate.sh).
#
#  2. FITNESS: every call is refused — the coordinator's own included — unless this file's
#     own current SHA-256 is a member of the committed hash ledger (HRN-41,
#     hooks/work-gate.verified-hashes.txt next to this file, one proven fingerprint per
#     line) rather than a single value in a machine-wide temp marker every session used to
#     compete over. bin/work-refusals appends the current fingerprint to that ledger on a
#     full pass (never rewriting the file — see append_to_ledger() there); this hook only
#     ever checks whether its own current hash already appears somewhere in the ledger.
#     This repository's own ~/Dev/ai/.githooks/pre-commit runs bin/work-refusals --only
#     hook against a staged edit's own indexed bytes and appends its fingerprint to the
#     ledger in the same commit, so a committed edit never lands unfit (HRN-41.B).
#     Three things get through regardless, because without them a broken gate could never
#     be repaired: running bin/work-refusals itself, an Edit/Write of this file, and a
#     Write/Edit of any card's own log.md.
#
#  3. CALLER IDENTITY: a call carrying no agent_id in its payload is the session's own — the
#     orchestrator — and passes with no further inspection ("вызов самой сессии пропускает
#     без разбора"). Everything from here on applies only to a subagent's own call.
#
#  4. NO BRIEF, NO LAUNCH: a subagent is known to this hook only because something told it —
#     a small caller-brief file naming its role and the card it works, {"role": ...,
#     "card": ...}. bin/work-agent-brief is the script that writes one, called by a
#     subagent as its own first action, naming its own role and card
#     (`bin/work-agent-brief --role executor --card HRN-6`). Two things write a brief, for
#     two different reasons:
#       - THIS HOOK, the moment it sees that very Bash call go by, parses --role/--card
#         straight out of the command string and writes briefs/agent-<agent_id>.json, keyed
#         on the agent_id carried by that SAME call's own payload — the only identifier
#         available at that moment that is guaranteed fresh and stable for this subagent's
#         whole life, established already for exactly this reason by HRN-46 and reused
#         unchanged by card-touch-gate.sh in this same directory ("agent_id values are
#         treated as unique on their own, with no session_id folded in"). agent_id cannot be
#         known before the subagent exists, so no launcher script run by the orchestrator
#         could ever write this file itself — only this hook, watching the subagent's own
#         first call, can.
#       - bin/work-agent-brief ITSELF, once the hook has allowed that same call through and
#         the real script runs a moment later, separately writes
#         briefs/session-<CLAUDE_CODE_SESSION_ID>.json — a second, independently useful path
#         (the script is a real, standalone command, testable on its own, and the one that
#         honours this card's own plan wording of a brief "named by the agent's session
#         identifier"), kept as a fallback this hook reads only when no agent_id-keyed brief
#         exists yet.
#     A subagent with neither file has every call refused, with one exemption: the Bash call
#     that runs bin/work-agent-brief itself, since that is how the very first brief gets
#     written at all.
#
#  5. PHASE BOUNDARY (HRN-2.D, rewritten by HRN-2.F): applies only to a subagent whose brief
#     names role "executor" — every other role is never judged by this rule at all. HRN-2.D's
#     own reading — "the current phase is the first phase in plan.md's own order that still
#     has an open step" — silently required every phase of the whole plan to close before the
#     boundary ever fired, so an executor that finished its own phase walked straight into
#     the next one (found live, on this very card, by HRN-2.B's own executor). HRN-2.F
#     replaces that scan: the boundary is judged only against the ONE phase this run's own
#     caller-brief names (bin/work-agent-brief's own --phase), never against the plan as a
#     whole.
#       - No phase named in the brief at all: refused, every call except a Write/Edit of the
#         card's own log.md — the same shape as "no caller-brief file", because an unnamed
#         phase would leave this rule nothing to judge and the run would never be stopped
#         (owner's own correction, 2026-08-28: «неназванная фаза не освобождает от границы,
#         а запрещает работу»).
#       - Phase named: read plan.md's own "## Шаги" section, split into phases by its
#         "### <ID>.<letter> — …" subheadings (a plan not split into phases at all is one
#         implicit phase named by the bare card id); each phase's steps are its own "- "
#         bullet lines, in order, numbered 1..N. Read log.md's own headings of the shape
#         "## <ID>.<letter>, шаг <N>" or "…, шаг <N>–<M>" (en dash), the convention HRN-2.A's
#         own executor established — the numbers named there are that phase's closed steps.
#         A phase that does not appear in plan.md at all is not a state this rule can judge,
#         so the call is skipped rather than denied. Once every one of the named phase's own
#         steps is closed, the boundary is reached for THAT phase — every further call is
#         refused except a Write/Edit of the card's own log.md, with the words «допиши
#         передачу и остановись», regardless of what any other phase in the plan looks like
#         (closed, open, or never started at all). While the named phase still has an open
#         step, every call passes with no inspection at all.
#     A card whose plan.md cannot be read is not yet in a state this rule can judge, so it is
#     skipped rather than denied — the same fail-open choice bin/work-agent-brief's own
#     malformed-command case already makes in rule 4 above.
#
#  8. CONTEXT SIZE CEILING (HRN-2.C): applies to every subagent call carrying a brief, any
#     role — "агента", not "исполнителя", is the word project.md's own paragraph uses. The
#     size of the context the agent's own most recent turn actually held (input_tokens +
#     cache_creation_input_tokens + cache_read_input_tokens of the LAST assistant record in
#     this run's own transcript, named by transcript_path in the hook's payload — what that
#     one generation was actually given to read, not a sum across the run) is compared
#     against CONTEXT_SIZE_CEILING (300,000 tokens). Past it, every call is refused except a
#     Write/Edit of this card's own log.md, with the words «запиши состояние в лог и
#     остановись» the plan itself quotes. A transcript that cannot be read, or carries no
#     assistant record with a usage field at all, is not a state this rule can judge, so the
#     call is skipped rather than denied — the same fail-open choice rule 5 already makes for
#     an unreadable plan.md.
#
#  9. SPEND CEILING (HRN-2.C): applies only to role "executor" — project.md's own wording
#     names it explicitly ("Потолок по расходу считается на прогон исполнителя"), unlike
#     rule 8 above. The run's cumulative spend (cache_read_input_tokens + output_tokens,
#     summed across every assistant record in this run's own transcript — the same
#     definition bin/agent-spend's own emit_spend() already uses for a card's `spend:`
#     field, reused here rather than invented fresh) is compared against SPEND_CEILING
#     (90,000,000 tokens). Counted per run, from that run's own transcript alone, never
#     accumulated across a card: there is no state file behind this number at all, so a
#     fresh executor's own fresh transcript starts this same count at zero by construction
#     — "свежий исполнитель приходит на карточку с нулём".
#
# 10. PACE CEILING (HRN-2.C): applies only to role "executor", the same scope as rule 9. The
#     run's own spend (rule 9's own count) divided by the number of tool calls it has made
#     (one per tool_use content block across the transcript) is compared against a threshold
#     read from a machine file, PACE_THRESHOLD_FILE (default hooks/work-gate-pace-threshold.txt,
#     next to this file — 460,000 as of HRN-2.C, per project.md's own "Потолок по темпу").
#     That file's absence, or content that does not parse as a bare integer, refuses every
#     call for this executor except a Write/Edit of this card's own log.md, regardless of
#     call count — this check runs before the call-count gate below, not behind it. Once a
#     threshold is read, the ceiling itself is judged only once this run has made more than
#     PACE_CALL_ALLOWANCE (120) tool calls — "темп не проверяется первые сто двадцать
#     вызовов" — every call up to and including the 120th passes with no inspection.
#
# 11. FILE-EDIT BRAKE (HRN-2.C, extended by HRN-21.C.1): the Nth Edit/Write of one and the
#     same file inside one run refuses — mirrors hooks/card-touch-gate.sh's own BRAKE rule
#     and its measured threshold (BRAKE_THRESHOLD = 9, HRN-123.1's own p90 of the per-path
#     edit-count distribution across archived executor runs) rather than deriving a fresh
#     number for the same fact, matching the number this card's own plan names directly
#     ("девятая правка"). Applies to every role — the plan states this ceiling "в одном
#     прогоне", not "у исполнителя" the way it names rules 9 and 10 above. A Write/Edit
#     inside this card's own folder is never counted at all ("не считая записей в файлы
#     карточки"); a Bash call re-running the same command however many times is never
#     counted either, since this rule only ever inspects Write/Edit ("не ограничивать
#     повторный запуск одной и той же команды"). HRN-21.C.1: the very first Write that
#     brings a file into existence — one that does not yet exist on disk at the moment this
#     hook runs — is not a "правка" of anything and is never counted either, whatever count
#     already sits on file for that path; and since the brake exists to catch hammering of
#     code that was already on disk when the run began, that creation also takes the path
#     out of the count for the rest of the run, marker file and all ("тормоз ловит долбёжку по одному
#     месту, а не написание нового файла").
#
# 12. REPEATED REFUSAL → GLOBAL BREAKAGE (HRN-13.C): every call to deny_and_exit(reason,
#     rule) below, for a call that carries an agent_id (a subagent's own call — rule 3
#     already let the session's own call through before this could ever run), counts against
#     a per-agent, per-rule streak. Three denials in a row by the SAME rule write one line to
#     the global-breakage journal (ai/harness/journals/global.md, via `bin/work-journal
#     --breakage-once`, deduplicated so the same agent+rule pair never earns a second line
#     the same day) and reset the streak to zero; a denial by a DIFFERENT rule resets the
#     streak to one without writing anything; a call this hook ALLOWS never reaches
#     deny_and_exit at all, so it neither increments nor resets the streak — an executor
#     denied by the same rule, forced to write log.md (itself always allowed) in between,
#     still hits three in a row on its next matching denial ("разрешённый вызов между
#     отказами счёт не сбрасывает").
#
# STATE. Everything this hook remembers between calls lives under WORK_GATE_STATE_DIR
# (default "${TMPDIR:-/tmp}/claude-work-gate", the convention hooks/card-touch-gate.sh
# already uses for its own per-agent state): briefs/agent-<agent_id>.json /
# briefs/session-<session_id>.json (rule 4), log-call-counts/agent-<agent_id>.txt (rule 7),
# file-edit-counts/agent-<agent_id>/<sanitized-path>.txt (rule 11) and
# consecutive-refusals/agent-<agent_id>.txt (rule 12: the last rule that denied this agent,
# and how many times in a row). Rule 2's own ledger lives outside this per-session state
# tree entirely — it is a committed file, deployed with this hook and read the same way by
# every session, never per-agent or per-run state. Rule 5 keeps no state of its own — it
# re-reads plan.md and log.md fresh on every call, and rules 8-10 keep no state of their own
# either — each re-reads this run's own transcript fresh on every call.
#
# TEST OVERRIDES, read only by bin/work-refusals, never present in a real deployed session:
#   WORK_GATE_STATE_DIR            overrides the whole state tree above.
#   WORK_GATE_LEDGER_PATH          overrides the path rule 2 reads its hash ledger from
#                                   (default hooks/work-gate.verified-hashes.txt, next to
#                                   this file).
#   WORK_GATE_WORK_ROOT            overrides the work root rule 5 resolves a card id
#                                   against (the directory holding the "harness" and
#                                   "timeline" kind folders, normally found via `git
#                                   worktree list --porcelain`'s own first entry — the
#                                   shared checkout's path, since a card's folder always
#                                   lives there and never inside a linked worktree's own
#                                   copy).
#   WORK_GATE_PACE_THRESHOLD_FILE  overrides the path rule 10 reads its threshold from
#                                   (default hooks/work-gate-pace-threshold.txt, next to
#                                   this file).
#
# Fail-closed: unparseable stdin denies.

STDIN_DATA="$(cat)"
# Passed to Python as-is; Python resolves it to the real underlying file with
# os.path.realpath() — see the comment on self_path below for why plain string handling
# here is not enough (~/.claude/hooks/ is itself a symlinked directory, and neither `cd
# "$(dirname ...)" && pwd` nor a hand-rolled `[ -L ]` loop over just the final path
# component follows a symlinked *directory* component, only a symlinked final file).
SELF_PATH="${BASH_SOURCE[0]}"

exec python3 - "$SELF_PATH" "$STDIN_DATA" <<'PYEOF'
import hashlib
import json
import os
import re
import subprocess
import sys

# realpath(), not just the literal argv value: ~/.claude/hooks/ is itself a symlinked
# directory (bin/bootstrap.sh points it at this file's real repository path), and Claude
# Code always invokes this hook through that deployed, symlinked path — never through the
# real repository path directly. Without resolving through the directory symlink here, the
# self-edit exemption below (which compares this value against the file_path an Edit/Write
# call names, always the real repository path) would never match a live invocation, only
# bin/work-refusals's own synthetic cases, which run bash directly against the real path
# and so never exercised the symlink at all (found and fixed in HRN-2.D).
self_path  = os.path.realpath(sys.argv[1])
stdin_data = sys.argv[2]

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

def allow_and_exit():
    print(ALLOW_JSON)
    sys.exit(0)

def _journal_shared_checkout_root():
    """The root bin/work-journal is found under and the journal files themselves resolve
    against, the same WORK_JOURNAL_DIR override bin/work_journal.py's own _checkout_root()
    honours first — this hook cannot import that module across the repository boundary, so
    it re-derives the same resolution here, never raising. Without the override: `git
    worktree list --porcelain`'s own first entry, the shared checkout's own path."""
    override = os.environ.get("WORK_JOURNAL_DIR")
    if override:
        return override
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):].strip()
    return None

def _write_refusal_journal(rule, input_text):
    """Best-effort call to bin/work-journal --refusal in the separate validite-app
    repository (HRN-13.B.4, HRN-13.A.4's own bin/work-journal) — never raises and never
    changes deny_and_exit's own return value or exit code, exactly like every other rule in
    this file that already fails open on an unreadable input rather than denying for a
    reason of its own making."""
    try:
        root = _journal_shared_checkout_root()
        if root is None:
            return
        journal_cmd = os.path.join(root, "bin", "work-journal")
        who = "hooks/work-gate.sh:" + str(globals().get("agent_id") or "session")
        subprocess.run([journal_cmd, "--refusal", who, rule, input_text],
                        capture_output=True, timeout=5)
    except Exception:
        pass

def consecutive_refusal_state_path(state_dir, aid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    return os.path.join(state_dir, "consecutive-refusals", "agent-" + safe + ".txt")

def read_consecutive_refusal_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            rule, count = f.read().strip().split("\t", 1)
        return rule, int(count)
    except (OSError, ValueError):
        return None, 0

def write_consecutive_refusal_state(path, rule, count):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(rule + "\t" + str(count))

CONSECUTIVE_REFUSAL_CEILING = 3

def _record_repeated_refusal(rule):
    """HRN-13.C.1: bump this agent's own consecutive-refusal streak for `rule`; on the third
    in a row, write one line to the global-breakage journal (deduplicated per agent+rule+day
    by bin/work-journal --breakage-once itself) and reset the streak to zero. A denial by a
    DIFFERENT rule resets the streak to one instead of writing anything. Skipped entirely for
    the session's own call (no agent_id) and for the narrow window before STATE_DIR itself
    is assigned — the same defensive globals().get(...) pattern _write_refusal_journal
    already uses above. Never raises."""
    aid = globals().get("agent_id")
    state_dir = globals().get("STATE_DIR")
    if not aid or not state_dir:
        return
    try:
        path = consecutive_refusal_state_path(state_dir, aid)
        last_rule, count = read_consecutive_refusal_state(path)
        count = count + 1 if last_rule == rule else 1
        if count >= CONSECUTIVE_REFUSAL_CEILING:
            root = _journal_shared_checkout_root()
            if root is not None:
                journal_cmd = os.path.join(root, "bin", "work-journal")
                key = "work-gate.repeated-refusal:%s:%s" % (aid, rule)
                text = ("hooks/work-gate.sh: агента %s правило %s отказало три раза "
                        "подряд." % (aid, rule))
                subprocess.run([journal_cmd, "--breakage-once", key, text],
                                capture_output=True, timeout=5)
            count = 0
        write_consecutive_refusal_state(path, rule, count)
    except Exception:
        pass

def deny_and_exit(reason, rule):
    _write_refusal_journal(rule, reason)
    _record_repeated_refusal(rule)
    print(deny_json(reason))
    sys.exit(0)

# --- 1. bypass -----------------------------------------------------------------------
if os.environ.get("CLAUDE_GATE_BYPASS") == "1":
    allow_and_exit()

# --- parse stdin (fail closed) --------------------------------------------------------
try:
    if not stdin_data.strip():
        raise ValueError("empty stdin")
    data = json.loads(stdin_data)
except Exception:
    deny_and_exit("Blocked by work-gate: gate error (unreadable hook payload), failing closed.", "work-gate.unreadable-payload")

tool_name  = data.get("tool_name") or ""
tool_input = data.get("tool_input") or {}
agent_id   = data.get("agent_id")
session_id = data.get("session_id") or ""

STATE_DIR = os.environ.get("WORK_GATE_STATE_DIR") or \
    os.path.join(os.environ.get("TMPDIR", "/tmp"), "claude-work-gate")
BRIEFS_DIR = os.path.join(STATE_DIR, "briefs")

# A card's own log.md, under the new folder shape ai/<kind>/<epic>/<ID>_<slug>/log.md, kind
# being "harness" or "timeline" (ai/harness/system/project.md, "Эпик"). Only log.md is
# matched here — the other card files, and the "one file, one author" rule that names them,
# belong to HRN-2.B, not to this file yet.
LOG_FILE_RE = re.compile(r'/ai/(?:harness|timeline)/[^/]+/[^/]+/log\.md$')

def file_path_of(ti):
    fp = ti.get("file_path")
    return fp if isinstance(fp, str) and fp else None

def command_of(ti):
    cmd = ti.get("command")
    return cmd if isinstance(cmd, str) else ""

def bash_names(command, script_basename):
    """True when a Bash command invokes a script by this basename — matched on any
    occurrence of the basename in the command line, the same coarse-but-safe matching
    harness-stamp-gate.sh already uses for 'bootstrap.sh' in its own command."""
    return script_basename in command

# --- 2. FITNESS: the current hash must be a proven member of the committed ledger --------
def own_hash():
    try:
        with open(self_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None

def ledger_path():
    return os.environ.get("WORK_GATE_LEDGER_PATH") or \
        os.path.join(os.path.dirname(self_path), "work-gate.verified-hashes.txt")

def ledger_contains(h):
    try:
        with open(ledger_path(), "r", encoding="utf-8") as f:
            return h in {line.strip() for line in f}
    except OSError:
        return False

is_refusals_run = tool_name == "Bash" and bash_names(command_of(tool_input), "work-refusals")
is_gate_self_edit = tool_name in ("Write", "Edit") and \
    file_path_of(tool_input) is not None and \
    os.path.realpath(file_path_of(tool_input)) == self_path
is_log_write = tool_name in ("Write", "Edit") and \
    file_path_of(tool_input) is not None and \
    LOG_FILE_RE.search(file_path_of(tool_input).replace(os.sep, "/")) is not None

current = own_hash()
fitness_ok = current is not None and ledger_contains(current)

if not fitness_ok:
    if is_refusals_run or is_gate_self_edit or is_log_write:
        allow_and_exit()
    deny_and_exit(
        "Blocked by work-gate's FITNESS rule: this hook's own file has changed since "
        "bin/work-refusals last passed against it, and a gate that might be broken stops "
        "every call rather than failing silently. Run bin/work-refusals to clear this; "
        "while it stands, the only calls that still get through are that run itself, an "
        "Edit/Write of hooks/work-gate.sh, and a Write/Edit of any card's own log.md. Set "
        "CLAUDE_GATE_BYPASS=1 only for a deliberate, known exception.",
        "work-gate.fitness-blocks-until-suite-passes"
    )

# --- 3. the session's own call passes without inspection ------------------------------
if not agent_id:
    allow_and_exit()

# --- 4. no brief, no launch (one exemption: writing the very first brief) -------------
KNOWN_ROLES = {"critic", "mapper", "executor", "tracer", "acceptor"}

def agent_brief_path(aid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    return os.path.join(BRIEFS_DIR, "agent-" + safe + ".json")

def session_brief_path(sid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(sid)) if sid else "_no_session_id_"
    return os.path.join(BRIEFS_DIR, "session-" + safe + ".json")

is_brief_self_write = tool_name == "Bash" and bash_names(command_of(tool_input), "work-agent-brief")
if is_brief_self_write:
    # The one moment this hook writes state of its own accord rather than only reading it:
    # agent_id is the sole identifier proven stable for a subagent's whole life (HRN-46), and
    # it is never visible to the subagent's own shell as an environment variable — only to
    # this hook's own payload — so this hook is the only thing that can ever correctly key a
    # brief on it. Parsed straight out of the command string about to run; a command that
    # does not parse (a malformed invocation) is still allowed through unconditionally,
    # since the real script's own argument validation is what should report that failure,
    # not this hook.
    command = command_of(tool_input)
    m_role = re.search(r'--role[= ]+(\S+)', command)
    m_card = re.search(r'--card[= ]+(\S+)', command)
    m_phase = re.search(r'--phase[= ]+(\S+)', command)
    if m_role and m_card and m_role.group(1) in KNOWN_ROLES and agent_id:
        os.makedirs(BRIEFS_DIR, exist_ok=True)
        brief_obj = {"role": m_role.group(1), "card": m_card.group(1)}
        if m_phase:
            brief_obj["phase"] = m_phase.group(1)
        try:
            with open(agent_brief_path(agent_id), "w", encoding="utf-8") as f:
                json.dump(brief_obj, f)
        except OSError:
            pass
    allow_and_exit()

def read_brief(aid, sid):
    for path in (agent_brief_path(aid) if aid else None, session_brief_path(sid)):
        if not path:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                b = json.load(f)
        except Exception:
            continue
        if not isinstance(b, dict):
            continue
        role, card = b.get("role"), b.get("card")
        if role and card:
            # "phase" (HRN-2.F): the plan phase this run is working, named only by whoever
            # launched it — bin/work-agent-brief's own --phase — and never derivable from the
            # card's own files. None when the brief carries no such key at all (an older
            # brief, or any role other than executor, which the phase boundary rule below
            # never requires it from).
            return {"role": role, "card": card, "phase": b.get("phase")}
    return None

brief = read_brief(agent_id, session_id)
if brief is None:
    deny_and_exit(
        "Blocked by work-gate: this subagent carries no caller-brief file. The step that "
        "launches an agent must run bin/work-agent-brief first, naming this agent's own "
        "role and the card it is working — this hook writes %s the moment it sees that "
        "call, and the script itself separately writes %s; neither exists yet (or neither "
        "is valid JSON naming a role and a card). «Нет файла — нет запуска.»" %
        (agent_brief_path(agent_id), session_brief_path(session_id)),
        "work-gate.no-brief-no-launch"
    )

# --- 5. PHASE BOUNDARY: an executor whose current phase has no open steps left is refused
# every call except a Write/Edit of its own card's log.md, and a Bash call that does nothing
# but `git add` or `git commit` (HRN-2.D, extended by HRN-21.A) -----------------------

# HRN-21.A: the boundary exists to stop an executor from STARTING new work once its own
# phase is closed, not to stop it from SAVING work already done — writing the log entry that
# closes the phase is worthless if the very next call, the commit that lands it, is refused.
# This list is closed and literal, per this card's own plan ("Решения, принятые при
# написании плана", "Защёлка ничего не толкует и ничего не угадывает"): no rule here
# recognises a call by resemblance to a save. `git merge`, `git push` and `git rebase` are
# refused at the boundary exactly as before, because the executor may not run them at all,
# boundary or not — they are not in this list and never will be. A harmless `git status`, or
# any command not in this list, is refused exactly like any other call.
#
# HRN-21.C.3: the same closed list also exempts a Bash call running bin/work-log, one more
# entry added the same deliberate way — the boundary must not strand an executor holding the
# one command this system requires it to close its own last step with. That call gets its
# own recognising function, is_phase_boundary_log_call() below, rather than joining this
# git-only one: a real bin/work-log invocation always carries a heredoc body (its own
# stdin — the check's own verbatim output), which legitimately spans many lines, so the bare
# "no newline anywhere" test below cannot apply to it.
PHASE_BOUNDARY_SAVE_GIT_SUBCOMMANDS = ("add", "commit")

# Every quoted span of a shell command — single-quoted, or double-quoted with backslash
# escapes honoured. Blanking these out before looking for chaining is what keeps an
# argument's own contents from being read as shell syntax.
QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", re.S)
CHAINING_RE = re.compile(r'(&&|;|\||\n)')

def chains(command):
    """True when the command runs more than one statement. Judged against the command with
    every quoted span blanked out, because a `;`, `|`, `&&` or newline inside an argument is
    ordinary prose — a handoff entry's own text carries all four — and reading it as shell
    syntax refused exactly the calls this boundary is supposed to let through (found live
    closing HRN-6.C)."""
    return CHAINING_RE.search(QUOTED_SPAN_RE.sub("", command)) is not None

def is_phase_boundary_save_call():
    """True only for a Bash call whose entire command is a single `git add` or `git commit`
    invocation — never a substring or resemblance match. A command that chains more than one
    statement is never exempt, even when one of its parts is itself a bare `git add` or
    `git commit`, since the exemption names one specific action, not a shell script that
    happens to contain it somewhere."""
    if tool_name != "Bash":
        return False
    command = command_of(tool_input)
    if chains(command):
        return False
    m = re.match(r'^\s*git\s+(\S+)', command)
    return m is not None and m.group(1) in PHASE_BOUNDARY_SAVE_GIT_SUBCOMMANDS

# A command invoking one of the three commands that record and land a closed phase, by the
# bare relative path or by any path ending in that same bin/<name> component — never by
# basename alone, so that a path such as ~/elsewhere/work-note is not exempt while
# /abs/path/to/bin/work-note is.
PHASE_BOUNDARY_LOG_CALL_RE = re.compile(r'^\s*(\S*/)?bin/work-(log|note|commit)\b')

def is_phase_boundary_log_call():
    """True only for a Bash call that is a single invocation of bin/work-log — exempted at
    the boundary for the same reason git add/commit already are (HRN-21.A.1), added by
    HRN-21.C.3: writing the log entry that closes a phase is worthless if the very next
    call, the one command this system requires to record it, is itself refused.

    Unlike git add/commit, a real invocation always carries a heredoc body (bin/work-log's
    own stdin, the check's own verbatim output) — legitimately spanning many lines and
    containing any character at all, including `&&`/`;`/`|` — so the plain "no newline
    anywhere" test is_phase_boundary_save_call() applies to git cannot apply here. Chaining
    is instead judged only against the text OUTSIDE the heredoc body: the first line, up to
    its own heredoc marker, carries none of `&&`/`;`/`|` and starts with `bin/work-log`; and
    when a heredoc marker is present, the command's own last line is exactly that marker and
    nothing follows it. A command naming no heredoc marker at all still may not chain,
    exactly like git add/commit.

    The command may name the script by an absolute path as well as by the bare relative one
    (found live closing HRN-6.B): an executor works in its own linked working copy while
    this environment resets every Bash call's own working directory to the shared checkout,
    so the relative form reaches the wrong copy — or no file at all, when the command being
    called is one the card itself is still building — and the only other way of reaching it,
    a `cd` in front, is chaining and refused. Matching is on the path's own trailing
    `bin/work-log`/`bin/work-note` component, never on the basename alone, so a command
    merely mentioning the name somewhere is still not exempt.

    `bin/work-commit` is exempt alongside the two log-writing commands, for the same reason
    and found the same way (closing HRN-6.C): it is what this system puts in place of the
    bare `git add`/`git commit` already exempt here, and an executor that cannot call it at
    the boundary cannot land the work whose closure it has just recorded — as happened, one
    phase after the absolute-path defect above, leaving a finished phase's code stranded
    uncommitted in its own working copy."""
    if tool_name != "Bash":
        return False
    command = command_of(tool_input)
    lines = command.rstrip("\n").split("\n")
    first_line = lines[0]
    heredoc_m = re.search(r'<<-?\s*([\'"]?)(\w+)\1\s*$', first_line)
    if heredoc_m:
        head = first_line[:heredoc_m.start()]
        if CHAINING_RE.search(QUOTED_SPAN_RE.sub("", head)):
            return False
        if PHASE_BOUNDARY_LOG_CALL_RE.match(head) is None:
            return False
        return lines[-1].strip() == heredoc_m.group(2)
    if chains(command):
        return False
    return PHASE_BOUNDARY_LOG_CALL_RE.match(command) is not None

# The two kinds of work a card can belong to, each its own folder directly under the work
# root — identical to bin/work-plan's own KINDS, kept as its own small copy here rather
# than imported, the same way this repository's other git-plumbing helpers each carry their
# own copy (bin/session-start's own repo_root()/primary_worktree_path() comments name the
# same convention).
CARD_KINDS = ("harness", "timeline")

def find_work_root():
    """The directory holding the "harness" and "timeline" kind folders. A card's own folder
    always lives in the shared checkout, never inside a linked worktree's own copy
    (ai/harness/system/project.md, "Папка карточки всегда живёт в общем каталоге, а не в
    копии"), so this is resolved from the shared checkout's own path — `git worktree
    list --porcelain`'s first entry, readable from inside any linked worktree too — not
    from whatever repository copy this call's own cwd happens to sit in. Returns None when
    that cannot be resolved (cwd is not inside a git working tree at all, or git itself is
    unavailable), in which case the phase-boundary rule below is skipped rather than
    denied."""
    override = os.environ.get("WORK_GATE_WORK_ROOT")
    if override:
        return override
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return os.path.join(line[len("worktree "):].strip(), "ai")
    return None

def epic_dirs(work_root):
    found = []
    for kind in CARD_KINDS:
        base = os.path.join(work_root, kind)
        if not os.path.isdir(base):
            continue
        for epic_name in sorted(os.listdir(base)):
            epic_dir = os.path.join(base, epic_name)
            if os.path.isdir(epic_dir):
                found.append(epic_dir)
    return found

def find_card_dir(work_root, card_id):
    for epic_dir in epic_dirs(work_root):
        for card_name in sorted(os.listdir(epic_dir)):
            if card_name == card_id or card_name.startswith(card_id + "_"):
                card_dir = os.path.join(epic_dir, card_name)
                if os.path.isdir(card_dir):
                    return card_dir
    return None

BULLET_RE = re.compile(r'^-\s+\S')
PHASE_HEADING_RE = re.compile(r'^###\s+(\S+)')

def find_section(text, heading_name):
    """The lines of a `## <heading_name>` section, up to the next `## ` heading (never a
    `### ` one, which `^##\\s+\\S` cannot match — the char right after the two hashes of a
    `### ` line is a third hash, not whitespace) or end of file. Empty string when the
    heading is not present at all."""
    lines = text.split("\n")
    start = None
    end = len(lines)
    heading_re = re.compile(r'^##\s+' + re.escape(heading_name) + r'\s*$')
    next_re = re.compile(r'^##\s+\S')
    for i, line in enumerate(lines):
        if start is None and heading_re.match(line):
            start = i + 1
            continue
        if start is not None and next_re.match(line):
            end = i
            break
    if start is None:
        return ""
    return "\n".join(lines[start:end])

def parse_plan_phases(plan_text, card_id):
    """Every phase in plan.md's own "## Шаги" section, in the order the plan itself lists
    them, as (phase_id, step_count) pairs — phase_id being the token right after a "### "
    subheading (e.g. "HRN-2.A"). A plan not split into phases at all — no "### " subheading
    anywhere in the section — is one implicit phase named by the bare card_id, its step
    count the section's own bullet lines."""
    section = find_section(plan_text, "Шаги")
    lines = section.split("\n")
    starts = [i for i, l in enumerate(lines) if PHASE_HEADING_RE.match(l)]
    if not starts:
        return [(card_id, sum(1 for l in lines if BULLET_RE.match(l)))]
    phases = []
    for idx, start in enumerate(starts):
        stop = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        phase_id = PHASE_HEADING_RE.match(lines[start]).group(1)
        steps = sum(1 for l in lines[start + 1:stop] if BULLET_RE.match(l))
        phases.append((phase_id, steps))
    return phases

NAMED_STEP_CLOSED_RE_CACHE = {}

def strip_fenced_blocks(text):
    """Blank out everything between a pair of lines beginning with three backticks — log.md's
    own code fences, which quote a check's verbatim output — before any heading pattern ever
    runs over the text (HRN-6.A.2). A heading-shaped line quoted inside one of these fences
    (part of an earlier entry's own check output, or a handoff's own account of what an older
    log looked like) must never be read as a real, closed step — the exact live defect HRN-5's
    own executor found (ai/harness/work-system/HRN-5_the-handover-command/log.md, line 219)."""
    lines = text.split("\n")
    out = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        out.append(line)
    return "\n".join(out)


def closed_steps_for_phase(log_text, phase_id):
    """The step numbers log.md names closed for one phase, read by name rather than by a
    step's position in plan.md's own list (HRN-2.E). HRN-6.A.2 narrows this to only the one
    form bin/work-plan ever stamps and bin/work-note ever echoes — "## <phase_id>.<N> —
    <state>" — matched per line, never across a newline. HRN-40 requires the same space
    and long dash the stamped form actually carries right after the step number, the
    same requirement bin/work-handover's own STEP_HEADING_RE already puts on the same
    question, so an interim progress note such as "## <phase_id>.<N>-progress — interim:
    ..." is never mistaken for that step's own closing heading. The older, pre-HRN-6.A.2,
    hand-typed "## <phase_id>, шаг <N>" convention is no longer recognised at all, and the
    text is stripped of every fenced code block first, so a heading-shaped line quoted
    verbatim inside a check's own output can never be mistaken for a real one."""
    text = strip_fenced_blocks(log_text)
    named_pattern = NAMED_STEP_CLOSED_RE_CACHE.get(phase_id)
    if named_pattern is None:
        named_pattern = re.compile(
            r'^#{1,6}\s*' + re.escape(phase_id) + r'\.(\d+)\s+—',
            re.MULTILINE,
        )
        NAMED_STEP_CLOSED_RE_CACHE[phase_id] = named_pattern
    closed = set()
    for m in named_pattern.finditer(text):
        closed.add(int(m.group(1)))
    return closed

def total_steps_for_phase(plan_text, card_id, phase_id):
    """The step count plan.md's own "## Шаги" section gives the one phase named phase_id, or
    None when that phase does not appear in the plan at all (including when the plan is not
    split into phases and phase_id is not the bare card_id parse_plan_phases falls back to
    naming)."""
    for pid, total in parse_plan_phases(plan_text, card_id):
        if pid == phase_id:
            return total
    return None

work_root = find_work_root()
card_dir = find_card_dir(work_root, brief["card"]) if work_root else None

if brief.get("role") == "executor" and card_dir is not None:
    fp = file_path_of(tool_input)

    def is_this_cards_log_write():
        # "Read" is exempted alongside "Write"/"Edit" (found live closing HRN-34.B): the
        # Edit tool's own client-side staleness check refuses to edit a file that changed
        # on disk since this session last read it, and log.md is dirtied outside Claude's
        # own file tracking by every bin/work-note call — so with Read still refused at the
        # boundary, Edit could never satisfy its own precondition and the boundary's one
        # designated escape (a Write/Edit of this file) became unreachable via Edit.
        return (tool_name in ("Read", "Write", "Edit") and fp is not None and
                os.path.realpath(fp) == os.path.realpath(os.path.join(card_dir, "log.md")))

    phase_id = brief.get("phase")
    if not phase_id:
        if is_this_cards_log_write():
            allow_and_exit()
        deny_and_exit(
            "Blocked by work-gate's PHASE BOUNDARY rule: this executor's caller-brief "
            "names no phase — an unnamed phase does not exempt a run from the boundary, it "
            "blocks it, exactly like a subagent that carries no caller-brief file at all "
            "(rule 4). Re-launch with bin/work-agent-brief --role executor --card %s "
            "--phase <ID>, naming the phase this run is actually working. The only call "
            "that still gets through is a Write/Edit of this card's own log.md: «допиши "
            "передачу и остановись»." % brief["card"],
            "work-gate.phase-boundary-blocks-unnamed-phase"
        )
    else:
        try:
            with open(os.path.join(card_dir, "plan.md"), "r", encoding="utf-8") as f:
                plan_text = f.read()
        except OSError:
            plan_text = None
        if plan_text is not None:
            total = total_steps_for_phase(plan_text, brief["card"], phase_id)
            if total:
                try:
                    with open(os.path.join(card_dir, "log.md"), "r", encoding="utf-8") as f:
                        log_text = f.read()
                except OSError:
                    log_text = ""
                closed = len(closed_steps_for_phase(log_text, phase_id) & set(range(1, total + 1)))
                if closed >= total:
                    if is_this_cards_log_write() or is_phase_boundary_save_call() or \
                            is_phase_boundary_log_call():
                        allow_and_exit()
                    deny_and_exit(
                        "Blocked by work-gate's PHASE BOUNDARY rule: every step of phase %s "
                        "— the phase this run's own caller-brief names — is already closed "
                        "in log.md, regardless of what any other phase in the plan looks "
                        "like. A fresh executor takes the next phase, not this one. The "
                        "only calls that still get through are a Read/Write/Edit of this "
                        "card's own log.md, a Bash call that does nothing but `git add` or "
                        "`git commit`, and a single, unchained Bash call running "
                        "bin/work-log, bin/work-note or bin/work-commit — saving work "
                        "already done, never starting anything new: «допиши передачу и "
                        "остановись»." % phase_id,
                        "work-gate.phase-boundary-own-phase-closed-later-untouched"
                    )

# --- 6. FILE AUTHORSHIP (HRN-2.B): "one file, one author" ------------------------------
# ai/harness/system/project.md, "Правка чужого файла": the executor may not write
# description.md, attention.md or done.md — each belongs to a different role (the owner via
# the orchestrator, the critic, the acceptor) — and may not write plan.md either, but that
# refusal names question.md instead, per this same document's "Проблема в плане": the
# executor records a proposed change there and keeps working, rather than touching the plan
# itself. The acceptor may not write log.md — that file is the executor's own. Only a call
# that targets a file actually inside THIS card's own folder is judged; card_dir is None
# (skip, fail open) exactly when rule 5 above already treats it as unresolvable.
EXECUTOR_LOCKED_FILES = ("description.md", "attention.md", "done.md")

if tool_name in ("Write", "Edit") and card_dir is not None:
    fp = file_path_of(tool_input)
    if fp is not None:
        real_fp = os.path.realpath(fp)
        real_card_dir = os.path.realpath(card_dir)
        if os.path.dirname(real_fp) == real_card_dir:
            fname = os.path.basename(real_fp)
            role = brief.get("role")
            if role == "executor" and fname == "plan.md":
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: plan.md is not the "
                    "executor's file to write — the orchestrator alone edits the plan. "
                    "Write the proposed change to question.md in this card's own folder "
                    "instead and keep working; the orchestrator watches for that file and "
                    "answers it. «Один файл, один автор.»",
                    "work-gate.file-authorship-plan"
                )
            if role == "executor" and fname in EXECUTOR_LOCKED_FILES:
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: %s is not the executor's "
                    "file to write — «Один файл, один автор». See "
                    "ai/harness/system/project.md, \"Правка чужого файла\"." % fname,
                    "work-gate.file-authorship-executor-locked"
                )
            if role == "acceptor" and fname == "log.md":
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: log.md is not the "
                    "acceptor's file to write — «Один файл, один автор». See "
                    "ai/harness/system/project.md, \"Правка чужого файла\".",
                    "work-gate.file-authorship-acceptor-log"
                )

# --- 7. LOG-WRITE CEILING (HRN-2.B, extended by HRN-21.B): twenty calls without a log.md
# write ------------------------------------------------------------------------------------
# ai/harness/system/project.md, "Двадцать вызовов без записи в log.md": applies only to the
# executor, and only once card_dir is known (fail open otherwise, same reasoning as rule 6 —
# without a resolved log.md path this rule could never recognise the one write meant to
# reset it, and would end up denying that write itself). agent_id is guaranteed present here
# — rule 3 above already exited for any call carrying none, so every call that reaches this
# point is a real subagent's own. The count lives in its own state file, one per agent_id,
# keyed the same way the brief files already are; a call denied by an earlier rule (FITNESS,
# no-brief, phase boundary, file authorship) never reaches here and so neither increments
# nor resets it.
#
# HRN-21.B: the system requires the executor to write log.md only through `bin/work-log`,
# never by hand (ai/harness/system/project.md, "log.md — пишет исполнитель"), and that
# command runs through Bash — so a bare Bash call naming it is exempted the same way rule 2
# above already exempts a Bash call naming `bin/work-refusals`: a closed, literal match on
# the script's own basename appearing anywhere in the command line, never a chain-aware
# parse. Exempting it is not enough on its own — a call that merely passes the ceiling but
# still counts toward it would still eventually starve the executor of the one command it
# needs — so this same call also resets the counter to zero, exactly like a direct Write/Edit
# of log.md, because a `bin/work-log` invocation IS that write, only spelled through a
# command rather than through the tool directly.
LOG_CALL_CEILING = 20

def log_call_count_path(aid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    return os.path.join(STATE_DIR, "log-call-counts", "agent-" + safe + ".txt")

def read_log_call_count(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0

def write_log_call_count(path, n):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(n))

if brief.get("role") == "executor" and card_dir is not None:
    fp = file_path_of(tool_input)
    is_this_cards_log_write_now = (
        tool_name in ("Write", "Edit") and fp is not None and
        os.path.realpath(fp) == os.path.realpath(os.path.join(card_dir, "log.md"))
    )
    is_work_log_call = tool_name == "Bash" and (
        bash_names(command_of(tool_input), "work-log") or
        bash_names(command_of(tool_input), "work-note"))
    count_path = log_call_count_path(agent_id)
    if is_this_cards_log_write_now or is_work_log_call:
        write_log_call_count(count_path, 0)
    else:
        n = read_log_call_count(count_path) + 1
        write_log_call_count(count_path, n)
        if n >= LOG_CALL_CEILING:
            deny_and_exit(
                "Blocked by work-gate's LOG CEILING rule: %d calls have passed since this "
                "executor last wrote to this card's own log.md — record state there now. "
                "The only call that still gets through is a Write/Edit of log.md, or a Bash "
                "call running bin/work-log or bin/work-note, any of which resets this count "
                "to zero. This ceiling does not end the run: it exists so that a run cut "
                "short stays resumable, so write the state and go straight on with the work. "
                "«Запиши состояние в лог и работай дальше.»" % n,
                "work-gate.log-ceiling"
            )

# --- shared by rules 8-11 below: "is this call a Write/Edit of THIS run's own card's
# log.md" — the same test rules 5 and 7 above each already define locally for their own
# narrower scopes, repeated here as its own top-level helper rather than factored out of
# that already-built code, since this phase's own brief is to add HRN-2.C's five steps and
# nothing beyond them. -------------------------------------------------------------------
def is_this_cards_log_write_call():
    fp = file_path_of(tool_input)
    return (tool_name in ("Write", "Edit") and fp is not None and card_dir is not None and
            os.path.realpath(fp) == os.path.realpath(os.path.join(card_dir, "log.md")))

# --- shared by rules 8-10: one walk of this run's own transcript ----------------------
def transcript_line_records(path):
    """Yield each JSON object from a transcript file, one per line, skipping a blank or
    unparseable one — the same tolerant walk bin/agent-spend's own measure()/load_calls()
    already use for the identical file format (a Claude Code session transcript), repeated
    here rather than imported: this hook has no import path to bin/, which lives in a
    different repository."""
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                yield record

def run_transcript_stats(path):
    """One walk of this run's own transcript, answering everything rules 8-10 below need:
    last_context — the context size the agent's own MOST RECENT turn actually held
    (input_tokens + cache_creation_input_tokens + cache_read_input_tokens of the last
    assistant record alone, never summed across the run — rule 8's own number); spend —
    the run's cumulative spend so far (cache_read_input_tokens + output_tokens, summed
    across every assistant record — the same definition bin/agent-spend's own emit_spend()
    already uses for a card's `spend:` field, reused here rather than invented fresh —
    rule 9's own number); calls — the number of tool calls the run has made (one per
    tool_use content block, the same count bin/agent-spend's own measure() already uses —
    rule 10's own denominator). None when path is missing, unreadable, or carries not one
    assistant record with a usage field at all — rules 8-10 then have nothing to judge and
    skip rather than deny, the same fail-open choice every earlier rule in this file
    already makes for a missing or unreadable input."""
    if not path:
        return None
    last_context = None
    spend = 0
    calls = 0
    seen_usage = False
    for record in transcript_line_records(path):
        if record.get("type") != "assistant":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        if usage:
            seen_usage = True
        u_input = usage.get("input_tokens", 0) or 0
        u_cwrite = usage.get("cache_creation_input_tokens", 0) or 0
        u_cread = usage.get("cache_read_input_tokens", 0) or 0
        u_output = usage.get("output_tokens", 0) or 0
        last_context = u_input + u_cwrite + u_cread
        spend += u_cread + u_output
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls += 1
    if not seen_usage:
        return None
    return {"last_context": last_context, "spend": spend, "calls": calls}

transcript_path = data.get("transcript_path")
run_stats = run_transcript_stats(transcript_path)

# --- 8. CONTEXT SIZE CEILING (HRN-2.C): every role -------------------------------------
CONTEXT_SIZE_CEILING = 300_000

if run_stats is not None and run_stats["last_context"] is not None and \
        run_stats["last_context"] > CONTEXT_SIZE_CEILING:
    if is_this_cards_log_write_call():
        allow_and_exit()
    deny_and_exit(
        "Blocked by work-gate's CONTEXT SIZE rule: this agent's own most recent turn held "
        "%d tokens of context, past the %d ceiling. «Запиши состояние в лог и остановись.» "
        "A fresh executor picks the card up from there with an empty context. The only "
        "call that still gets through is a Write/Edit of this card's own log.md." %
        (run_stats["last_context"], CONTEXT_SIZE_CEILING),
        "work-gate.context-size"
    )

# --- 9. SPEND CEILING (HRN-2.C): role "executor" only, counted on this run's own
# transcript alone, never accumulated across the card ------------------------------------
SPEND_CEILING = 90_000_000

if brief.get("role") == "executor" and run_stats is not None and \
        run_stats["spend"] > SPEND_CEILING:
    if is_this_cards_log_write_call():
        allow_and_exit()
    deny_and_exit(
        "Blocked by work-gate's SPEND CEILING rule: this executor's own run has spent %d "
        "tokens (cache-read plus output, summed from its own transcript), past the %d "
        "ceiling counted for this run alone, never accumulated across the whole card — a "
        "fresh executor's own transcript starts this same count at zero. «Запиши "
        "состояние в лог и остановись.» The only call that still gets through is a "
        "Write/Edit of this card's own log.md." % (run_stats["spend"], SPEND_CEILING),
        "work-gate.spend-ceiling"
    )

# --- 10. PACE CEILING (HRN-2.C): role "executor" only, tokens spent per tool call this
# run has made, threshold read from a machine file, not checked before call 120 ----------
PACE_CALL_ALLOWANCE = 120

def pace_threshold_file():
    return os.environ.get("WORK_GATE_PACE_THRESHOLD_FILE") or \
        os.path.join(os.path.dirname(self_path), "work-gate-pace-threshold.txt")

def read_pace_threshold():
    try:
        with open(pace_threshold_file(), "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None

if brief.get("role") == "executor":
    pace_threshold = read_pace_threshold()
    if pace_threshold is None:
        if is_this_cards_log_write_call():
            allow_and_exit()
        deny_and_exit(
            "Blocked by work-gate's PACE rule: no number was found at %s — the pace "
            "threshold this rule judges every call against must live there as a bare "
            "integer, and its absence refuses every call for this executor rather than "
            "silently skipping the check. The only call that still gets through is a "
            "Write/Edit of this card's own log.md." % pace_threshold_file(),
            "work-gate.pace-threshold-missing"
        )
    elif run_stats is not None and run_stats["calls"] > PACE_CALL_ALLOWANCE:
        pace = run_stats["spend"] / run_stats["calls"]
        if pace > pace_threshold:
            if is_this_cards_log_write_call():
                allow_and_exit()
            deny_and_exit(
                "Blocked by work-gate's PACE rule: this run has spent %.0f tokens per "
                "tool call (%d tokens over %d calls), past the %d threshold read from %s. "
                "«Запиши состояние в лог и остановись.» The only call that still gets "
                "through is a Write/Edit of this card's own log.md." %
                (pace, run_stats["spend"], run_stats["calls"], pace_threshold,
                 pace_threshold_file()),
                "work-gate.pace-ceiling"
            )

# --- 11. FILE-EDIT BRAKE (HRN-2.C): the Nth Edit/Write of one file inside one run -------
FILE_EDIT_BRAKE_THRESHOLD = 9

def file_edit_count_path(aid, real_fp):
    safe_agent = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    safe_file = re.sub(r'[^A-Za-z0-9_-]', '_', real_fp)
    return os.path.join(STATE_DIR, "file-edit-counts", "agent-" + safe_agent,
                         safe_file + ".txt")

def read_file_edit_count(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0

def write_file_edit_count(path, n):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(n))

def file_created_marker_path(aid, real_fp):
    return file_edit_count_path(aid, real_fp) + ".created"

def mark_file_created_this_run(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("1")

if tool_name in ("Write", "Edit"):
    fp = file_path_of(tool_input)
    if fp is not None:
        real_fp = os.path.realpath(fp)
        is_card_file = card_dir is not None and \
            os.path.dirname(real_fp) == os.path.realpath(card_dir)
        # HRN-21.C.1: a Write that brings a file into existence — one that does not yet
        # exist on disk at the moment this hook runs, before the tool call itself executes
        # — is a creation, not a "правка" (edit) of anything, and is never counted at all.
        # Checked fresh against the filesystem on every call, never remembered as a flag of
        # its own: the next Write/Edit of this same path finds the file now on disk (this
        # call's own effect, once it actually runs) and counts normally from there.
        is_fresh_creation = tool_name == "Write" and not os.path.exists(real_fp)
        # The brake exists to catch an agent hammering code that was already on disk when
        # its run began. A file this same run brought into existence is not that: an agent
        # authoring a new script honestly edits it a dozen times, and refusing that stops
        # real work while catching nothing. So the creation lays down a marker for this
        # (run, path) pair, and every later Write/Edit of that path inside the same run is
        # left uncounted. The run stays bounded either way — the spend, context and pace
        # ceilings all still apply to it.
        created_marker = file_created_marker_path(agent_id, real_fp)
        if is_fresh_creation:
            mark_file_created_this_run(created_marker)
        was_created_this_run = os.path.exists(created_marker)
        if not is_card_file and not is_fresh_creation and not was_created_this_run:
            count_path = file_edit_count_path(agent_id, real_fp)
            n = read_file_edit_count(count_path) + 1
            write_file_edit_count(count_path, n)
            if n >= FILE_EDIT_BRAKE_THRESHOLD:
                deny_and_exit(
                    "Blocked by work-gate's FILE-EDIT BRAKE rule: this run has now edited "
                    "%s %d times, past the %d threshold. A whole-file Write is counted the "
                    "same as a point edit, so there is no way to keep working on this one "
                    "file in this run: either move on to other work, or record the state "
                    "with bin/work-note and hand the file's remaining work to a fresh run. "
                    "This count is per file path and per run; it never counts a write to one "
                    "of this card's own files, and a Bash call re-running the same "
                    "command however many times is never limited at all." %
                    (fp, n, FILE_EDIT_BRAKE_THRESHOLD),
                    "work-gate.file-edit-brake"
                )

allow_and_exit()
PYEOF
