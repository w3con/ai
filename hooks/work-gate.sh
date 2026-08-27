#!/usr/bin/env bash
# work-gate.sh — PreToolUse hook: the enforcement backbone of the new work-management
# system (HRN-2, ai/harness/system/project.md, "Хук на вызов инструмента", in the
# validite-app repository). A rule that used to live only in prose becomes a rule nobody can
# break by accident, because the tool call itself is refused.
#
# This file currently builds phases HRN-2.A (the fitness guard and caller identity),
# HRN-2.B (one-file-one-author and the log-write ceiling), HRN-2.D/F (the phase boundary,
# judged against the run's own named phase) and HRN-2.E's own rewrite of closed_steps_for_phase
# to read a step's closure by its permanent name rather than only the older free-form "шаг N"
# convention — not HRN-2.C (the context/spend/pace ceilings and the file-edit brake), built by
# a separate run.
#
# WHAT THIS FILE DOES, IN THE ORDER IT DOES IT
#
#  1. Bypass: CLAUDE_GATE_BYPASS=1 disables every rule below, the same escape hatch the
#     other hooks in this directory share (memory-store-guard.sh, plan-gate.sh,
#     card-touch-gate.sh).
#
#  2. FITNESS: every call is refused — the coordinator's own included — unless
#     bin/work-refusals has passed against this exact file since it was last edited.
#     bin/work-refusals itself lays down the fingerprint on a full pass (writes the SHA-256
#     of hooks/work-gate.sh's own bytes to WORK_GATE_STATE_DIR/verified-hash.txt); this hook
#     only ever compares its own current hash against that marker. Three things get through
#     regardless, because without them a broken gate could never be repaired: running
#     bin/work-refusals itself, an Edit/Write of this file, and a Write/Edit of any card's
#     own log.md.
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
# STATE. Everything this hook remembers between calls lives under WORK_GATE_STATE_DIR
# (default "${TMPDIR:-/tmp}/claude-work-gate", the convention hooks/card-touch-gate.sh
# already uses for its own per-agent state): verified-hash.txt (rule 2, written by
# bin/work-refusals, read only here) and briefs/agent-<agent_id>.json /
# briefs/session-<session_id>.json (rule 4). Rule 5 keeps no state of its own — it re-reads
# plan.md and log.md fresh on every call.
#
# TEST OVERRIDES, read only by bin/work-refusals, never present in a real deployed session:
#   WORK_GATE_STATE_DIR   overrides the whole state tree above.
#   WORK_GATE_WORK_ROOT   overrides the work root rule 5 resolves a card id against (the
#                         directory holding the "harness" and "timeline" kind folders,
#                         normally found via `git worktree list --porcelain`'s own first
#                         entry — the shared checkout's path, since a card's folder always
#                         lives there and never inside a linked worktree's own copy).
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

def deny_and_exit(reason):
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
    deny_and_exit("Blocked by work-gate: gate error (unreadable hook payload), failing closed.")

tool_name  = data.get("tool_name") or ""
tool_input = data.get("tool_input") or {}
agent_id   = data.get("agent_id")
session_id = data.get("session_id") or ""

STATE_DIR = os.environ.get("WORK_GATE_STATE_DIR") or \
    os.path.join(os.environ.get("TMPDIR", "/tmp"), "claude-work-gate")
BRIEFS_DIR = os.path.join(STATE_DIR, "briefs")
HASH_MARKER = os.path.join(STATE_DIR, "verified-hash.txt")

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

# --- 2. FITNESS: the suite must have passed against this exact file since its last edit -
def own_hash():
    try:
        with open(self_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None

def stored_hash():
    try:
        with open(HASH_MARKER, "r", encoding="utf-8") as f:
            return f.readline().strip()
    except OSError:
        return None

is_refusals_run = tool_name == "Bash" and bash_names(command_of(tool_input), "work-refusals")
is_gate_self_edit = tool_name in ("Write", "Edit") and \
    file_path_of(tool_input) is not None and \
    os.path.realpath(file_path_of(tool_input)) == self_path
is_log_write = tool_name in ("Write", "Edit") and \
    file_path_of(tool_input) is not None and \
    LOG_FILE_RE.search(file_path_of(tool_input).replace(os.sep, "/")) is not None

current = own_hash()
verified = stored_hash()
fitness_ok = current is not None and verified is not None and current == verified

if not fitness_ok:
    if is_refusals_run or is_gate_self_edit or is_log_write:
        allow_and_exit()
    deny_and_exit(
        "Blocked by work-gate's FITNESS rule: this hook's own file has changed since "
        "bin/work-refusals last passed against it, and a gate that might be broken stops "
        "every call rather than failing silently. Run bin/work-refusals to clear this; "
        "while it stands, the only calls that still get through are that run itself, an "
        "Edit/Write of hooks/work-gate.sh, and a Write/Edit of any card's own log.md. Set "
        "CLAUDE_GATE_BYPASS=1 only for a deliberate, known exception."
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
        (agent_brief_path(agent_id), session_brief_path(session_id))
    )

# --- 5. PHASE BOUNDARY: an executor whose current phase has no open steps left is refused
# every call except a Write/Edit of its own card's log.md (HRN-2.D) --------------------

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

STEP_CLOSED_RE_CACHE = {}
NAMED_STEP_CLOSED_RE_CACHE = {}

def closed_steps_for_phase(log_text, phase_id):
    """The step numbers log.md names closed for one phase, read by name rather than by a
    step's position in plan.md's own list (HRN-2.E) — two independent forms of heading are
    matched and their results combined:
      - the mechanical form bin/work-log itself prints, "## <phase_id>.<N> — <state>": the
        step's own permanent name (bin/work-plan's own stamp), matched literally.
      - the older, hand-typed form HRN-2.A's own executor established before bin/work-log
        existed, "## <phase_id>, шаг <N>" or "…, шаг <N>–<M>" (en dash) — still read
        unchanged, so a log written before this command existed keeps working.
    Both are matched per line, never across a newline, so a heading with nothing after the
    step numbers is still read correctly."""
    pattern = STEP_CLOSED_RE_CACHE.get(phase_id)
    if pattern is None:
        pattern = re.compile(
            r'^#{1,6}\s*' + re.escape(phase_id) + r'\s*,\s*шаг\s+([0-9][0-9,–\- ]*)',
            re.MULTILINE,
        )
        STEP_CLOSED_RE_CACHE[phase_id] = pattern
    named_pattern = NAMED_STEP_CLOSED_RE_CACHE.get(phase_id)
    if named_pattern is None:
        named_pattern = re.compile(
            r'^#{1,6}\s*' + re.escape(phase_id) + r'\.(\d+)\b',
            re.MULTILINE,
        )
        NAMED_STEP_CLOSED_RE_CACHE[phase_id] = named_pattern
    closed = set()
    for m in pattern.finditer(log_text):
        for token in re.split(r'[,\s]+', m.group(1).strip()):
            if not token:
                continue
            if "–" in token or "-" in token:
                parts = re.split(r'[–\-]', token)
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    closed.update(range(int(parts[0]), int(parts[1]) + 1))
            elif token.isdigit():
                closed.add(int(token))
    for m in named_pattern.finditer(log_text):
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
        return (tool_name in ("Write", "Edit") and fp is not None and
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
            "передачу и остановись»." % brief["card"]
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
                    if is_this_cards_log_write():
                        allow_and_exit()
                    deny_and_exit(
                        "Blocked by work-gate's PHASE BOUNDARY rule: every step of phase %s "
                        "— the phase this run's own caller-brief names — is already closed "
                        "in log.md, regardless of what any other phase in the plan looks "
                        "like. A fresh executor takes the next phase, not this one. The "
                        "only call that still gets through is a Write/Edit of this card's "
                        "own log.md: «допиши передачу и остановись»." % phase_id
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
                    "answers it. «Один файл, один автор.»"
                )
            if role == "executor" and fname in EXECUTOR_LOCKED_FILES:
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: %s is not the executor's "
                    "file to write — «Один файл, один автор». See "
                    "ai/harness/system/project.md, \"Правка чужого файла\"." % fname
                )
            if role == "acceptor" and fname == "log.md":
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: log.md is not the "
                    "acceptor's file to write — «Один файл, один автор». See "
                    "ai/harness/system/project.md, \"Правка чужого файла\"."
                )

# --- 7. LOG-WRITE CEILING (HRN-2.B): twenty calls without a log.md write ---------------
# ai/harness/system/project.md, "Двадцать вызовов без записи в log.md": applies only to the
# executor, and only once card_dir is known (fail open otherwise, same reasoning as rule 6 —
# without a resolved log.md path this rule could never recognise the one write meant to
# reset it, and would end up denying that write itself). agent_id is guaranteed present here
# — rule 3 above already exited for any call carrying none, so every call that reaches this
# point is a real subagent's own. The count lives in its own state file, one per agent_id,
# keyed the same way the brief files already are; a call denied by an earlier rule (FITNESS,
# no-brief, phase boundary, file authorship) never reaches here and so neither increments
# nor resets it.
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
    count_path = log_call_count_path(agent_id)
    if is_this_cards_log_write_now:
        write_log_call_count(count_path, 0)
    else:
        n = read_log_call_count(count_path) + 1
        write_log_call_count(count_path, n)
        if n >= LOG_CALL_CEILING:
            deny_and_exit(
                "Blocked by work-gate's LOG CEILING rule: %d calls have passed since this "
                "executor last wrote to this card's own log.md — record state there now. "
                "The only call that still gets through is a Write/Edit of log.md, which "
                "resets this count to zero. «Запиши состояние в лог и остановись.»" % n
            )

allow_and_exit()
PYEOF
