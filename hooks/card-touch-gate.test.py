#!/usr/bin/env python3
"""Test harness for hooks/card-touch-gate.sh (HRN-49, restructured by HRN-109).

Built before this hook is ever registered live in settings.json, precisely because a
registered PreToolUse hook matched on every tool takes effect for every Claude Code
session on this machine the moment settings.json names it — including the coordinator and
any other executor running concurrently in a sibling worktree. Every scenario below is run
against a scratch state directory (CARD_TOUCH_GATE_STATE_DIR) and a scratch fixture
transcript file, never real state or a real session transcript, so this suite can never
interact with an actual executor's own running count.

Since HRN-109, the hook no longer guesses a run's card from any tool call the run makes
itself — it reads the brief the run was actually spawned with, recovered from a
transcript_path field in its own hook payload naming the coordinator's durable session
transcript, which records every Task/Agent spawn as a JSON object carrying that spawned
agent's agentId, prompt and description. Every scenario below that wants a card
established therefore builds a small fixture transcript file with fake_transcript() and
passes its path as transcript_path, rather than putting a card-shaped path in the tool
call's own file_path/command/prompt/description the way the pre-HRN-109 suite did.

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


def fake_transcript(entries):
    """A scratch file shaped like a real coordinator session transcript: one JSON object
    per line, each carrying a top-level toolUseResult with agentId/prompt/description —
    exactly the shape confirmed against a live payload while building HRN-109 (see that
    card's own Working state). `entries` is a list of dicts, each at least {"agentId":
    …, "prompt": …}; "description" defaults to "" when omitted."""
    fd, path = tempfile.mkstemp(prefix="card-touch-gate-transcript-", suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for e in entries:
            line = {
                "toolUseResult": {
                    "agentId": e["agentId"],
                    "prompt": e.get("prompt", ""),
                    "description": e.get("description", ""),
                }
            }
            f.write(json.dumps(line) + "\n")
    return path


def call(tool_name, tool_input, agent_id=None, state_dir=None, transcript_path=None,
         extra_env=None):
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    if agent_id is not None:
        payload["agent_id"] = agent_id
        payload["agent_type"] = "general-purpose"
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
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
          transcript_path=None, extra_env=None, reason_contains=None):
    global fails
    decision, reason = call(tool_name, tool_input, agent_id=agent_id, state_dir=state_dir,
                             transcript_path=transcript_path, extra_env=extra_env)
    ok = decision == expected
    if ok and reason_contains is not None:
        ok = bool(reason) and reason_contains in reason
    fails += 0 if ok else 1
    detail = "" if ok else f"  (expected {expected}, got {decision}, reason={reason!r})"
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{detail}")


CARD = "ai/harness/tasks/ZZZ-1_fixture.md"
OTHER_CARD = "ai/harness/tasks/ZZZ-2_unrelated.md"


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

    # --- the card is established from the spawn brief, not from any call the run makes ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentA", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "first call establishes the card from the transcript-recovered "
                       "brief, even though this call's own tool_input names nothing",
              "Bash", {"command": "ls -la"}, agent_id="agentA", state_dir=d,
              transcript_path=t)

        # 19 more ordinary, non-touching calls (total 20 since the card was last touched)
        for i in range(19):
            check("allow", f"ordinary call {i+2}/20 since last touch still allows",
                  "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d,
                  transcript_path=t)

        # the 21st call without a touch crosses the threshold and is refused, naming the
        # card recovered from the brief
        check("deny", "21st call without touching the card is refused",
              "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d,
              transcript_path=t, reason_contains=CARD)
        check("deny", "refusal names the threshold",
              "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d,
              transcript_path=t, reason_contains="20 tool calls")

        # an Edit to the tracked card resets the count
        check("allow", "editing the tracked card resets the count and is itself allowed",
              "Edit", {"file_path": "/Users/laptop/Dev/app/" + CARD}, agent_id="agentA",
              state_dir=d, transcript_path=t)

        # after the reset, another 20 ordinary calls are allowed again before a refusal
        for i in range(20):
            check("allow", f"post-reset call {i+1}/20 allows",
                  "Bash", {"command": "echo still working"}, agent_id="agentA",
                  state_dir=d, transcript_path=t)
        check("deny", "post-reset 21st call refuses again",
              "Bash", {"command": "echo still working"}, agent_id="agentA", state_dir=d,
              transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- the shared checkout's copy of a card and an executor's own worktree copy of the
    # same card count as one, because touches_card compares the canonical suffix alone
    # (cfbd25d, kept by this restructuring — the brief always names the shared-checkout
    # path, since that is what plan-gate.sh requires, while the executor's own Edit call
    # names its own worktree's longer path) ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentW",
                           "prompt": f"Implement /Users/laptop/Dev/app/{CARD}"}])
    try:
        check("allow", "card established from the brief's shared-checkout path",
              "Read", {"file_path": "/Users/laptop/Dev/app/README.md"}, agent_id="agentW",
              state_dir=d, transcript_path=t)
        worktree_path = ("/Users/laptop/Dev/app/.claude/worktrees/agent-agentW/" + CARD)
        check("allow", "an Edit at the executor's own worktree path still touches the "
                       "same card and resets the count",
              "Edit", {"file_path": worktree_path}, agent_id="agentW", state_dir=d,
              transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- HRN-109.6: a run that reads, greps and edits an UNRELATED card first is still
    # asked for its brief's own card when it crosses the threshold — this is the exact
    # failure recorded in this card's own "Reasons to exist": an executor forced to write
    # a paragraph into a card that was never its own, just to satisfy this hook ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentP", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "call 1/20: Read of an unrelated, closed card never establishes it",
              "Read", {"file_path": "/Users/laptop/Dev/app/" + OTHER_CARD},
              agent_id="agentP", state_dir=d, transcript_path=t)
        check("allow", "call 2/20: Grep across the unrelated card never establishes it",
              "Grep", {"pattern": "status", "path": "/Users/laptop/Dev/app/" + OTHER_CARD},
              agent_id="agentP", state_dir=d, transcript_path=t)
        check("allow", "call 3/20: an actual Edit to the unrelated card does not steal "
                       "the tracked identity — the card was already established from the "
                       "brief on call 1 and is never replaced",
              "Edit", {"file_path": "/Users/laptop/Dev/app/" + OTHER_CARD},
              agent_id="agentP", state_dir=d, transcript_path=t)
        for i in range(17):
            check("allow", f"ordinary call {i+4}/20 since the real card was last touched "
                           "(never, in this run)",
                  "Bash", {"command": "echo x"}, agent_id="agentP", state_dir=d,
                  transcript_path=t)
        check("deny", "the 21st call refuses, and names this run's OWN card from its "
                      "brief — never the unrelated card it read, grepped and edited",
              "Bash", {"command": "echo x"}, agent_id="agentP", state_dir=d,
              transcript_path=t, reason_contains=CARD)
        # and the denial reason must NOT name the unrelated card at all
        decision, reason = call("Bash", {"command": "echo x"}, agent_id="agentP",
                                 state_dir=d, transcript_path=t)
        ok = decision == "deny" and reason and OTHER_CARD not in reason
        fails += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  the denial reason never names the unrelated "
              f"card the run merely read, grepped and edited"
              f"{'' if ok else f'  (reason={reason!r})'}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- fail open when the brief cannot be determined at all ---
    d = fresh_dir()
    try:
        check("allow", "transcript_path names a file that does not exist on disk",
              "Bash", {"command": "echo x"}, agent_id="agentQ", state_dir=d,
              transcript_path="/tmp/does-not-exist-hrn109-" + os.urandom(4).hex() + ".jsonl")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    d = fresh_dir()
    t = fake_transcript([{"agentId": "some-other-agent", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "the transcript exists but holds no spawn record for THIS agent_id",
              "Bash", {"command": "echo x"}, agent_id="agentR", state_dir=d,
              transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentS",
                           "prompt": "Fix the recalled-goods bug, see ai/plans/plan_recalled-goods.md"}])
    try:
        check("allow", "the recovered brief names a legacy plan, not a task card, so no "
                       "card is ever established",
              "Bash", {"command": "echo x"}, agent_id="agentS", state_dir=d,
              transcript_path=t)
        check("allow", "still allowed well past the threshold, for the same reason",
              "Bash", {"command": "echo x"}, agent_id="agentS", state_dir=d,
              transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentT", "prompt": "just fix the bug, no path named"}])
    try:
        check("allow", "the recovered brief names no .md path at all",
              "Bash", {"command": "echo x"}, agent_id="agentT", state_dir=d,
              transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- driving an unrecoverable-brief agent 30 calls deep never denies it ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentU", "prompt": "no brief path here either"}])
    try:
        for i in range(30):
            check("allow", f"agentU call {i+1}/30 allowed — no card ever recoverable",
                  "Bash", {"command": "echo x"}, agent_id="agentU", state_dir=d,
                  transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- two different agent_ids, each with its own brief in the SAME transcript file (the
    # ordinary case — one coordinator session spawning several executors), are tracked
    # completely independently ---
    d = fresh_dir()
    t = fake_transcript([
        {"agentId": "agentC", "prompt": f"Implement {CARD}"},
        {"agentId": "agentD", "prompt": f"Implement {OTHER_CARD}"},
    ])
    try:
        check("allow", "agentC establishes its own card from its own brief", "Read",
              {"file_path": "/tmp/whatever"}, agent_id="agentC", state_dir=d,
              transcript_path=t)
        for i in range(20):
            check("allow", f"agentD ordinary call {i+1}/20 never affects agentC's count",
                  "Bash", {"command": "echo agentD"}, agent_id="agentD", state_dir=d,
                  transcript_path=t)
        check("deny", "agentD is refused on its own 21st call, naming ITS OWN card",
              "Bash", {"command": "echo agentD"}, agent_id="agentD", state_dir=d,
              transcript_path=t, reason_contains=OTHER_CARD)
        check("allow", "agentC's own count is untouched by agentD's calls",
              "Bash", {"command": "echo agentC"}, agent_id="agentC", state_dir=d,
              transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- CLAUDE_GATE_BYPASS=1 always allows, even well past the threshold ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentE", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "establish card (call 1/20)", "Read", {"file_path": "/tmp/whatever"},
              agent_id="agentE", state_dir=d, transcript_path=t)
        for i in range(19):
            check("allow", f"drive agentE to the threshold ({i+2}/20)", "Bash",
                  {"command": "echo x"}, agent_id="agentE", state_dir=d, transcript_path=t)
        check("deny", "confirm agentE is now genuinely refused, without bypass",
              "Bash", {"command": "echo x"}, agent_id="agentE", state_dir=d,
              transcript_path=t)
        check("allow", "CLAUDE_GATE_BYPASS=1 overrides that exact same refusal",
              "Bash", {"command": "echo x"}, agent_id="agentE", state_dir=d,
              transcript_path=t, extra_env={"CLAUDE_GATE_BYPASS": "1"})
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

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
