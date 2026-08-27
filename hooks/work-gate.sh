#!/usr/bin/env bash
# work-gate.sh — PreToolUse hook: the enforcement backbone of the new work-management
# system (HRN-2, ai/harness/system/project.md, "Хук на вызов инструмента", in the
# validite-app repository). A rule that used to live only in prose becomes a rule nobody can
# break by accident, because the tool call itself is refused.
#
# This file currently builds phase HRN-2.A alone — the fitness guard and caller identity —
# not the later phases (one-file-one-author, run ceilings) that HRN-2.B and HRN-2.C add on
# top of it in later runs.
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
# STATE. Everything this hook remembers between calls lives under WORK_GATE_STATE_DIR
# (default "${TMPDIR:-/tmp}/claude-work-gate", the convention hooks/card-touch-gate.sh
# already uses for its own per-agent state): verified-hash.txt (rule 2, written by
# bin/work-refusals, read only here) and briefs/agent-<agent_id>.json /
# briefs/session-<session_id>.json (rule 4).
#
# TEST OVERRIDES, read only by bin/work-refusals, never present in a real deployed session:
#   WORK_GATE_STATE_DIR   overrides the whole state tree above.
#
# Fail-closed: unparseable stdin denies.

STDIN_DATA="$(cat)"
SELF_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

exec python3 - "$SELF_PATH" "$STDIN_DATA" <<'PYEOF'
import hashlib
import json
import os
import re
import sys

self_path  = sys.argv[1]
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
    os.path.abspath(file_path_of(tool_input)) == os.path.abspath(self_path)
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
    if m_role and m_card and m_role.group(1) in KNOWN_ROLES and agent_id:
        os.makedirs(BRIEFS_DIR, exist_ok=True)
        try:
            with open(agent_brief_path(agent_id), "w", encoding="utf-8") as f:
                json.dump({"role": m_role.group(1), "card": m_card.group(1)}, f)
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
            return {"role": role, "card": card}
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

allow_and_exit()
PYEOF
