#!/usr/bin/env python3
"""Test harness for hooks/card-touch-gate.sh (HRN-49).

Built before this hook is ever registered live in settings.json, precisely because a
registered PreToolUse hook matched on every tool takes effect for every Claude Code
session on this machine the moment settings.json names it — including the coordinator and
any other executor running concurrently in a sibling worktree. Every scenario below is run
against a scratch state directory (CARD_TOUCH_GATE_STATE_DIR), never the real one, so this
suite can never interact with an actual executor's own running count.

Run directly: python3 /Users/laptop/Dev/ai/hooks/card-touch-gate.test.py
Exit code 0 when every check passes, 1 when any fails (own PASS/FAIL harness, matching the
two sibling *.test.py files in this directory rather than unittest).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = "/Users/laptop/Dev/ai/hooks/card-touch-gate.sh"

fails = 0


def call(tool_name, tool_input, agent_id=None, state_dir=None, extra_env=None):
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    if agent_id is not None:
        payload["agent_id"] = agent_id
        payload["agent_type"] = "general-purpose"
    env = dict(os.environ)
    if state_dir:
        env["CARD_TOUCH_GATE_STATE_DIR"] = state_dir
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(["bash", HOOK], input=json.dumps(payload),
                        capture_output=True, text=True, env=env)
    try:
        out = json.loads(r.stdout)["hookSpecificOutput"]
        return out["permissionDecision"], out.get("permissionDecisionReason")
    except Exception:
        return "PARSE_FAIL(" + r.stdout[:200] + ")", None


def check(expected, label, tool_name, tool_input, agent_id=None, state_dir=None,
          extra_env=None, reason_contains=None):
    global fails
    decision, reason = call(tool_name, tool_input, agent_id=agent_id,
                             state_dir=state_dir, extra_env=extra_env)
    ok = decision == expected
    if ok and reason_contains is not None:
        ok = bool(reason) and reason_contains in reason
    fails += 0 if ok else 1
    detail = "" if ok else f"  (expected {expected}, got {decision}, reason={reason!r})"
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{detail}")


CARD = "ai/harness/tasks/ZZZ-1_fixture.md"


def fresh_dir():
    return tempfile.mkdtemp(prefix="card-touch-gate-test-")


try:
    # --- the coordinator (no agent_id at all) is never counted, never gated ---
    d = fresh_dir()
    try:
        for i in range(30):
            check("allow", f"coordinator call {i+1}/30 is never gated",
                  "Bash", {"command": "echo hi"}, agent_id=None, state_dir=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- a subagent's first call, reading its own brief, establishes the card and allows ---
    d = fresh_dir()
    try:
        check("allow", "first call (Read of its own card) establishes the card and allows",
              "Read", {"file_path": "/Users/laptop/Dev/app/" + CARD}, agent_id="agentA", state_dir=d)

        # 19 more ordinary, non-touching calls (total 20 since the card was last touched,
        # remembering the establishing Read above already counted as one) must all allow
        for i in range(19):
            check("allow", f"ordinary call {i+2}/20 since last touch still allows",
                  "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d)

        # the 21st call without a touch crosses the threshold and is refused
        check("deny", "21st call without touching the card is refused",
              "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d,
              reason_contains=CARD)
        check("deny", "refusal names the threshold",
              "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d,
              reason_contains="20 tool calls")

        # an Edit to the tracked card resets the count
        check("allow", "editing the tracked card resets the count and is itself allowed",
              "Edit", {"file_path": "/Users/laptop/Dev/app/" + CARD}, agent_id="agentA", state_dir=d)

        # after the reset, another 20 ordinary calls are allowed again before a refusal
        for i in range(20):
            check("allow", f"post-reset call {i+1}/20 allows",
                  "Bash", {"command": "echo still working"}, agent_id="agentA", state_dir=d)
        check("deny", "post-reset 21st call refuses again",
              "Bash", {"command": "echo still working"}, agent_id="agentA", state_dir=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- an Edit to some OTHER, non-card file does not reset the count ---
    d = fresh_dir()
    try:
        check("allow", "establish card via Read (call 1/20)", "Read",
              {"file_path": CARD}, agent_id="agentB", state_dir=d)
        for i in range(18):
            check("allow", f"ordinary call {i+2}/20", "Bash",
                  {"command": "ls"}, agent_id="agentB", state_dir=d)
        check("allow", "an Edit to an unrelated file counts as an ordinary call (20/20) "
                       "and does not reset anything",
              "Edit", {"file_path": "/Users/laptop/Dev/app/bin/some_other_file.go"},
              agent_id="agentB", state_dir=d)
        check("deny", "the next call after the unrelated Edit refuses — the unrelated "
                      "Edit never reset anything, so this is call 21 since the real card "
                      "was last touched",
              "Bash", {"command": "ls"}, agent_id="agentB", state_dir=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- two different agent_ids are tracked completely independently ---
    d = fresh_dir()
    try:
        check("allow", "agentC establishes its own card", "Read",
              {"file_path": "ai/harness/tasks/ZZZ-2_other.md"}, agent_id="agentC", state_dir=d)
        for i in range(20):
            check("allow", f"agentD ordinary call {i+1}/20 never affects agentC's count",
                  "Bash", {"command": "echo agentD"}, agent_id="agentD", state_dir=d)
        # agentD, never having established a card, is allowed past the threshold rather than
        # refused. This hook is registered globally against every tool call on the machine,
        # so an agent that has never named a card-shaped path may not be one of this
        # project's executors at all; refusing it would order it to edit a card it does not
        # have, which is a permanent freeze rather than a nudge.
        check("allow", "agentD allowed past threshold because no card was ever identified",
              "Bash", {"command": "echo agentD"}, agent_id="agentD", state_dir=d)
        # agentC is completely unaffected by agentD's calls
        check("allow", "agentC's own count is untouched by agentD's calls",
              "Bash", {"command": "echo agentC"}, agent_id="agentC", state_dir=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- CLAUDE_GATE_BYPASS=1 always allows, even well past the threshold ---
    d = fresh_dir()
    try:
        check("allow", "establish card (call 1/20)", "Read", {"file_path": CARD},
              agent_id="agentE", state_dir=d)
        for i in range(19):
            check("allow", f"drive agentE to the threshold ({i+2}/20)", "Bash",
                  {"command": "echo x"}, agent_id="agentE", state_dir=d)
        check("deny", "confirm agentE is now genuinely refused, without bypass",
              "Bash", {"command": "echo x"}, agent_id="agentE", state_dir=d)
        check("allow", "CLAUDE_GATE_BYPASS=1 overrides that exact same refusal",
              "Bash", {"command": "echo x"}, agent_id="agentE", state_dir=d,
              extra_env={"CLAUDE_GATE_BYPASS": "1"})
    finally:
        shutil.rmtree(d, ignore_errors=True)

finally:
    pass

# --- fail OPEN on empty stdin (deliberately the opposite of the other hooks in this
# directory — see card-touch-gate.sh's own header comment for why) ---
r = subprocess.run(["bash", HOOK], input="", capture_output=True, text=True)
ok = '"allow"' in r.stdout
fails += 0 if ok else 1
print(f"  {'PASS' if ok else 'FAIL'}  empty stdin -> allow (fail-open by design)")

# --- fail OPEN on malformed JSON, same reason ---
r = subprocess.run(["bash", HOOK], input="{not json", capture_output=True, text=True)
ok = '"allow"' in r.stdout
fails += 0 if ok else 1
print(f"  {'PASS' if ok else 'FAIL'}  malformed JSON -> allow (fail-open by design)")

print(f"\n  total passed, failures: {fails}")
sys.exit(1 if fails else 0)
