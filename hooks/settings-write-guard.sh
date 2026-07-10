#!/usr/bin/env bash
# settings-write-guard.sh — PreToolUse hook: refuse Bash commands that WRITE to a
# settings.json (or settings.local.json), so the permission classifier on the
# Edit/Write tools cannot be sidestepped by switching tool.
#
# What IS blocked: a Bash command whose effect is to create, overwrite, patch,
#                  move, copy onto, or delete a settings file. Detected forms:
#                    > / >> redirect onto it, tee, mv/cp onto it, rm, sed -i,
#                    truncate, dd of=, and python/node code that opens it for
#                    writing (write_text, json.dump, open(..., "w")).
# What is NOT blocked: reading it. `cat`, `grep`, `jq`, `python3 -m json.tool
#                      settings.json > /dev/null` and friends pass, because the
#                      redirect target there is /dev/null, not the settings file.
#
# Why this exists. On 2026-07-10 a build agent was denied a `Write` to
# settings.json by the auto-mode classifier, and completed the same write with a
# `cat > … <<EOF` heredoc in Bash. The file it produced was correct, so nothing
# broke — but a prohibition that is lifted by changing tool is not a prohibition.
# This is the same defect the plan-gate hook had (it checked for a scope PASS in
# any nearby plan rather than in the plan handed to the executor) and it gets the
# same treatment: a deterministic PreToolUse check that does not care which tool
# you reached for. Approved by Alex, 2026-07-10 («Классификатор … Да, чини»).
#
# The intended path for editing settings is the Edit or Write tool. If those are
# denied, that denial is the answer: stop and ask Alex. Do not route around it.
#
# Bypass: CLAUDE_GATE_BYPASS=1 (shared with plan-gate.sh).
# Fail-closed: any parse error → deny.

STDIN_DATA="$(cat)"

exec python3 - "$STDIN_DATA" <<'PYEOF'
import sys
import os
import re
import json

stdin_data = sys.argv[1]

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

DENY_WRITE = (
    "Blocked by settings-write-guard: this Bash command writes to a settings.json. "
    "Settings files must be edited with the Edit or Write tool, never through the "
    "shell — otherwise a denial on those tools can be sidestepped by switching tool. "
    "If Edit/Write is itself denied for this file, that denial IS the answer: stop "
    "and ask Alex rather than routing around it. Reading the file is not blocked."
)

DENY_ERROR = "Blocked by settings-write-guard: gate error, failing closed."

try:
    if not stdin_data.strip():
        raise ValueError("empty stdin")
    data = json.loads(stdin_data)
except Exception:
    print(deny_json(DENY_ERROR))
    sys.exit(0)

if os.environ.get("CLAUDE_GATE_BYPASS") == "1":
    print(ALLOW_JSON)
    sys.exit(0)

if data.get("tool_name") != "Bash":
    print(ALLOW_JSON)
    sys.exit(0)

cmd = (data.get("tool_input") or {}).get("command") or ""
if "settings.json" not in cmd and "settings.local.json" not in cmd:
    print(ALLOW_JSON)
    sys.exit(0)

# A path token ENDING in settings.json / settings.local.json, optionally quoted.
# The trailing look-ahead matters: without it, `settings.json` also matches the
# prefix of `settings.json.bak-2026-07-10`, so the guard would refuse to let anyone
# delete a backup — a file that is not a live settings file and, in this repository's
# history, held a plaintext API key that needed removing. Match the whole name only.
TARGET = r'''["']?[^\s"'|;&<>]*settings(?:\.local)?\.json(?![\w.-])["']?'''

# Shell forms. Each names the settings file as the thing being written, so a bare
# mention of the name elsewhere in the command cannot trigger them.
#
# GAP is the run of characters allowed between a command word and its target. It
# excludes newlines as well as the shell separators, because a command is one line:
# without that, `[^|;&]*` walks across line breaks and stitches a "dangerous
# command" out of three innocent ones. That is not hypothetical — on 2026-07-10 the
# in-place-edit rule matched `sed 's/^/  /'` on one line, the `-i` of `git grep -i`
# on the next, and the words `settings.json` on a third, and blocked a read-only
# command. Third false positive of the day from this file; each was a real bug.
GAP = r'[^|;&\n]*'

SHELL_PATTERNS = [
    # > target   or   >> target   (but NOT  > /dev/null)
    re.compile(r'>>?[ \t]*' + TARGET),
    # tee [-a] target
    re.compile(r'\btee\b' + GAP + TARGET),
    # mv/cp/install/ln with the settings file as the final (destination) argument
    re.compile(r'\b(?:mv|cp|install|ln)\b' + GAP + r'[ \t]' + TARGET + r'[ \t]*(?:$|[|;&\n])'),
    # rm target
    re.compile(r'\brm\b' + GAP + TARGET),
    # sed -i / --in-place, with -i as its own flag rather than any stray "-i"
    re.compile(r'\bsed\b' + GAP + r'(?:-i\b|--in-place)' + GAP + TARGET),
    re.compile(r'\b(?:truncate|shred)\b' + GAP + TARGET),
    re.compile(r'\bdd\b' + GAP + r'of=[ \t]*' + TARGET),
]

# Interpreter forms: a write call in embedded Python/JS whose TARGET is a settings
# file. The settings path must sit inside the call itself — not merely somewhere in
# the same command.
#
# Two earlier versions were wrong, and both were caught by running the thing rather
# than reasoning about it:
#   1. matching `write_text(` anywhere → blocked a script editing a plan file that
#      happened to contain the word "settings.json" in a search string;
#   2. matching a settings path within 120 characters of the write call → same false
#      positive, because in `t.replace('… settings.json …'); p.write_text(t)` the
#      mention and the call are neighbours.
# A guard that blocks routine work is a guard people learn to switch off, so the rule
# is now narrow on purpose.
#
# Known gap, stated rather than hidden: a path bound to a variable first
# (`p = Path("settings.json"); p.write_text(...)`) is not caught. Closing it needs
# real parsing of an arbitrary interpreter language, which is out of proportion here.
# The shell forms above cover the realistic route — a heredoc — which is the one that
# was actually used on 2026-07-10.
SETTINGS_STR = r'''["'][^"']*settings(?:\.local)?\.json["']'''
INTERPRETER_PATTERNS = [
    # pathlib.Path("…/settings.json").write_text(…)
    re.compile(r'Path\s*\(\s*' + SETTINGS_STR + r'\s*\)\s*\.\s*write_text\s*\('),
    # open("…/settings.json", "w")   — also covers json.dump(x, open(…, "w"))
    re.compile(r'open\s*\(\s*' + SETTINGS_STR + r'\s*,[^)]*["\']w'),
    # fs.writeFileSync("…/settings.json", …)
    re.compile(r'writeFileSync\s*\(\s*' + SETTINGS_STR),
]

for pat in SHELL_PATTERNS + INTERPRETER_PATTERNS:
    if pat.search(cmd):
        print(deny_json(DENY_WRITE))
        sys.exit(0)

print(ALLOW_JSON)
sys.exit(0)
PYEOF
