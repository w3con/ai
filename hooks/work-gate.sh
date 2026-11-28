#!/usr/bin/env bash
# work-gate.sh is a PreToolUse hook. It reads one JSON hook payload from stdin and emits
# one JSON allow or deny decision on stdout; malformed input is denied when the gate applies.
# The work-management policy is inactive unless optional private configuration enables it.
# When enabled, the hook checks spawn sanctions, agent briefs, task ownership, and write
# boundaries before applying transcript, call-count, pace, and repeated-edit limits.
# Session calls retain their configured allow behavior; subagent decisions follow the rules.
# Per-run state is stored under WORK_GATE_STATE_DIR or ${TMPDIR:-/tmp}/claude-work-gate.
# WORK_GATE_WORK_ROOT, WORK_GATE_CARD_WORKTREE_ROOT, and WORK_GATE_PACE_THRESHOLD_FILE
# provide configured test overrides for work-root, linked-copy, and pace-threshold lookups.
# Set CLAUDE_GATE_BYPASS=1 to bypass every gate rule.

STDIN_DATA="$(cat)"
# Passed to Python as-is; Python resolves it to the real underlying file with
# os.path.realpath() — see the comment on self_path below for why plain string handling
# here is not enough (~/.claude/hooks/ is itself a symlinked directory, and neither `cd
# "$(dirname ...)" && pwd` nor a hand-rolled `[ -L ]` loop over just the final path
# component follows a symlinked *directory* component, only a symlinked final file).
SELF_PATH="${BASH_SOURCE[0]}"

exec python3 - "$SELF_PATH" "$STDIN_DATA" <<'PYEOF'
import glob
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys

# realpath(), not just the literal argv value: ~/.claude/hooks/ is itself a symlinked
# directory (bin/bootstrap.sh points it at this file's real repository path), and Claude
# Code always invokes this hook through that deployed, symlinked path — never through the
# real repository path directly. Without resolving through the directory symlink here, the
# self-edit exemption below (which compares this value against the file_path an Edit/Write
# call names, always the real repository path) would never match a live invocation, only
# a synthetic case running bash directly against the real path, which never exercises the
    # Resolve the deployed hook path through any symlinked directory components.
self_path  = os.path.realpath(sys.argv[1])
stdin_data = sys.argv[2]

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

def allow_and_exit(reason=None):
    # Allow explanations use additional context; an empty explanation preserves the
    # standard allow payload.
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": reason,
            }
        }))
    else:
        print(ALLOW_JSON)
    sys.exit(0)

# Task-management enforcement is an optional private adapter. A clean public install
# has no task-system assumptions and therefore does not activate this gate. The full
# legacy decision engine below remains available when explicitly enabled in private
# configuration; no policy is inferred from a repository name or remote address.
toolkit_root = os.path.dirname(os.path.dirname(self_path))
try:
    sys.path.insert(0, toolkit_root)
    from lib.private_config import load as load_private_config
    work_management_config = load_private_config(toolkit_root).get("work_management", {})
except Exception:
    work_management_config = {}
if not isinstance(work_management_config, dict) or work_management_config.get("enabled") is not True:
    allow_and_exit()

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
    """Record a refusal when the configured journal is available; never raise."""
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
    """Track consecutive denials by rule and journal repeated failures best-effort."""
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
                text = ("hooks/work-gate.sh: agent %s was denied three times in a row "
                        "by rule %s." % (aid, rule))
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

STATE_DIR = os.environ.get("WORK_GATE_STATE_DIR") or \
    os.path.join(os.environ.get("TMPDIR", "/tmp"), "claude-work-gate")
BRIEFS_DIR = os.path.join(STATE_DIR, "briefs")
SANCTIONS_DIR = os.path.join(STATE_DIR, "sanctions")

# --- 1b. scope: only the repository that carries the work-management system ------------
# Scope is structural: a repository must contain real work-management directories, or
# the current session must have a sanction that identifies a configured work root.
def _session_has_work_root_sanction(sid):
    try:
        safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(sid)) if sid else "_no_session_id_"
        d = os.path.join(SANCTIONS_DIR, safe)
        for name in os.listdir(d):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(d, name), "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict) and obj.get("work_root"):
                root = obj["work_root"]
                for kind in ("harness", "timeline"):
                    d2 = os.path.join(root, kind)
                    if os.path.isdir(d2) and not os.path.islink(d2):
                        return True
    except Exception:
        return False
    return False

def work_management_repo(session_id_for_scope):
    override = os.environ.get("WORK_GATE_SCOPE")
    if override in ("on", "off"):
        return override == "on"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        result = None
    if result is not None and result.returncode == 0:
        root = result.stdout.strip()
        if root:
            ok = True
            for kind in ("harness", "timeline"):
                d = os.path.join(root, "ai", kind)
                if not os.path.isdir(d) or os.path.islink(d):
                    ok = False
                    break
            if ok:
                return True
    return _session_has_work_root_sanction(session_id_for_scope)

# Throwaway, best-effort parse — its only purpose is the session id the scope check above
# needs. The real, fail-closed parse of stdin_data below is untouched and stays the one every
# other rule in this file relies on.
try:
    _scope_data = json.loads(stdin_data)
    if not isinstance(_scope_data, dict):
        _scope_data = {}
except Exception:
    _scope_data = {}
_scope_session_id = _scope_data.get("session_id") or ""

if not work_management_repo(_scope_session_id):
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

# Match the work log in the supported work-management directory layout.
LOG_FILE_RE = re.compile(r'/ai/(?:harness|timeline)/[^/]+/[^/]+/log\.md$')

def file_path_of(ti):
    fp = ti.get("file_path")
    return fp if isinstance(fp, str) and fp else None

def command_of(ti):
    cmd = ti.get("command")
    return cmd if isinstance(cmd, str) else ""

# Every quoted span of a shell command — single-quoted, or double-quoted with backslash
# escapes honoured — blanked out before this hook looks for a chain separator or a program
# name, so a `|`, `;`, `&&`, newline or a command's own name, when it merely sits inside a
# quoted argument or a heredoc body's own prose, is never read as shell syntax. Defined here,
# ahead of its own canonical home a few hundred lines down (next to chains(), which still
# reads it from there), because bash_names() below needs it and this script runs top to
# bottom: bash_names() is first called at this run's own line judging the brief-writing
# command, hundreds of lines before chains() is ever reached.
QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", re.S)

# A leading run of environment-variable assignments, or a bare `env` naming them, standing in
# front of the program word — `FOO=bar bin/work-note …`, `env FOO=bar bin/work-note …` — is
# skipped when looking for that word, so a command written either way still names its program.
_ENV_ASSIGNMENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=\S*$')

def bash_names(command, script_basename):
    """Return whether a command segment invokes the requested executable."""
    lines = command.rstrip("\n").split("\n")
    first_line = lines[0]
    heredoc_m = re.search(r'<<-?\s*([\'"]?)(\w+)\1\s*$', first_line)
    text = first_line[:heredoc_m.start()] if heredoc_m else command
    bare = QUOTED_SPAN_RE.sub("", text)
    for segment in re.split(r'&&|\|\||[;|\n]', bare):
        tokens = segment.split()
        i = 0
        while i < len(tokens) and (tokens[i] == "env" or _ENV_ASSIGNMENT_RE.match(tokens[i])):
            i += 1
        if i < len(tokens) and os.path.basename(tokens[i]) == script_basename:
            return True
    return False

CARD_KINDS = ("harness", "timeline")

def find_work_root(card_id=None):
    """Resolve the shared work root, preferring explicit overrides and sanctions."""
    override = os.environ.get("WORK_GATE_WORK_ROOT")
    if override:
        return override
    if card_id:
        sanction = matching_sanction(card_id)
        if sanction and sanction.get("work_root"):
            return sanction["work_root"]
        agent_wr = _agent_brief_work_root(card_id, agent_id)
        if agent_wr:
            return agent_wr
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

def find_card_worktree_root(card_id):
    """Resolve the linked worktree for a card from its branch name."""
    override = os.environ.get("WORK_GATE_CARD_WORKTREE_ROOT")
    if override:
        return override
    sanction = matching_sanction(card_id)
    if sanction and sanction.get("worktree_path"):
        return sanction["worktree_path"]
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    target_branch = "refs/heads/work/" + card_id.lower()
    current_path = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):].strip()
        elif line.startswith("branch "):
            if line[len("branch "):].strip() == target_branch and current_path:
                return current_path
    return None

def declared_repos_beyond_primary(card_id):
    """Return configured repositories beyond the card's primary repository."""
    sanction = matching_sanction(card_id)
    if not sanction:
        return []
    repos = sanction.get("code_repos")
    if not isinstance(repos, list) or len(repos) <= 1:
        return []
    return [str(r) for r in repos[1:]]

def find_repo_worktree_root(repo, card_id):
    """The same resolution find_card_worktree_root() performs, scoped to `repo` alone via
    `git -C <repo> worktree list --porcelain` rather than this hook's own default cwd — so a
    declared second repository's own linked working copy is found on its own terms, never by
    accident inheriting whatever repository the hook process happens to be sitting in. None on
    any failure to run git there at all, or when no worktree of `repo` carries this card's own
    branch."""
    try:
        result = subprocess.run(
            ["git", "-C", repo, "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    target_branch = "refs/heads/work/" + card_id.lower()
    current_path = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):].strip()
        elif line.startswith("branch "):
            if line[len("branch "):].strip() == target_branch and current_path:
                return current_path
    return None

# --- 2. Executor spawn sanctions -------------------------------------------------------
def sanctions_dir(sid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(sid)) if sid else "_no_session_id_"
    return os.path.join(SANCTIONS_DIR, safe)

def read_sanctions(sid):
    """Read valid sanction records from the current session's state directory."""
    d = sanctions_dir(sid)
    result = []
    try:
        names = sorted(os.listdir(d))
    except Exception:
        return result
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, name), "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        if isinstance(obj, dict):
            result.append(obj)
    return result

def matching_sanction(card_id):
    """Return the newest session sanction matching a card identifier."""
    if not card_id:
        return None
    try:
        candidates = [s for s in read_sanctions(session_id) if s.get("card") == card_id]
    except Exception:
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda c: c.get("time") or 0, reverse=True)
    return candidates[0]

TERMINAL_STATE_FILES = ("done.md", "cancelled.md", "rejected.md", "question.md")

def sanction_card_is_terminal(card_id):
    """Return whether the card has a terminal-state marker, or None if unresolved."""
    try:
        root = find_work_root(card_id)
        if root is None:
            return None
        card_dir = find_card_dir(root, card_id)
        if card_dir is None:
            return None
        return any(os.path.isfile(os.path.join(card_dir, fname))
                    for fname in TERMINAL_STATE_FILES)
    except Exception:
        return None

DENY_NO_SANCTION = (
    "Blocked by work-gate: no sanction on file for this session raising an executor "
    "subagent — call bin/work-handover <ID> for a fresh phase, or bin/work-resume <ID> "
    "for an interrupted one, and let it print the executor's own brief before spawning "
    "the executor with it."
)

# --- 2b. One active task per conversation ----------------------------------------------
ONE_TASK_STATE_DIR = os.path.join(STATE_DIR, "one-task")

def one_task_state_path(transcript_path):
    """None when there is no transcript_path to key state on — this rule then has nothing
    to judge and falls through to an allow, the same fail-open posture card-touch-gate.sh's
    own COORD rule already takes when it cannot establish a session identifier."""
    if not transcript_path:
        return None
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', os.path.basename(str(transcript_path)))
    return os.path.join(ONE_TASK_STATE_DIR, safe + ".json")

SECOND_TASK_TEMPLATE = (
    "Blocked by work-gate: this conversation already sanctioned an executor on {owned}, and "
    "this spawn's own sanction names a different card, {attempted}. One conversation runs "
    "one task: finish the current task and close this conversation with /clear before "
    "starting the next one, or, when the two pieces of work genuinely must run at the same "
    "time, open a separate session with /parallel instead of spawning a second executor here."
)

def owned_card_is_closed(card_id):
    """Return whether an active task has a completion or cancellation marker."""
    try:
        root = find_work_root(card_id)
        if root is None:
            return None
        card_dir = find_card_dir(root, card_id)
        if card_dir is None:
            return None
        return os.path.isfile(os.path.join(card_dir, "done.md")) or \
            os.path.isfile(os.path.join(card_dir, "cancelled.md"))
    except Exception:
        return None

def second_task_deny_reason(card, transcript_path):
    """Return a denial reason when another active task occupies this session."""
    try:
        state_path = one_task_state_path(transcript_path)
        if not state_path:
            return None
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
            os.makedirs(ONE_TASK_STATE_DIR, exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"card": card}, f)
            return None
        if owned == card:
            return None
        closed = owned_card_is_closed(owned)
        if closed is None:
            return None  # a reading error of this check's own — never a reason to deny
        if closed:
            os.makedirs(ONE_TASK_STATE_DIR, exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"card": card}, f)
            return None
        return SECOND_TASK_TEMPLATE.format(owned=owned, attempted=card)
    except Exception:
        return None
# --- end 2b -----------------------------------------------------------------------------

if not agent_id and tool_name in ("Task", "Agent") and \
        (tool_input.get("subagent_type") or "").strip() == "executor":
    prompt_text = ((tool_input.get("prompt") or "") + " " +
                   (tool_input.get("description") or ""))
    # Match the newest sanctioned card named in the spawn prompt; ignore terminal cards.
    matched_sanction = None
    for candidate in sorted(read_sanctions(session_id),
                            key=lambda c: c.get("time") or 0, reverse=True):
        card = candidate.get("card")
        if card and card in prompt_text and not sanction_card_is_terminal(card):
            matched_sanction = candidate
            break
    if matched_sanction is None:
        deny_and_exit(DENY_NO_SANCTION, "work-gate.no-sanction-executor-spawn")
    matched_card = matched_sanction.get("card")
    matched_estimate = matched_sanction.get("estimate")
    matched_short = bool(matched_sanction.get("short"))
    # Short tasks with supported estimates do not occupy the session's active-task slot.
    if not (matched_short or (isinstance(matched_estimate, int) and matched_estimate in (1, 2))):
        second_reason = second_task_deny_reason(matched_card, data.get("transcript_path"))
        if second_reason is not None:
            deny_and_exit(second_reason, "work-gate.second-task-in-conversation")

# --- 3. Session call counters ----------------------------------------------------------
COORD_CALL_CEILING = 761  # card-touch-gate.sh's own COORD_CEILING
SEARCH_AGENT_RAISE_CEILING = 28  # card-touch-gate.sh's own SEARCH_AGENT_CEILING
SEARCH_AGENT_ROLE_TYPES = {"Explore", "Plan", "trace-audit"}  # plan-gate.sh's own
                                                               # ALLOWLISTED_SUBTYPES

COORD_CALLS_DIR = os.path.join(STATE_DIR, "coord-calls")
SEARCH_AGENT_RAISES_DIR = os.path.join(STATE_DIR, "search-agent-raises")

COORD_COUNT_WARN_TEMPLATE = (
    "work-gate's COORD count: this coordinator session has made {count} tool calls, past its "
    "own watched ceiling of {ceiling} (carried over from the retired card-touch-gate.sh's own "
    "COORD rule). This is a count, not a refusal — the call still passes."
)

SEARCH_AGENT_RAISE_WARN_TEMPLATE = (
    "work-gate's SEARCH-AGENT count: this session has raised {count} reading agents "
    "(subagent_type={agent_type} included), past its own watched ceiling of {ceiling} "
    "(carried over from the retired card-touch-gate.sh's own SEARCH-AGENT rule). This is a "
    "count, not a refusal — the spawn still passes."
)

def _sanitized_transcript_token(transcript_path):
    if not transcript_path:
        return None
    return re.sub(r'[^A-Za-z0-9_-]', '_', os.path.basename(str(transcript_path)))

def _bump_counter(dir_path, token, field):
    """Best-effort increment-and-read of a per-token counter file; never raises — returns the
    new count (starting at 1) on success, None when the count cannot be established at all,
    the same fail-open posture every other rule in this file already takes."""
    try:
        os.makedirs(dir_path, exist_ok=True)
        path = os.path.join(dir_path, token + ".json")
        count = 0
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    count = loaded.get(field, 0)
            except Exception:
                count = 0
        count += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump({field: count}, f)
        return count
    except Exception:
        return None

if not agent_id:
    warn_reason = None
    token = _sanitized_transcript_token(data.get("transcript_path"))
    if token:
        coord_count = _bump_counter(COORD_CALLS_DIR, token, "coord_count")
        if coord_count is not None and coord_count > COORD_CALL_CEILING:
            warn_reason = COORD_COUNT_WARN_TEMPLATE.format(
                count=coord_count, ceiling=COORD_CALL_CEILING)
        subagent_type = (tool_input.get("subagent_type") or "").strip()
        if tool_name in ("Task", "Agent") and subagent_type in SEARCH_AGENT_ROLE_TYPES:
            raise_count = _bump_counter(SEARCH_AGENT_RAISES_DIR, token, "raise_count")
            if raise_count is not None and raise_count > SEARCH_AGENT_RAISE_CEILING:
                search_warn = SEARCH_AGENT_RAISE_WARN_TEMPLATE.format(
                    agent_type=subagent_type, count=raise_count,
                    ceiling=SEARCH_AGENT_RAISE_CEILING)
                warn_reason = (warn_reason + " " + search_warn) if warn_reason else search_warn
    allow_and_exit(warn_reason)

# --- 4. no brief, no launch (one exemption: writing the very first brief) -------------
KNOWN_ROLES = {"critic", "executor", "tracer", "acceptor", "reader"}
# "reader" is the one role that names no card: a read-only agent raised to gather or to look
# something up belongs to no card at all, and before it existed such an agent was refused
# every tool call it made, this hook's own read-only allowlist included, because rule 4 below
# runs before that allowlist is ever reached — measured 2026-09-07 on a market-research agent
# that could not run bin/websearch, could not Read a file, and could not reach the documented
# CLAUDE_GATE_BYPASS escape either, since that variable is read from the session's own
# environment and never from the command line a blocked agent is trying to run.
CARDLESS_ROLES = {"reader"}

def agent_brief_path(aid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    return os.path.join(BRIEFS_DIR, "agent-" + safe + ".json")

def session_brief_path(sid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(sid)) if sid else "_no_session_id_"
    return os.path.join(BRIEFS_DIR, "session-" + safe + ".json")

def _agent_brief_work_root(card_id, aid):
    """Read this agent's brief work root when its card matches."""
    if not aid:
        return None
    try:
        with open(agent_brief_path(aid), "r", encoding="utf-8") as f:
            obj = json.load(f)
    except Exception:
        return None
    if isinstance(obj, dict) and obj.get("card") == card_id:
        return obj.get("work_root")
    return None

is_brief_self_write = tool_name == "Bash" and bash_names(command_of(tool_input), "work-agent-brief")
if is_brief_self_write:
    # The one moment this hook writes state of its own accord rather than only reading it:
    # The hook payload supplies the agent identifier used to key this brief.
    command = command_of(tool_input)
    m_role = re.search(r'--role[= ]+(\S+)', command)
    m_card = re.search(r'--card[= ]+(\S+)', command)
    m_phase = re.search(r'--phase[= ]+(\S+)', command)
    m_root = re.search(r'--root[= ]+(\S+)', command)
    role_named = m_role.group(1) if m_role else None
    card_given = bool(m_card) or (role_named in CARDLESS_ROLES)
    if m_role and card_given and role_named in KNOWN_ROLES and agent_id:
        os.makedirs(BRIEFS_DIR, exist_ok=True)
        brief_obj = {"role": role_named, "card": m_card.group(1) if m_card else ""}
        if m_phase:
            brief_obj["phase"] = m_phase.group(1)
        if m_root:
            # Preserve the explicitly supplied work root for later card resolution.
            brief_obj["work_root"] = m_root.group(1)
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
        if role and (card or role in CARDLESS_ROLES):
            # Return optional phase and work-root metadata with the brief.
            return {"role": role, "card": card, "phase": b.get("phase"),
                    "work_root": b.get("work_root")}
    return None

brief = read_brief(agent_id, session_id)
if brief is None:
    deny_and_exit(
        "Blocked by work-gate: this subagent carries no caller-brief file. The step that "
        "launches an agent must run bin/work-agent-brief first, naming this agent's own "
        "role and the card it is working — this hook writes %s the moment it sees that "
        "call, and the script itself separately writes %s; neither exists yet (or neither "
        "is valid JSON naming a role and a card). No brief, no launch." %
        (agent_brief_path(agent_id), session_brief_path(session_id)),
        "work-gate.no-brief-no-launch"
    )

# --- 4a. READING ROLE IS READ-ONLY: the three reading roles get no Bash call at all -------
# The brief call itself never arrives here — rule 4's own is_brief_self_write branch allows
# and exits on it above — so every Bash call that reaches this line is a second one, and a
# reading agent has no second one. Enforced here rather than in the agent's own `tools:`
# line, which cannot hold a scoped Bash specifier: see rule 4a's own paragraph in the header.
READING_ROLES = ("critic", "tracer", "acceptor", "reader")

# Reading roles may use this allowlisted set of read-only shell programs to search content.
READ_ONLY_PROGRAMS = frozenset((
    "grep", "egrep", "fgrep", "rg", "find", "ls", "cat", "head", "tail", "wc", "nl",
    "sort", "uniq", "cut", "tr", "basename", "dirname", "realpath", "stat", "file",
    "echo", "true", "pwd", "test", "diff", "comm", "md5", "shasum", "date", "sed",
    # The web-search and web-scrape commands are included as read-only lookup tools.
    "websearch", "webscrape",
))
# Written forms that turn a reading program into a writing one, or that reach a program this
# list never vetted. Matched on the raw command before it is split, so no quoting trick in a
# later segment can smuggle one past the per-segment program check below.
WRITING_FORMS = re.compile(
    r'(>>?|`|\$\(|\bsed\b[^|;&]*\s-[a-zA-Z]*i|\bxargs\b|\btee\b|\bfind\b[^|;&]*'
    r'-(exec|execdir|ok|okdir|delete|fprint|fls))'
)

def split_command_segments(command):
    """Split a command at shell separators while respecting quoted arguments."""
    segments, current, quote = [], [], None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            current.append(ch)
            i += 1
            continue
        if command.startswith("&&", i) or command.startswith("||", i):
            segments.append("".join(current))
            current = []
            i += 2
            continue
        if ch in "|;\n":
            segments.append("".join(current))
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    segments.append("".join(current))
    return segments


def is_read_only_command(command):
    """True when every program the command runs is in READ_ONLY_PROGRAMS and the command
    carries no form that writes. Segments are split on the shell's own separators, and each
    segment's own first bare word is the program it runs; a segment whose program cannot be
    read as a bare word fails closed."""
    if not command.strip() or WRITING_FORMS.search(command):
        return False
    for segment in split_command_segments(command):
        segment = segment.strip()
        if not segment:
            continue
        # The leading ~ is part of the path a caller actually types, and this hook's own
        # The refusal text names the installed toolkit path for websearch.
        # the web. Without ~ in this class the match failed at position 0 and the hook
        # refused the very command it recommends (measured 2026-09-10, same critic run).
        m = re.match(r'([~A-Za-z0-9_./-]+)', segment)
        if not m:
            return False
        program = os.path.basename(m.group(1))
        if program not in READ_ONLY_PROGRAMS:
            return False
    return True

if (brief.get("role") in READING_ROLES and tool_name == "Bash"
        and is_read_only_command(command_of(tool_input))):
    allow_and_exit("work-gate.reading-role-search-allowed")

if brief.get("role") in READING_ROLES and tool_name == "Bash":
    deny_and_exit(
        "Blocked by work-gate's READING ROLE IS READ-ONLY rule: role \"%s\" reads and never "
        "runs anything. The one Bash call this role is allowed, bin/work-agent-brief, has "
        "already happened. What is refused is this command, because it can run something "
        "or change something: %s\n"
        "Searching is allowed and is how you are meant to work. These programs pass, alone "
        "or piped into one another: grep, rg, find, ls, cat, head, tail, wc, nl, sort, "
        "uniq, cut, tr, sed, diff, basename, dirname, realpath, stat, file, echo, pwd, "
        "test, %s/bin/websearch — which is how you search the web, never the "
        "built-in WebSearch tool — and %s/bin/webscrape, which reads the full text of one "
        "page. Redirection, command substitution, xargs, tee, sed -i and find -exec are "
        "refused, and so is every program not on that list. Note that the Grep and Glob "
        "tools do not exist here: grep and find through this Bash tool are their "
        "replacement, not a workaround.\n"
        "Search a file for the name you need, then Read only the line range the match "
        "points at. Never read a large file end to end to search it.\n"
        "You never run a check yourself and you never see a check's output. Whatever raised "
        "you runs every check with its own hand, after reading your answer." %
        (brief.get("role"), toolkit_root, toolkit_root, command_of(tool_input)),
        "work-gate.reading-role-read-only"
    )

# --- 4b. THE CARDLESS READING ROLE STOPS HERE: every rule below this line is scoped to a
# card — its folder, its log, its sanction, its working copy — and a "reader" names none, so
# each of them would either resolve nothing or refuse a legitimate call. Its Bash calls have
# already been judged by rule 4a above, on exactly the same read-only allowlist every other
# reading role gets; what passes here is everything else it does, Read above all.
if brief.get("role") in CARDLESS_ROLES:
    allow_and_exit("work-gate.cardless-reading-role")

# Shared shell-command parsing helpers used by the gate rules below.
QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", re.S)
CHAINING_RE = re.compile(r'(&&|;|\||\n)')

def chains(command):
    """Return whether the command contains an unquoted statement separator."""
    return CHAINING_RE.search(QUOTED_SPAN_RE.sub("", command)) is not None

# Git options that consume a value before the subcommand.
GIT_PRE_SUBCOMMAND_VALUE_OPTS = ("-C", "-c")

def git_subcommand(command):
    """The subcommand of a `git …` invocation, skipping the options that legitimately come
    before it, or None when the command is not a git invocation at all."""
    tokens = command.split()
    if not tokens or tokens[0] != "git":
        return None
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in GIT_PRE_SUBCOMMAND_VALUE_OPTS:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token
    return None

# Git subcommands accepted by the state-recording escape.
PHASE_BOUNDARY_SAVE_GIT_SUBCOMMANDS = ("add", "commit")

# A command invoking one of the three commands that record a run's own state, by the bare
# relative path or by any path ending in that same bin/<name> component — never by basename
# alone, so that a path such as ~/elsewhere/work-note is not exempt while
# /abs/path/to/bin/work-note is.
PHASE_BOUNDARY_LOG_CALL_RE = re.compile(r'^\s*(\S*/)?bin/work-(log|note|commit)\b')

def matched_log_call_kind():
    """Return the kind of state-recording command invoked, or None if unmatched."""
    if tool_name != "Bash":
        return None
    command = command_of(tool_input)
    lines = command.rstrip("\n").split("\n")
    first_line = lines[0]
    heredoc_m = re.search(r'<<-?\s*([\'"]?)(\w+)\1\s*$', first_line)
    if heredoc_m:
        head = first_line[:heredoc_m.start()]
        if CHAINING_RE.search(QUOTED_SPAN_RE.sub("", head)):
            return None
        m = PHASE_BOUNDARY_LOG_CALL_RE.match(head)
        if m is None:
            return None
        if lines[-1].strip() != heredoc_m.group(2):
            return None
        return m.group(2)
    if chains(command):
        return None
    m = PHASE_BOUNDARY_LOG_CALL_RE.match(command)
    return m.group(2) if m else None

work_root = find_work_root(brief.get("card"))
card_dir = find_card_dir(work_root, brief["card"]) if work_root else None

# Refuse a brief naming a card that cannot be resolved under the configured work root.
if work_root and card_dir is None:
    deny_and_exit(
        "Blocked by work-gate: this run's own caller-brief names %r as its card, and no "
        "card folder of that name exists under %s. A card is named by its identifier — "
        "TST-1, DEMO-2 — never by a path to its own folder. Every rule this gate scopes to "
        "a card is off while the brief says this, so the run is stopped here rather than "
        "allowed to continue ungoverned. Re-write the brief with the identifier: "
        "bin/work-agent-brief --role %s --card <ID>%s" %
        (brief["card"], work_root, brief.get("role") or "executor",
         (" --phase " + brief["phase"]) if brief.get("phase") else ""),
        "work-gate.brief-names-no-card"
    )

# Shared lookup for this card's log path in the checkout and linked worktree.
_log_paths_cache = []

def this_cards_log_paths():
    """Every address this run's own card's log.md legitimately has, as real paths: the file
    inside the card's own folder in the shared checkout, and the same relative path inside
    the card's own linked working copy when one exists. Empty when card_dir could not be
    resolved at all — the caller then matches nothing, which is the same fail-open posture
    every rule scoped to a card already takes for an unresolvable card_dir. The working copy
    is found by find_card_worktree_root(), the one lookup every other rule in this file
    already uses for it, and the whole answer is computed once per call of this hook: it
    runs `git worktree list` as a subprocess, and every caller below sits on a path that is
    reached only when a ceiling has already fired."""
    if _log_paths_cache:
        return _log_paths_cache[0]
    paths = []
    if card_dir is not None:
        shared = os.path.realpath(os.path.join(card_dir, "log.md"))
        paths.append(shared)
        shared_root = os.path.dirname(work_root) if work_root else None
        own_root = find_card_worktree_root(brief["card"])
        if shared_root and own_root:
            try:
                rel = os.path.relpath(shared, os.path.realpath(shared_root))
            except ValueError:
                rel = None
            if rel and not rel.startswith(os.pardir):
                paths.append(os.path.realpath(os.path.join(own_root, rel)))
    _log_paths_cache.append(paths)
    return paths

def names_this_cards_log(fp):
    """True when the path this call names is this card's own log.md, at either address."""
    if fp is None:
        return False
    return os.path.realpath(fp) in this_cards_log_paths()

# Reject chained state-recording calls because their state changes cannot be reliably
# accounted for by the single-call checks.
def chained_recording_call():
    """The script name — "note", "commit" or "log" — this Bash call really invokes inside a
    chain, or None. Judged against the same text matched_log_call_kind() judges: the first
    line up to its own heredoc marker when there is one, the whole command otherwise, with
    every quoted span blanked out first, so a `;` or `|` inside a handoff's own prose is
    never read as shell syntax."""
    if tool_name != "Bash":
        return None
    if matched_log_call_kind() is not None:
        return None
    command = command_of(tool_input)
    first_line = command.rstrip("\n").split("\n")[0]
    heredoc_m = re.search(r'<<-?\s*([\'"]?)(\w+)\1\s*$', first_line)
    head = first_line[:heredoc_m.start()] if heredoc_m else command
    bare = QUOTED_SPAN_RE.sub("", head)
    if not CHAINING_RE.search(bare):
        return None
    for segment in re.split(r'&&|\|\||[;|\n]', bare):
        m = PHASE_BOUNDARY_LOG_CALL_RE.match(segment)
        if m:
            return m.group(2)
    return None

if brief.get("role") == "executor":
    chained_kind = chained_recording_call()
    if chained_kind:
        deny_and_exit(
            "Blocked by work-gate's CHAINED RECORDING CALL rule: this call invokes "
            "bin/work-%s inside a chain, and a chained invocation counts as none at all. "
            "Left to run, it would write its entry and return zero while this gate saw no "
            "call at all: the ceiling on calls made without writing to the log would not "
            "reset. That silence cost one run its whole ceiling, so the call is stopped "
            "here rather than left to half-work quietly.\n"
            "Run it as one command: no `cd` in front, and no `&&`, `;`, `|` or line break "
            "anywhere outside a quoted argument. You do not have to be standing in the "
            "card's own working copy and there is no path to pass — name the script by its "
            "own absolute path and it finds that copy itself:\n"
            "      %s/bin/work-%s …" %
            (chained_kind,
             os.path.dirname(work_root) if work_root else "<shared checkout>", chained_kind),
            "work-gate.chained-recording-call"
        )

# --- 6. File authorship ---------------------------------------------------------------
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
                    "answers it. One file, one author.",
                    "work-gate.file-authorship-plan"
                )
            if role == "executor" and fname in EXECUTOR_LOCKED_FILES:
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: %s is not the executor's "
                    "file to write — one file, one author." % fname,
                    "work-gate.file-authorship-executor-locked"
                )
            if role == "acceptor" and fname == "log.md":
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: log.md is not the "
                    "acceptor's file to write — one file, one author.",
                    "work-gate.file-authorship-acceptor-log"
                )

# --- 6a. Working-copy boundary --------------------------------------------------------
def resolve_shared_checkout_root():
    """The shared checkout's own path — os.path.dirname(work_root), since find_work_root()
    above always returns that path with "ai" appended, by construction or by its own test
    override. None when work_root itself is None."""
    if not work_root:
        return None
    return os.path.dirname(work_root)

def git_common_dir(path):
    """Return the resolved Git common directory, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=5, cwd=path,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    if not out:
        return None
    return os.path.realpath(out)

def same_repository(path_a, path_b):
    """Compare repository identities, returning None when either cannot be resolved."""
    common_a = git_common_dir(path_a)
    common_b = git_common_dir(path_b)
    if common_a is None or common_b is None:
        return None
    return common_a == common_b

WORKING_COPY_BOUNDARY_TEMPLATE = (
    "Blocked by work-gate's WORKING COPY BOUNDARY rule: this call would edit %s, inside the "
    "shared checkout — not this card's own working copy, %s. Repeat the same edit at the "
    "right address instead: %s."
)

# Offer a substituted destination only when both paths resolve to the same repository.
CROSS_REPOSITORY_BOUNDARY_TEMPLATE = (
    "Blocked by work-gate's WORKING COPY BOUNDARY rule: this call would edit %s, inside the "
    "shared checkout — not this card's own working copy, %s, and the two are not confirmed to "
    "be the same repository. No substituted address is offered: a path built by rewriting the "
    "text alone could name a file in a different repository, the very leak this rule exists to "
    "stop. Return this step to the orchestrator instead: bin/work-question %s --root %s."
)

# Shell writes checked by the working-copy boundary.
SHELL_WRITE_FORM_TABLE = (
    ("output redirection", ">, >>, >|, a leading stream number (2>, 2>>), or &>"),
    ("tee", "with or without -a"),
    ("cp/mv destination", "the last non-option argument, or -t/--target-directory's own value"),
    ("sed -i", "the file arguments left once its own flags are parsed"),
)

SHELL_WRITE_FORMS_TEXT = "; ".join(
    "%s (%s)" % (name, desc) for name, desc in SHELL_WRITE_FORM_TABLE
)

SHELL_BOUNDARY_SCOPE_NOTE = (
    "This boundary is judged on a shell write too, by these forms only: %s. Two things are "
    "never judged at all: a write made from inside a heredoc body by another program (e.g. "
    "`python3 <<'EOF'` opening a file inside its own body), and a relative target after `cd` "
    "to a value that is not a literal path (a variable, a command substitution)." %
    SHELL_WRITE_FORMS_TEXT
)

def working_copy_boundary_denial(real_fp, card_id):
    """Return boundary-denial text and rule suffix, or None when the target is allowed."""
    real_card_dir = os.path.realpath(card_dir)
    if os.path.dirname(real_fp) == real_card_dir:
        return None
    shared_root = resolve_shared_checkout_root()
    own_root = find_card_worktree_root(card_id)
    if not (shared_root and own_root):
        return None
    real_shared_root = os.path.realpath(shared_root)
    real_own_root = os.path.realpath(own_root)
    inside_shared = (real_fp == real_shared_root or
                      real_fp.startswith(real_shared_root + os.sep))
    inside_own = (real_fp == real_own_root or
                  real_fp.startswith(real_own_root + os.sep))
    if not (inside_shared and not inside_own):
        return None
    if same_repository(real_shared_root, real_own_root) is not True:
        return (CROSS_REPOSITORY_BOUNDARY_TEMPLATE %
                (real_fp, real_own_root, card_id, work_root),
                "working-copy-boundary-cross-repository")
    rel = os.path.relpath(real_fp, real_shared_root)
    right_path = os.path.join(real_own_root, rel)
    return (WORKING_COPY_BOUNDARY_TEMPLATE % (real_fp, real_own_root, right_path),
            "working-copy-boundary")

def declared_repo_boundary_denial(real_fp, card_id):
    """Check write targets against each additional repository declared by the card."""
    real_card_dir = os.path.realpath(card_dir)
    if os.path.dirname(real_fp) == real_card_dir:
        return None
    for repo in declared_repos_beyond_primary(card_id):
        real_repo = os.path.realpath(repo)
        inside_repo = (real_fp == real_repo or real_fp.startswith(real_repo + os.sep))
        if not inside_repo:
            continue
        repo_own_root = find_repo_worktree_root(real_repo, card_id)
        if not repo_own_root:
            continue
        real_repo_own_root = os.path.realpath(repo_own_root)
        inside_repo_own = (real_fp == real_repo_own_root or
                            real_fp.startswith(real_repo_own_root + os.sep))
        if inside_repo_own:
            continue
        rel = os.path.relpath(real_fp, real_repo)
        right_path = os.path.join(real_repo_own_root, rel)
        return (WORKING_COPY_BOUNDARY_TEMPLATE % (real_fp, real_repo_own_root, right_path),
                "working-copy-boundary")
    return None

if brief.get("role") == "executor" and tool_name in ("Write", "Edit") and card_dir is not None:
    fp = file_path_of(tool_input)
    if fp is not None:
        real_fp = os.path.realpath(fp)
        result = working_copy_boundary_denial(real_fp, brief["card"])
        if result:
            text, suffix = result
            deny_and_exit(text + "\n" + SHELL_BOUNDARY_SCOPE_NOTE, "work-gate." + suffix)

        # Check additional repositories declared by this card.
        result2 = declared_repo_boundary_denial(real_fp, brief["card"])
        if result2:
            text2, suffix2 = result2
            deny_and_exit(text2, "work-gate." + suffix2)

# --- 6b. Git command policy -----------------------------------------------------------
GIT_PRE_SUBCOMMAND_VALUE_OPTS_6B = GIT_PRE_SUBCOMMAND_VALUE_OPTS  # same two options, same skip

def git_subcommand_and_arg(command):
    """(subcommand, the token right after it) of a `git …` invocation, walking past the same
    pre-subcommand options git_subcommand() above already walks past. The second element is
    used only to tell `git worktree list` apart from `git worktree add`/`remove`/… — None
    when there is no further token. (None, None) when `command` is not a git invocation."""
    tokens = command.split()
    if not tokens or tokens[0] != "git":
        return None, None
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in GIT_PRE_SUBCOMMAND_VALUE_OPTS_6B:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token, (tokens[i + 1] if i + 1 < len(tokens) else None)
    return None, None

def git_dash_c_path(command):
    """The path argument of this `git …` invocation's own `-C <path>` option, or None when
    it carries none — used only to resolve which repository a git call actually targets."""
    tokens = command.split()
    if not tokens or tokens[0] != "git":
        return None
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token == "-C":
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if token == "-c":
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return None
    return None

def command_head_before_heredoc(command):
    """Return the command text before a heredoc body, if present."""
    m = re.search(r'<<-?\s*([\'"]?)(\w+)\1', command)
    return command[:m.start()] if m else command

def git_statements(command):
    """Every top-level statement of `command`'s own head (command_head_before_heredoc above)
    — split on `&&`, `;`, `|` or a newline outside any quoted span, the same quote-aware rule
    chains() already uses to decide whether a command chains at all, kept position-aligned
    with the original text (padded, not stripped) so the split points land in the same place
    in both strings."""
    head = command_head_before_heredoc(command)
    blanked = QUOTED_SPAN_RE.sub(lambda m: "x" * len(m.group(0)), head)
    parts, last = [], 0
    for m in CHAINING_RE.finditer(blanked):
        parts.append(head[last:m.start()])
        last = m.end()
    parts.append(head[last:])
    return [p.strip() for p in parts if p.strip()]

def project_worktree_roots():
    """Every worktree path `git worktree list --porcelain` reports for the repository
    reachable from this hook's own default working directory — the shared checkout every
    Bash call's own cwd is always reset to — covering both that shared checkout itself and
    every card's own linked working copy cut alongside it. None on any failure to run git at
    all, in which case a `-C <path>` git call is treated as unresolvable and not judged, the
    same fail-open posture every other rule in this file already takes on a reading error of
    its own."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    roots = [line[len("worktree "):].strip()
             for line in result.stdout.splitlines() if line.startswith("worktree ")]
    return roots or None

def path_is_in_project(path, roots):
    if not path or not roots:
        return False
    try:
        real = os.path.realpath(path)
    except Exception:
        return False
    for root in roots:
        real_root = os.path.realpath(root)
        if real == real_root or real.startswith(real_root + os.sep):
            return True
    return False

GIT_READ_ONLY_SUBCOMMANDS = {"status", "diff", "log", "show", "rev-parse", "ls-files"}
GIT_COMMAND_SAVE_SUBCOMMANDS = {"stash", "add", "commit", "checkout", "switch",
                                 "restore", "reset", "branch", "clean"}
GIT_COMMAND_LAND_SUBCOMMANDS = {"merge", "rebase", "push"}

GIT_COMMAND_SAVE_TEMPLATE = (
    "Blocked by work-gate's GIT COMMAND rule: `git %s` is not the executor's own way to "
    "save or discard work — call bin/work-commit <step> \"<result>\" instead, which stages and "
    "commits everything this step changed through the project's own pre-commit checks, "
    "after recording the same step's state with bin/work-note %s <step> \"<status>\". "
    "Reading commands stay open without limit: git status, diff, log, show, rev-parse, "
    "ls-files, worktree list."
)
GIT_COMMAND_LAND_TEMPLATE = (
    "Blocked by work-gate's GIT COMMAND rule: `git %s` lands or moves this card's own "
    "branch, and that is never the executor's own move — acceptance (bin/work-accept, run "
    "by the coordinator once the card's work is done) is what folds the branch in. Reading "
    "commands stay open without limit: git status, diff, log, show, rev-parse, ls-files, "
    "worktree list."
)
GIT_COMMAND_UNKNOWN_TEMPLATE = (
    "Blocked by work-gate's GIT COMMAND rule: `git %s` is not one of the reading commands an "
    "executor may run directly — status, diff, log, show, rev-parse, ls-files, worktree "
    "list. Save or discard work with bin/work-commit <step> \"<result>\", record it with "
    "bin/work-note %s <step> \"<status>\", and leave landing the branch to acceptance."
)

def git_command_denial(subcommand_label, card_id):
    if subcommand_label in GIT_COMMAND_SAVE_SUBCOMMANDS:
        return GIT_COMMAND_SAVE_TEMPLATE % (subcommand_label, card_id)
    if subcommand_label in GIT_COMMAND_LAND_SUBCOMMANDS:
        return GIT_COMMAND_LAND_TEMPLATE % subcommand_label
    return GIT_COMMAND_UNKNOWN_TEMPLATE % (subcommand_label, card_id)

NPM_INSTALL_RE = re.compile(r'(?:^|[\s;&|])npm\s+install\b')

if brief.get("role") == "executor" and tool_name == "Bash":
    command = command_of(tool_input)
    head_blanked = QUOTED_SPAN_RE.sub(lambda m: "x" * len(m.group(0)),
                                       command_head_before_heredoc(command))
    if NPM_INSTALL_RE.search(head_blanked):
        deny_and_exit(
            "Blocked by work-gate's GIT COMMAND rule: `npm install` rewrites the lock file "
            "— call `npm ci` instead, which installs exactly what the lock file already "
            "records.",
            "work-gate.npm-install"
        )

    project_roots = None
    for statement in git_statements(command):
        subcommand, nxt = git_subcommand_and_arg(statement)
        if subcommand is None:
            continue
        dash_c = git_dash_c_path(statement)
        if dash_c is not None:
            if project_roots is None:
                project_roots = project_worktree_roots()
            if not path_is_in_project(dash_c, project_roots):
                continue  # A repository outside the current checkout is not judged.
        if subcommand == "worktree":
            if nxt == "list":
                continue
            deny_and_exit(git_command_denial("worktree " + (nxt or ""), brief["card"]),
                          "work-gate.git-command")
        if subcommand in GIT_READ_ONLY_SUBCOMMANDS:
            continue
        deny_and_exit(git_command_denial(subcommand, brief["card"]), "work-gate.git-command")

# --- 6c. Shell write boundary ---------------------------------------------------------
# Detect supported write forms and resolve relative targets from the shell's current path.

def _strip_quotes(raw):
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        return raw[1:-1]
    return raw

def _statement_tokens(text):
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(r'\S+', text)]

def _program_word(tokens):
    return os.path.basename(tokens[0][0]) if tokens else None

_SHELL_REDIRECT_OPERATOR_RE = re.compile(r'[0-9]{1,2}>{1,2}|&>|>\||>>|>')

def _redirect_targets(blanked, original):
    """Every ("output redirection", target) pair on this one statement's own blanked text —
    a quote-blanked copy, same length, same positions as `original` — the operator matched
    on the blanked text, the target string read back from `original` at the same span so a
    quoted target keeps its real content and then has its own quotes stripped. `>&1`/`>&-`
    (fd duplication or fd close) is never a file write and is skipped."""
    targets = []
    for m in _SHELL_REDIRECT_OPERATOR_RE.finditer(blanked):
        op, start = m.group(0), m.start()
        if op[0].isdigit():
            before = blanked[start - 1] if start > 0 else None
            if before is not None and before not in " \t":
                continue  # the digit belongs to a longer token, not a leading stream number
        pos = m.end()
        while pos < len(blanked) and blanked[pos] in " \t":
            pos += 1
        if pos < len(blanked) and blanked[pos] == "&":
            continue  # fd duplication or fd close (>&1, >&-) — never a file write
        word = re.match(r'\S+', blanked[pos:])
        if not word:
            continue
        targets.append(("output redirection", _strip_quotes(original[pos:pos + word.end()])))
    return targets

def _tee_targets(tokens, original):
    if _program_word(tokens) != "tee":
        return []
    out = []
    for tok, start, end in tokens[1:]:
        if tok in ("-a", "--append", "-") or tok.startswith("-"):
            continue
        out.append(("tee", _strip_quotes(original[start:end])))
    return out

def _cp_mv_targets(tokens, original):
    if _program_word(tokens) not in ("cp", "mv"):
        return []
    positional = []
    target_dir_span = None
    i = 1
    while i < len(tokens):
        tok, start, end = tokens[i]
        if tok in ("-t", "--target-directory") and i + 1 < len(tokens):
            target_dir_span = tokens[i + 1][1:3]
            i += 2
            continue
        if tok.startswith("--target-directory="):
            value_start = start + len("--target-directory=")
            target_dir_span = (value_start, end)
            i += 1
            continue
        if tok.startswith("-"):
            i += 1
            continue
        positional.append((start, end))
        i += 1
    if target_dir_span is not None:
        vstart, vend = target_dir_span
        return [("cp/mv destination", _strip_quotes(original[vstart:vend]))]
    if len(positional) >= 2:
        start, end = positional[-1]
        return [("cp/mv destination", _strip_quotes(original[start:end]))]
    return []

def _sed_i_targets(tokens, original):
    if _program_word(tokens) != "sed":
        return []
    has_i = False
    script_from_flag = False
    positional = []
    i = 1
    while i < len(tokens):
        tok, start, end = tokens[i]
        if tok == "-i":
            has_i = True
            if i + 1 < len(tokens) and tokens[i + 1][0] in ("''", '""'):
                i += 2  # BSD sed's own separate-argument suffix, consumed
                continue
            i += 1
            continue
        if tok.startswith("-i") and not tok.startswith("--"):
            has_i = True  # GNU sed's own attached suffix, e.g. -i.bak
            i += 1
            continue
        if tok == "--in-place" or tok.startswith("--in-place="):
            has_i = True
            i += 1
            continue
        if tok in ("-e", "--expression", "-f", "--file"):
            script_from_flag = True
            i += 2
            continue
        if tok.startswith("--expression=") or tok.startswith("--file="):
            script_from_flag = True
            i += 1
            continue
        if tok.startswith("-"):
            i += 1
            continue
        positional.append((start, end))
        i += 1
    if not has_i:
        return []
    files = positional if script_from_flag else positional[1:]
    return [("sed -i", _strip_quotes(original[start:end])) for start, end in files]

def _statement_write_targets(blanked, original, tokens):
    return (_redirect_targets(blanked, original) + _tee_targets(tokens, original) +
            _cp_mv_targets(tokens, original) + _sed_i_targets(tokens, original))

def _write_statements(command):
    """Split command statements while preserving the shell redirection operator `>|`."""
    protected = command.replace(">|", ">\x01")
    return [statement.replace("\x01", "|") for statement in git_statements(protected)]

_LITERAL_PATH_RE = re.compile(r'[$`*?\[\]]')

def executor_shell_cwd():
    """Return the shell working directory, with an optional test override."""
    return os.environ.get("WORK_GATE_SHELL_CWD") or os.getcwd()

def shell_write_targets_with_base(command, cwd):
    """Return detected write targets resolved against the command's effective directory."""
    results = []
    base = cwd
    base_known = True
    for original in _write_statements(command):
        blanked = QUOTED_SPAN_RE.sub(lambda m: "x" * len(m.group(0)), original)
        tokens = _statement_tokens(blanked)
        if tokens and tokens[0][0] == "cd" and len(tokens) >= 2:
            cd_start, cd_end = tokens[1][1], tokens[1][2]
            cd_raw = _strip_quotes(original[cd_start:cd_end])
            if _LITERAL_PATH_RE.search(cd_raw):
                base_known = False
            else:
                base = os.path.expanduser(cd_raw) if cd_raw.startswith("~") else \
                    (cd_raw if os.path.isabs(cd_raw) else os.path.join(base, cd_raw))
                base_known = True
            continue  # a `cd` statement itself never writes anything
        for form, raw_target in _statement_write_targets(blanked, original, tokens):
            if os.path.isabs(raw_target):
                results.append((form, raw_target))
            elif base_known:
                results.append((form, os.path.join(base, raw_target)))
            # else: a relative target after a non-literal `cd` — left unresolved, not judged
    return results

if brief.get("role") == "executor" and tool_name == "Bash" and card_dir is not None:
    shell_command = command_of(tool_input)
    for form, resolved in shell_write_targets_with_base(shell_command, executor_shell_cwd()):
        real_target = os.path.realpath(resolved)
        result = working_copy_boundary_denial(real_target, brief["card"])
        if result:
            text, suffix = result
            deny_and_exit(
                text + "\nCaught by: %s.\n%s" % (form, SHELL_BOUNDARY_SCOPE_NOTE),
                "work-gate.shell-" + suffix
            )
        # Apply the same additional-repository check used for Write and Edit.
        result2 = declared_repo_boundary_denial(real_target, brief["card"])
        if result2:
            text2, suffix2 = result2
            deny_and_exit(
                text2 + "\nCaught by: %s.\n%s" % (form, SHELL_BOUNDARY_SCOPE_NOTE),
                "work-gate.shell-" + suffix2
            )

# --- 7. Log-write ceiling -------------------------------------------------------------
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
    # Match the shared card log and its linked-worktree counterpart.
    def names_this_cards_log_cheaply(p):
        return (p is not None and os.path.basename(p) == "log.md"
                and names_this_cards_log(p))
    is_this_cards_log_write_now = (
        tool_name in ("Write", "Edit") and names_this_cards_log_cheaply(fp)
    )
    # A Read of that same file passes without resetting anything. Write and Edit both refuse
    # client-side on a file this session has not read ("File has not been read yet"), so with
    # Read refused here the ceiling's own designated escape could not satisfy its own
    # precondition — the second half of the same deadlock.
    is_this_cards_log_read_now = (
        tool_name == "Read" and names_this_cards_log_cheaply(fp)
    )
    log_command = command_of(tool_input)
    is_work_log_call = tool_name == "Bash" and (
        bash_names(log_command, "work-log") or
        bash_names(log_command, "work-note"))
    # A --handoff call passes this ceiling but resets nothing: it records that the run is
    # stopping, not that a step closed. Only a step-naming bin/work-note call — or a direct
    # Write/Edit of log.md — says the run actually moved, and only that resets the count.
    is_handoff_call = is_work_log_call and "--handoff" in (log_command or "")
    # Allow commits without resetting the log-write counter.
    is_work_commit_call = tool_name == "Bash" and bash_names(log_command or "", "work-commit")
    count_path = log_call_count_path(agent_id)
    if is_this_cards_log_write_now or (is_work_log_call and not is_handoff_call):
        write_log_call_count(count_path, 0)
    elif is_handoff_call or is_work_commit_call or is_this_cards_log_read_now:
        pass
    else:
        n = read_log_call_count(count_path) + 1
        write_log_call_count(count_path, n)
        if n >= LOG_CALL_CEILING:
            deny_and_exit(
                "Blocked by work-gate's LOG CEILING rule: %d calls have passed since this "
                "executor last wrote to this card's own log.md. This ceiling does not end "
                "the run and is not a reason to stop: it refuses one call and asks for a "
                "line in the journal, nothing more. A Write/Edit of log.md, or a Bash call "
                "running bin/work-note with a step name, resets this count to zero and lets "
                "the work go straight on. The step named there does not have to be finished "
                "— write the step you are on and the state it is actually in, in one line, "
                "and carry on with the same step. A bin/work-note --handoff call also gets "
                "through but resets nothing: it says the run is stopping, not that work was "
                "done, so write one only when you really are ending the run, and never as a "
                "way out from under this ceiling. This ceiling does not end the run. Record "
                "the current step's state in one line and continue. Write a handoff only "
                "when the run is actually ending." % n,
                "work-gate.log-ceiling"
            )

# --- Shared state-recording helpers ---------------------------------------------------
def recording_call_names_this_card():
    """Check whether a work-note command names the current card."""
    command = command_of(tool_input)
    head = command.rstrip("\n").split("\n")[0]
    heredoc_m = re.search(r'<<-?\s*([\'"]?)(\w+)\1\s*$', head)
    if heredoc_m:
        head = head[:heredoc_m.start()]
    try:
        tokens = shlex.split(head)
    except ValueError:
        tokens = head.split()
    want = str(brief.get("card") or "").upper()
    return bool(want) and any(t.upper() == want for t in tokens[1:])

def is_state_recording_escape_call():
    """Return whether this call can record state while a resource ceiling is active."""
    if tool_name in ("Read", "Write", "Edit"):
        return names_this_cards_log(file_path_of(tool_input))
    kind = matched_log_call_kind()
    if kind == "commit":
        return True
    if kind == "note":
        return recording_call_names_this_card()
    # Permit a single add or commit for an external repository as a state-recording escape.
    command = command_of(tool_input)
    if tool_name == "Bash" and command and not chains(command) and \
            git_subcommand(command) in PHASE_BOUNDARY_SAVE_GIT_SUBCOMMANDS:
        target = git_dash_c_path(command)
        shared_root = os.path.dirname(work_root) if work_root else None
        if target and shared_root:
            try:
                rel = os.path.relpath(os.path.realpath(target),
                                      os.path.realpath(shared_root))
            except (OSError, ValueError):
                return True
            if rel.startswith(os.pardir):
                return True
    return False

def ceiling_escape_sentence():
    """The closing paragraph every ceiling below shares: the exact calls that still get
    through, written as commands the agent can run rather than as a category it has to
    recognise. The order is the order they have to be made in — a handoff refuses a dirty
    working copy, so the commit comes first whenever there is uncommitted code."""
    card = brief.get("card") or "<ID>"
    phase = brief.get("phase") or "<phase>"
    paths = this_cards_log_paths()
    log_at = paths[-1] if paths else "log.md in the card folder"
    return (
        "These calls, and nothing else, still get through. Each is a single command: no "
        "`cd` in front, no `&&`, no `;`, no `|`.\n"
        "  1. Commit what is already built, if anything in the working copy is still "
        "uncommitted — the handoff below refuses a dirty copy, so this comes first:\n"
        "         bin/work-commit %s.<N> \"<step result>\"\n"
        "  2. Write the handoff, which is what a fresh executor picks the work up from:\n"
        "         bin/work-note %s --handoff %s \"<status, findings, next steps>\"\n"
        "  3. A Read, Write or Edit of this card's own log.md, and of no other file:\n"
        "         %s\n"
        "  4. If this card's work reaches a repository outside this project, one `git add` "
        "or `git commit` naming it through its own `-C`, so that work is saved too:\n"
        "         git -C <repository path> commit -m \"…\" -- <path>\n"
        "Then stop." % (phase, card, phase, log_at)
    )

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

# --- Transcript lookup for resource limits ---------------------------------------------
AGENT_TRANSCRIPT_GLOBS = [
    os.path.expanduser("~/.claude/projects/*/%s.jsonl"),
    "/private/tmp/claude-*/*/*/tasks/%s.output",
]

def agent_transcript_path(aid):
    """Return the newest transcript for an agent, honoring the test override."""
    override = os.environ.get("WORK_GATE_AGENT_TRANSCRIPT")
    if override:
        return override
    if not aid or not re.fullmatch(r'[A-Za-z0-9_-]+', str(aid)):
        return None
    for pattern in AGENT_TRANSCRIPT_GLOBS:
        hits = glob.glob(pattern % aid)
        if not hits:
            continue
        try:
            return max(hits, key=os.path.getmtime)
        except OSError:
            return hits[0]
    return None

if agent_id:
    transcript_path = agent_transcript_path(agent_id)
else:
    transcript_path = data.get("transcript_path")
run_stats = run_transcript_stats(transcript_path)

# --- 8. Context-size ceiling -----------------------------------------------------------
CONTEXT_SIZE_CEILING = 300_000
CONTEXT_SOFT_CEILING = 250_000

if run_stats is not None and run_stats["last_context"] is not None:
    last_context = run_stats["last_context"]
    if last_context > CONTEXT_SIZE_CEILING:
        if is_state_recording_escape_call():
            allow_and_exit()
        deny_and_exit(
            "Blocked by work-gate's CONTEXT SIZE rule: this agent's own most recent turn held "
            "%d tokens of context, past the %d ceiling. Record the state in the log and stop. "
            "A fresh executor picks the card up from there with an empty context.\n%s" %
            (last_context, CONTEXT_SIZE_CEILING, ceiling_escape_sentence()),
            "work-gate.context-size"
        )
    elif last_context > CONTEXT_SOFT_CEILING:
        # This branch adds a warning to an allow and never refuses.
        allow_and_exit(
            "work-gate's CONTEXT SIZE rule: this agent's own most recent turn held %d tokens "
            "of context, past the %d soft ceiling and %d short of the %d hard one, where "
            "every call is refused except the ones that record where the run stopped. Close "
            "the step you are on, write it to log.md with bin/work-note, and — if the run is "
            "actually ending — write a handoff too, rather than waiting to be cut off. Stop "
            "voluntarily while there is still room to do so." %
            (last_context, CONTEXT_SOFT_CEILING, CONTEXT_SIZE_CEILING - last_context,
             CONTEXT_SIZE_CEILING)
        )

# --- 9. Per-run spend ceiling ----------------------------------------------------------
SPEND_CEILING = 90_000_000

if brief.get("role") == "executor" and run_stats is not None and \
        run_stats["spend"] > SPEND_CEILING:
    if is_state_recording_escape_call():
        allow_and_exit()
    deny_and_exit(
        "Blocked by work-gate's SPEND CEILING rule: this executor's own run has spent %d "
        "tokens (cache-read plus output, summed from its own transcript), past the %d "
        "ceiling counted for this run alone, never accumulated across the whole card — a "
        "fresh executor's own transcript starts this same count at zero. Record the state "
        "in the log and stop.\n%s" %
        (run_stats["spend"], SPEND_CEILING, ceiling_escape_sentence()),
        "work-gate.spend-ceiling"
    )

# --- 10. Pace ceiling ------------------------------------------------------------------
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
        if is_state_recording_escape_call():
            allow_and_exit()
        deny_and_exit(
            "Blocked by work-gate's PACE rule: no number was found at %s — the pace "
            "threshold this rule judges every call against must live there as a bare "
            "integer, and its absence refuses every call for this executor rather than "
            "silently skipping the check.\n%s" %
            (pace_threshold_file(), ceiling_escape_sentence()),
            "work-gate.pace-threshold-missing"
        )
    elif run_stats is not None and run_stats["calls"] > PACE_CALL_ALLOWANCE:
        pace = run_stats["spend"] / run_stats["calls"]
        if pace > pace_threshold:
            if is_state_recording_escape_call():
                allow_and_exit()
            deny_and_exit(
                "Blocked by work-gate's PACE rule: this run has spent %.0f tokens per "
                "tool call (%d tokens over %d calls), past the %d threshold read from %s. "
                "Record the state in the log and stop.\n%s" %
                (pace, run_stats["spend"], run_stats["calls"], pace_threshold,
                 pace_threshold_file(), ceiling_escape_sentence()),
                "work-gate.pace-ceiling"
            )

# --- 11. Per-file edit brake -----------------------------------------------------------
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
        # A first Write creates a file rather than editing an existing file.
        # Check the filesystem on each call; later writes to an existing file are counted.
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
                # Past the threshold the brake stops point edits, never the file's remaining
                # work: a whole-file Write is the way through, and it is allowed here.
                if tool_name == "Write":
                    allow_and_exit()
                deny_and_exit(
                    "Blocked by work-gate's FILE-EDIT BRAKE rule: this run has now touched "
                    "%s %d times, past the %d threshold, so point edits of this file are "
                    "refused from here on. This is not a ban on finishing the file. The way "
                    "through is one whole-file rewrite: read the file, work out every "
                    "remaining change at once, and write the complete new content back in a "
                    "single Write call of this same path — a Write is allowed past the "
                    "threshold, an Edit is not. If the remaining work is too large to hold in "
                    "one rewrite, record the state with bin/work-note and hand the rest to a "
                    "fresh run. This count is per file path and per run; it never counts a "
                    "write to one of this card's own files, and a Bash call re-running the "
                    "same command however many times is never limited at all." %
                    (fp, n, FILE_EDIT_BRAKE_THRESHOLD),
                    "work-gate.file-edit-brake"
                )

# --- 13. Attach command reference to the first save-shaped call -------------------------
REFERENCE_MARKER_DIR = os.path.join(STATE_DIR, "reference-shown")

def reference_marker_path(aid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid)) if aid else "_no_agent_"
    return os.path.join(REFERENCE_MARKER_DIR, "agent-" + safe + ".txt")

def looks_like_save_call(command):
    """Return whether a command appears to record completed work."""
    if re.search(r'(^|\s)(\S*/)?bin/work-(note|commit)\b', command):
        return True
    return git_subcommand(command) in PHASE_BOUNDARY_SAVE_GIT_SUBCOMMANDS

LEGACY_BRIEF_HEADINGS = {
    "reference": "\u0421\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a \u043a\u043e\u043c\u0430\u043d\u0434:",
    "behavior": "\u041f\u043e\u0441\u0442\u043e\u044f\u043d\u043d\u043e\u0435 \u043f\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u0435 \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044f",
}

def command_reference_text(card_id, phase, card_dir_path):
    """Extract and personalize the command-reference section of a brief template."""
    if not work_root or not card_id:
        return None
    template = os.path.join(os.path.dirname(work_root.rstrip("/")), "bin", "templates",
                            "executor-brief.md")
    try:
        with open(template, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    reference_heading = "Command reference:"
    start = text.find(reference_heading)
    if start < 0:
        reference_heading = LEGACY_BRIEF_HEADINGS["reference"]
        start = text.find(reference_heading)
    if start < 0:
        return None
    behavior_heading = "Executor behavior:"
    end = text.find(behavior_heading, start)
    if end < 0:
        end = text.find(LEGACY_BRIEF_HEADINGS["behavior"], start)
    section = text[start:end] if end > start else text[start:]
    section = section.replace("{{CARD_ID}}", card_id)
    section = section.replace("{{PHASE}}", phase or "<phase>")
    section = section.replace("{{CARD_DIR}}", card_dir_path or "<card folder>")
    return section.strip()

if brief.get("role") == "executor" and tool_name == "Bash":
    marker = reference_marker_path(agent_id)
    if not os.path.exists(marker) and looks_like_save_call(command_of(tool_input)):
        reference = command_reference_text(brief.get("card"), brief.get("phase"), card_dir)
        if reference is not None:
            try:
                os.makedirs(os.path.dirname(marker), exist_ok=True)
                with open(marker, "w", encoding="utf-8") as f:
                    f.write("shown\n")
            except OSError:
                pass
            allow_and_exit(
                "Command reference, attached once per run to the first call that appears to "
                "save work. It also appears at the start of your brief.\n\n" + reference
            )

# --- 14. Repeated-search guidance ------------------------------------------------------
SEARCH_REPEAT_MAP_AT = 2      # this search is allowed, with the map attached to it
SEARCH_REPEAT_DENY_AT = 3     # this search, and every later one, is refused

SEARCH_TOOL_RE = re.compile(r'(^|[|;&]\s*)(\S*/)?(grep|egrep|fgrep|rg|ag|ack|awk|sed)\b')

def search_count_path(aid, real_fp):
    safe_agent = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    safe_file = re.sub(r'[^A-Za-z0-9_-]', '_', real_fp)
    return os.path.join(STATE_DIR, "search-counts", "agent-" + safe_agent,
                        safe_file + ".txt")

def searched_files(tname, ti):
    """Every existing regular file this one call searches inside. A Grep call names its path
    outright. A Bash call is read by taking every token of a grep/rg/sed/awk command line and
    keeping the ones that turn out to be real files on disk — which drops flags, patterns and
    directories without having to parse a shell command properly. A directory-wide search is
    therefore never counted at all: this rule is about pecking at one known file."""
    raw = []
    if tname == "Grep":
        p = ti.get("path")
        if isinstance(p, str) and p:
            raw.append(p)
    elif tname == "Bash":
        cmd = command_of(ti)
        if SEARCH_TOOL_RE.search(cmd):
            raw = re.findall(r'[^\s\'"|;&<>()]+', cmd)
    out = []
    for t in raw:
        try:
            rp = os.path.realpath(t)
        except (OSError, ValueError):
            continue
        if os.path.isfile(rp) and rp not in out:
            out.append(rp)
    return out

def map_material(real_fp):
    """What the run is handed instead of another search: how long the file actually is, and
    what the card's own map.md already says about it — the paragraphs naming that file when
    there are any, the whole map otherwise. A card with no map still gets the line count and
    the advice, so this never withholds the answer, only shortens it."""
    try:
        with open(real_fp, "r", encoding="utf-8", errors="replace") as f:
            line_count = sum(1 for _ in f)
    except OSError:
        line_count = None
    text = None
    if card_dir:
        try:
            with open(os.path.join(card_dir, "map.md"), "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = None
    excerpt = None
    if text and text.strip():
        base = os.path.basename(real_fp)
        paragraphs = [p for p in re.split(r'\n\s*\n', text) if base in p]
        excerpt = "\n\n".join(paragraphs).strip() if paragraphs else text.strip()
        if len(excerpt) > 3000:
            excerpt = excerpt[:3000] + "\n…"
    return line_count, excerpt

def search_advice(line_count, excerpt):
    length = ("%d lines" % line_count) if line_count is not None else "unknown length"
    body = ("A whole-file Read has no limit, reads this file in full (%s), and resets this "
            "count so searches are allowed again." % length)
    if excerpt:
        return body + "\n\nWhat the card's map.md already says about this file:\n\n" + excerpt
    return body + "\n\nThe card's map.md has no information about this file; read the file itself."

if brief.get("role") == "executor":
    # A whole-file Read — no offset, no limit — is the thing this rule wants to happen, so it
    # wipes the count for that path rather than merely passing.
    if tool_name == "Read" and tool_input.get("offset") is None and \
            tool_input.get("limit") is None:
        read_fp = file_path_of(tool_input)
        if read_fp:
            try:
                stale = search_count_path(agent_id, os.path.realpath(read_fp))
                if os.path.exists(stale):
                    os.remove(stale)
            except OSError:
                pass
    # Counted with the same two integer helpers rule 11 counts edits with, over their own
    # directory. Every file this one call searches is counted before any of them is judged,
    # so a command naming two files leaves neither count behind.
    searched = []
    for searched_fp in searched_files(tool_name, tool_input):
        search_path = search_count_path(agent_id, searched_fp)
        searched.append((read_file_edit_count(search_path) + 1, searched_fp))
        write_file_edit_count(search_path, searched[-1][0])
    for n, searched_fp in searched:
        if n >= SEARCH_REPEAT_DENY_AT:
            line_count, excerpt = map_material(searched_fp)
            deny_and_exit(
                "Blocked by work-gate's REPEATED SEARCH rule: search %d for %s in this run "
                "is refused. The work is not blocked; only this method is. %s" %
                (n, searched_fp, search_advice(line_count, excerpt)),
                "work-gate.repeated-search"
            )
    for n, searched_fp in searched:
        if n >= SEARCH_REPEAT_MAP_AT:
            line_count, excerpt = map_material(searched_fp)
            allow_and_exit(
                "This is the second search of %s in this run. The next search of this file "
                "will be refused. %s" % (searched_fp, search_advice(line_count, excerpt))
            )

allow_and_exit()
PYEOF
