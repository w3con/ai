#!/usr/bin/env bash
# harness-stamp-gate.sh — PreToolUse hook: refuse to work on a machine whose
# harness has not been deployed at the version this checkout carries.
#
# The repository holds its deployment version in HARNESS_VERSION. bootstrap.sh
# copies that number into ~/.claude/.harness-stamp as its last action, and only
# after every target deployed successfully. This hook compares the two on every
# tool call.
#
# Equal            -> allow, silently.
# HARNESS_VERSION unreadable -> allow. A checkout with no version file is not
#                    using this mechanism, which is not the same as being stale.
# Missing or different stamp -> deny everything except the calls needed to read
#                    the situation and repair it: Read, Glob, Grep, and a Bash
#                    call that runs bootstrap.sh.
#
# Escape hatch: CLAUDE_HARNESS_BYPASS=1 disables the gate entirely. It is named
# in the first line of every refusal, because a gate deployed by the script it
# guards must never be able to lock out the repair.

STDIN_DATA="$(cat)"
HOOK_PATH="${BASH_SOURCE[0]}"

exec python3 - "$HOOK_PATH" "$STDIN_DATA" <<'PYEOF'
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

# The hook is deployed as ~/.claude/hooks/<name> symlinked into the checkout, so
# the checkout root is two levels up from the resolved path of this file.
repo_dir = os.path.dirname(os.path.dirname(os.path.realpath(hook_path)))
version_file = os.path.join(repo_dir, "HARNESS_VERSION")
stamp_file = os.path.join(os.path.expanduser("~"), ".claude", ".harness-stamp")
bootstrap = os.path.join(repo_dir, "bootstrap.sh")

def read_first_line(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readline().strip()
    except OSError:
        return None

repo_version = read_first_line(version_file)
if not repo_version:
    allow_and_exit()

stamp = read_first_line(stamp_file)
if stamp == repo_version:
    allow_and_exit()

try:
    data = json.loads(stdin_data) if stdin_data.strip() else {}
except Exception:
    data = {}

tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {}) or {}

# Reading is always permitted: the refusal below tells the reader to go and look
# at files, so forbidding that would make the instruction impossible to follow.
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
    situation = ("this machine is stamped at harness version %s while the checkout carries "
                 "version %s, so the deployed configuration is out of date" % (stamp, repo_version))

print(deny(
    "Run  %s  to deploy the harness, or set CLAUDE_HARNESS_BYPASS=1 to disable this gate.\n\n"
    "Blocked by harness-stamp-gate: %s. Hooks, agents, skills and rules in force right now are "
    "not the ones this checkout defines, and acting on them produces work built against stale "
    "instructions. Reading files is still allowed, as is running the deploy script above. "
    "Everything else stays blocked until the stamp matches." % (bootstrap, situation)
))
sys.exit(0)
PYEOF
