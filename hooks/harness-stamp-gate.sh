#!/usr/bin/env bash
# harness-stamp-gate.sh — PreToolUse hook: refuse to work on a machine whose deployed
# ~/.claude/settings.json disagrees with what this checkout's settings.json.template would
# render right now.
#
# HRN-155 replaces the earlier hand-kept HARNESS_VERSION counter with a digest taken from
# the rendered settings themselves: ~/.claude/.harness-stamp holds the SHA-256 digest of the
# exact bytes bootstrap.sh wrote to ~/.claude/settings.json — the sed substitution's output,
# with its trailing newlines stripped exactly the way a $(...) capture strips them, followed
# by the single trailing newline bootstrap.sh's own printf '%s\n' adds back. This hook
# reproduces those same bytes from settings.json.template and this machine's own home
# directory, digests them the same way, and compares the result against the stamp. A
# hand-kept counter needs someone to remember to raise it every time the template changes; a
# digest taken from the template itself needs no discipline at all — it changes precisely
# when the thing it guards changes, and agrees with the stamp again the moment the deploy
# that produced the new template is re-run.
#
# Equal              -> allow, silently.
# Template unreadable -> allow. A checkout with no template is not using this mechanism,
#                        which is not the same as being stale (AC4).
# Missing or different stamp -> deny everything except the calls needed to read the
#                        situation and repair it: Read, Glob, Grep, NotebookRead, TodoWrite,
#                        and a Bash call that runs bootstrap.sh.
#
# Escape hatch: CLAUDE_HARNESS_BYPASS=1 disables the gate entirely. It is named in the first
# line of every refusal, because a gate deployed by the script it guards must never be able
# to lock out the repair.
#
# Test overrides (set only by hooks/harness-stamp-gate.test.py, never by bootstrap.sh, never
# present in a real deployed session):
#   HARNESS_STAMP_GATE_REPO_DIR    overrides the checkout root the template is read from;
#                                  default: two levels up from this file's own resolved path,
#                                  the same derivation the pre-HRN-155 version of this hook
#                                  used for HARNESS_VERSION.
#   HARNESS_STAMP_GATE_STAMP_FILE  overrides the stamp file's own path; default:
#                                  ~/.claude/.harness-stamp.

STDIN_DATA="$(cat)"
HOOK_PATH="${BASH_SOURCE[0]}"

exec python3 - "$HOOK_PATH" "$STDIN_DATA" <<'PYEOF'
import hashlib
import json
import os
import sys

hook_path  = sys.argv[1]
stdin_data = sys.argv[2]

ALLOW = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

def allow_and_exit():
    print(ALLOW)
    sys.exit(0)

if os.environ.get("CLAUDE_HARNESS_BYPASS") == "1":
    allow_and_exit()

# The hook is deployed as ~/.claude/hooks/<name> symlinked into the checkout, so the
# checkout root is two levels up from the resolved path of this file — overridable so the
# test suite can point it at a scratch checkout instead of the real one.
repo_dir = os.environ.get("HARNESS_STAMP_GATE_REPO_DIR") or \
    os.path.dirname(os.path.dirname(os.path.realpath(hook_path)))
template_file = os.path.join(repo_dir, "settings.json.template")
stamp_file = os.environ.get("HARNESS_STAMP_GATE_STAMP_FILE") or \
    os.path.join(os.path.expanduser("~"), ".claude", ".harness-stamp")
bootstrap = os.path.join(repo_dir, "bootstrap.sh")

def read_first_line(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readline().strip()
    except OSError:
        return None

def expected_digest():
    """Reproduce the exact bytes bootstrap.sh writes to ~/.claude/settings.json: the
    template with every __HOME__ replaced by this machine's own home directory, its
    trailing newlines stripped exactly the way a $(...) capture strips them, then a single
    trailing newline added back — and digest those bytes with SHA-256. Returns None when the
    template cannot be read at all, which the caller treats as "this mechanism is not in
    use here", never as "stale" (AC4)."""
    try:
        with open(template_file, "rb") as f:
            template_bytes = f.read()
    except OSError:
        return None
    home = os.path.expanduser("~").encode("utf-8")
    rendered = template_bytes.replace(b"__HOME__", home)
    rendered = rendered.rstrip(b"\n") + b"\n"
    return hashlib.sha256(rendered).hexdigest()

digest = expected_digest()
if digest is None:
    allow_and_exit()

stamp = read_first_line(stamp_file)
if stamp == digest:
    allow_and_exit()

try:
    data = json.loads(stdin_data) if stdin_data.strip() else {}
except Exception:
    data = {}

tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {}) or {}

# Reading is always permitted: the refusal below tells the reader to go and look at files,
# so forbidding that would make the instruction impossible to follow.
if tool_name in ("Read", "Glob", "Grep", "NotebookRead", "TodoWrite"):
    allow_and_exit()

# The one Bash call that must get through is the repair itself.
if tool_name == "Bash":
    command = tool_input.get("command", "") or ""
    if "bootstrap.sh" in command:
        allow_and_exit()

if stamp is None:
    situation = ("this machine carries no harness stamp at all, so the configuration in "
                 "~/.claude has never been deployed from this checkout")
else:
    situation = ("this machine's harness stamp does not match the digest this checkout's "
                 "settings.json.template would render right now, so the deployed "
                 "configuration is out of date")

print(deny(
    "Run  %s  to deploy the harness, or set CLAUDE_HARNESS_BYPASS=1 to disable this gate.\n\n"
    "Blocked by harness-stamp-gate: %s. Hooks, agents, skills and rules in force right now are "
    "not the ones this checkout defines, and acting on them produces work built against stale "
    "instructions. Reading files is still allowed, as is running the deploy script above. "
    "Everything else stays blocked until the stamp matches." % (bootstrap, situation)
))
sys.exit(0)
PYEOF
