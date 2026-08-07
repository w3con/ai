#!/usr/bin/env python3
"""Test harness for the HRN-47 candidate of hooks/card-touch-gate.sh (extends the HRN-49 /
HRN-109 suite this file is copied from, adding coverage for the PACE rule and the
SEARCH-AGENT ceiling HRN-47 adds to the same hook — see that file's own header for what the
TOUCH rule, the PACE rule and the SEARCH-AGENT mechanism each are and why they are kept
separate).

Built before this hook is ever registered live in settings.json, precisely because a
registered PreToolUse hook matched on every tool takes effect for every Claude Code session
on this machine the moment settings.json names it — including the coordinator and any other
executor running concurrently in a sibling worktree. Every scenario below is run against a
scratch state directory (CARD_TOUCH_GATE_STATE_DIR) and a scratch fixture transcript file,
never real state or a real session transcript, so this suite can never interact with an
actual executor's own running count. The PACE-rule scenarios also need a real card file on
disk to read a live ticked-box count and an optional `rate:` field from, so those additionally
run against a scratch CLAUDE_PROJECT_DIR built fresh per scenario by fixture_project() below
— never the real app repository.

Since HRN-109, the hook no longer guesses a run's card from any tool call the run makes
itself — it reads the brief the run was actually spawned with, recovered from a
transcript_path field in its own hook payload naming the coordinator's durable session
transcript, which records every Task/Agent spawn as a JSON object carrying that spawned
agent's agentId, prompt and description. Every scenario below that wants a card established
therefore builds a small fixture transcript file with fake_transcript() and passes its path
as transcript_path, rather than putting a card-shaped path in the tool call's own
file_path/command/prompt/description the way the pre-HRN-109 suite did.

Every TOUCH-rule-only scenario below (everything carried over from the pre-HRN-47 suite)
deliberately never creates a real card file on disk. That is not an oversight: the TOUCH
rule needs no file at all (it only counts calls since the last card-shaped Edit/Write), and
the PACE rule fails open — silently, allowing every call — whenever it cannot open the
card's real file, which is exactly the condition these scenarios are already in. So the
21st-call denial in each of them is still, and only, the TOUCH rule firing, and several of
those scenarios below assert that explicitly (reason_contains="TOUCH rule") to lock in that
the PACE rule's own fail-open never masks or interferes with it.

Run directly: python3 /Users/laptop/Dev/ai/hooks/card-touch-gate.test.py [candidate-path]
With no argument this runs against the installed hook at
/Users/laptop/Dev/ai/hooks/card-touch-gate.sh; given one argument it runs against that file
instead, which is what bin/hook-install uses to test a candidate before installing it.
Exit code 0 when every check passes, 1 when any fails (own PASS/FAIL harness, matching the
sibling *.test.py files in this directory rather than unittest).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else "/Users/laptop/Dev/ai/hooks/card-touch-gate.sh"

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


def fixture_project(cards=None):
    """A scratch directory to use as CLAUDE_PROJECT_DIR, so the PACE rule's own file reads
    (read_ticked_boxes, read_card_rate) have a real, controlled file to open instead of
    silently falling open — and so every scenario that establishes a card is fully isolated
    from whatever the test process's own cwd happens to hold, never relying on the fallback
    to os.getcwd() that resolve_card_path() also tries. `cards` is a dict of
    {relative_path: {"ticked": N, "unticked": M, "rate": R}}, M and R optional (M defaults
    to 1, R to no rate: line at all, meaning the hook falls back to its own default rate).
    Passing no cards at all (or None) still returns a real, empty directory — used by
    scenarios that want the PACE rule to fail open because the named card simply is not
    there."""
    root = tempfile.mkdtemp(prefix="card-touch-gate-project-")
    for rel_path, spec in (cards or {}).items():
        write_fixture_card(root, rel_path, spec.get("ticked", 0),
                            unticked=spec.get("unticked", 1), rate=spec.get("rate"))
    return root


def write_fixture_card(root, rel_path, ticked, unticked=1, rate=None):
    """Write (or overwrite) a minimal, real card file at root/rel_path with `ticked` ticked
    checkpoint lines and `unticked` unticked ones, optionally carrying a `rate:` frontmatter
    field. Used both by fixture_project() at scenario setup and, on its own, mid-scenario to
    simulate an executor ticking a box — so a test can prove the PACE rule's budget widens
    live off the same file, on the very next call, with no restart of anything."""
    abs_path = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    lines = ["---", "id: ZZZ-1"]
    if rate is not None:
        lines.append(f"rate: {rate}")
    lines.append("---")
    lines.append("## Checkpoints")
    for i in range(ticked):
        lines.append(f"- [x] ZZZ-1.{i + 1} — done")
    for i in range(unticked):
        lines.append(f"- [ ] ZZZ-1.{ticked + i + 1} — todo")
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return abs_path


def call(tool_name, tool_input, agent_id=None, state_dir=None, transcript_path=None,
         extra_env=None, project_dir=None, agent_type="general-purpose"):
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    if agent_id is not None:
        payload["agent_id"] = agent_id
        payload["agent_type"] = agent_type
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    env = dict(os.environ)
    if state_dir:
        env["CARD_TOUCH_GATE_STATE_DIR"] = state_dir
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = project_dir
    else:
        env.pop("CLAUDE_PROJECT_DIR", None)
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
          transcript_path=None, extra_env=None, reason_contains=None, project_dir=None,
          agent_type="general-purpose", reason_not_contains=None):
    global fails
    decision, reason = call(tool_name, tool_input, agent_id=agent_id, state_dir=state_dir,
                             transcript_path=transcript_path, extra_env=extra_env,
                             project_dir=project_dir, agent_type=agent_type)
    ok = decision == expected
    if ok and reason_contains is not None:
        ok = bool(reason) and reason_contains in reason
    if ok and reason_not_contains is not None:
        ok = bool(reason) and reason_not_contains not in reason
    fails += 0 if ok else 1
    detail = "" if ok else f"  (expected {expected}, got {decision}, reason={reason!r})"
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{detail}")


CARD = "ai/harness/tasks/ZZZ-1_fixture.md"
OTHER_CARD = "ai/harness/tasks/ZZZ-2_unrelated.md"


def fresh_dir():
    return tempfile.mkdtemp(prefix="card-touch-gate-test-")


try:
    # =====================================================================================
    # Carried over from the pre-HRN-47 suite, unchanged in substance: every scenario below
    # never creates a real card file, so the PACE rule fails open throughout and every
    # denial below is the TOUCH rule alone, on exactly its original terms.
    # =====================================================================================

    # --- the coordinator (no agent_id at all) is never counted, never gated, by either
    # rule ---
    d = fresh_dir()
    try:
        for i in range(30):
            check("allow", f"coordinator call {i+1}/30 is never gated",
                  "Bash", {"command": "echo hi"}, agent_id=None, state_dir=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- the card is established from the spawn brief, not from any call the run makes;
    # the TOUCH rule fires at its own, unchanged threshold ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentA", "prompt": f"Implement {CARD}"}])
    empty_proj = fixture_project()
    try:
        check("allow", "first call establishes the card from the transcript-recovered "
                       "brief, even though this call's own tool_input names nothing",
              "Bash", {"command": "ls -la"}, agent_id="agentA", state_dir=d,
              transcript_path=t, project_dir=empty_proj)

        # 19 more ordinary, non-touching calls (total 20 since the card was last touched)
        for i in range(19):
            check("allow", f"ordinary call {i+2}/20 since last touch still allows",
                  "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d,
                  transcript_path=t, project_dir=empty_proj)

        # the 21st call without a touch crosses the TOUCH rule's own threshold and is
        # refused, naming the card recovered from the brief; the PACE rule never gets a
        # chance to speak because it fails open (no real card file under empty_proj)
        check("deny", "21st call without touching the card is refused by the TOUCH rule",
              "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d,
              transcript_path=t, project_dir=empty_proj, reason_contains=CARD)
        check("deny", "refusal names the TOUCH rule by name and its threshold",
              "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d,
              transcript_path=t, project_dir=empty_proj, reason_contains="TOUCH rule")
        check("deny", "refusal states the threshold in tool calls",
              "Bash", {"command": "go test ./..."}, agent_id="agentA", state_dir=d,
              transcript_path=t, project_dir=empty_proj, reason_contains="20 tool calls")

        # an Edit to the tracked card resets the TOUCH rule's own count (unchanged)
        check("allow", "editing the tracked card resets the TOUCH rule's count and is "
                       "itself allowed", "Edit",
              {"file_path": "/Users/laptop/Dev/app/" + CARD}, agent_id="agentA",
              state_dir=d, transcript_path=t, project_dir=empty_proj)

        # after the reset, another 20 ordinary calls are allowed again before a refusal
        for i in range(20):
            check("allow", f"post-reset call {i+1}/20 allows",
                  "Bash", {"command": "echo still working"}, agent_id="agentA",
                  state_dir=d, transcript_path=t, project_dir=empty_proj)
        check("deny", "post-reset 21st call refuses again, still the TOUCH rule",
              "Bash", {"command": "echo still working"}, agent_id="agentA", state_dir=d,
              transcript_path=t, project_dir=empty_proj, reason_contains="TOUCH rule")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(empty_proj, ignore_errors=True)
        os.remove(t)

    # --- the shared checkout's copy of a card and an executor's own worktree copy of the
    # same card count as one, because touches_card compares the canonical suffix alone ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentW",
                           "prompt": f"Implement /Users/laptop/Dev/app/{CARD}"}])
    try:
        check("allow", "card established from the brief's shared-checkout path",
              "Read", {"file_path": "/Users/laptop/Dev/app/README.md"}, agent_id="agentW",
              state_dir=d, transcript_path=t)
        worktree_path = ("/Users/laptop/Dev/app/.claude/worktrees/agent-agentW/" + CARD)
        check("allow", "an Edit at the executor's own worktree path still touches the "
                       "same card and resets the TOUCH rule's count",
              "Edit", {"file_path": worktree_path}, agent_id="agentW", state_dir=d,
              transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- HRN-109.6: a run that reads, greps and edits an UNRELATED card first is still
    # asked for its brief's own card when it crosses the TOUCH rule's threshold ---
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
        check("deny", "the 21st call refuses (TOUCH rule), and names this run's OWN card "
                      "from its brief — never the unrelated card it read, grepped and "
                      "edited",
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

    # --- fail open when the brief cannot be determined at all — untouched by either rule
    # ---
    d = fresh_dir()
    try:
        check("allow", "transcript_path names a file that does not exist on disk",
              "Bash", {"command": "echo x"}, agent_id="agentQ", state_dir=d,
              transcript_path="/tmp/does-not-exist-hrn47-" + os.urandom(4).hex() + ".jsonl")
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
        check("allow", "still allowed well past the TOUCH threshold, for the same reason",
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

    # --- driving an unrecoverable-brief agent 30 calls deep never denies it, under either
    # rule ---
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

    # --- two different agent_ids, each with its own brief in the SAME transcript file, are
    # tracked completely independently under the TOUCH rule ---
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

    # --- CLAUDE_GATE_BYPASS=1 always allows, even well past the TOUCH threshold ---
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

    # =====================================================================================
    # New for HRN-47: the PACE rule (relay tier, refuse tier, live-widening off the card's
    # own ticked-box count, and the optional per-card `rate:` override), proved against a
    # real fixture card file rather than a bare token.
    # =====================================================================================

    # --- the PACE rule can fire while the TOUCH rule's own count is nowhere near its
    # threshold, because a card touch resets the TOUCH rule's count but never the PACE
    # rule's total — proving the two rules are genuinely independent, not one comparison in
    # two names ---
    d = fresh_dir()
    proj = fixture_project({CARD: {"ticked": 0}})  # default rate: relay 20, refuse 28
    t = fake_transcript([{"agentId": "agentPace1", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "agentPace1 establishes the card (total call 1/20)", "Read",
              {"file_path": "/tmp/x"}, agent_id="agentPace1", state_dir=d,
              transcript_path=t, project_dir=proj)

        # 3 cycles of (4 ordinary calls + 1 touch) = 15 calls; each touch resets the TOUCH
        # rule's own count to 0, so it never climbs past 4 within a cycle, while the PACE
        # rule's total keeps advancing regardless, reaching 16 after these three cycles
        for cycle in range(3):
            for i in range(4):
                check("allow", f"cycle {cycle+1} ordinary call {i+1}/4 keeps the TOUCH "
                               "rule's own count low", "Bash", {"command": "echo x"},
                      agent_id="agentPace1", state_dir=d, transcript_path=t,
                      project_dir=proj)
            check("allow", f"cycle {cycle+1} touch resets the TOUCH rule's own count to 0 "
                           "(PACE's own total is unaffected by this reset)",
                  "Edit", {"file_path": "/Users/laptop/Dev/app/" + CARD},
                  agent_id="agentPace1", state_dir=d, transcript_path=t, project_dir=proj)

        # total is now 16 (1 + 3*5); 4 more ordinary calls bring it to 17, 18, 19, 20 — all
        # still within the PACE relay budget of 20 (rate 20 x (0 ticked + 1))
        for i in range(4):
            check("allow", f"post-cycles ordinary call {i+1}/4, PACE total now "
                           f"{17+i}/20, TOUCH's own count only {i+1}/20",
                  "Bash", {"command": "echo x"}, agent_id="agentPace1", state_dir=d,
                  transcript_path=t, project_dir=proj)

        # the 21st total call crosses the PACE relay budget (20) while the TOUCH rule's own
        # count is only 5 — nowhere near ITS OWN threshold of 20 — so this denial must be
        # the PACE rule's, not the TOUCH rule's
        check("deny", "PACE relay fires at total call 21 while the TOUCH rule's own count "
                      "is only 5/20 — proof the two rules are independent",
              "Bash", {"command": "echo x"}, agent_id="agentPace1", state_dir=d,
              transcript_path=t, project_dir=proj, reason_contains="PACE rule (relay",
              # the PACE message legitimately NAMES the TOUCH rule in passing, to explain
              # the two are separate — what must NOT appear is the TOUCH rule's own denial
              # actually firing, i.e. its own message's distinct lead-in
              reason_not_contains="Blocked by card-touch-gate's TOUCH rule")

        # an Edit/Write to the tracked card is still let through even while PACE is over
        # its relay budget
        check("allow", "an Edit to the tracked card is allowed through the PACE relay, "
                       "exactly as AC11 requires",
              "Edit", {"file_path": "/Users/laptop/Dev/app/" + CARD},
              agent_id="agentPace1", state_dir=d, transcript_path=t, project_dir=proj)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)
        os.remove(t)

    # --- the PACE rule's relay tier and refuse tier, and the optional per-card `rate:`
    # override (AC5), proved together against a card that overrides the default rate ---
    d = fresh_dir()
    proj = fixture_project({CARD: {"ticked": 0, "rate": 5}})  # relay 5, refuse 5*1.4=7
    t = fake_transcript([{"agentId": "agentPace2", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "agentPace2 establishes the card under its own rate:5 (total 1/5)",
              "Read", {"file_path": "/tmp/x"}, agent_id="agentPace2", state_dir=d,
              transcript_path=t, project_dir=proj)
        for i in range(4):
            check("allow", f"ordinary call {i+2}/5, still within the card's own relay "
                           "budget of 5", "Bash", {"command": "echo x"},
                  agent_id="agentPace2", state_dir=d, transcript_path=t, project_dir=proj)
        check("deny", "6th total call crosses the card's own relay budget (5) — relay "
                      "tier, not refuse", "Bash", {"command": "echo x"},
              agent_id="agentPace2", state_dir=d, transcript_path=t, project_dir=proj,
              reason_contains="PACE rule (relay")
        check("deny", "7th total call is still within the refuse ceiling (7) — relay "
                      "tier again, not refuse", "Bash", {"command": "echo x"},
              agent_id="agentPace2", state_dir=d, transcript_path=t, project_dir=proj,
              reason_contains="PACE rule (relay")
        check("deny", "8th total call crosses the refuse ceiling (7) — refuse tier",
              "Bash", {"command": "echo x"}, agent_id="agentPace2", state_dir=d,
              transcript_path=t, project_dir=proj, reason_contains="PACE rule (refuse")
        check("allow", "an Edit to the tracked card is still allowed through even at the "
                       "refuse tier", "Edit", {"file_path": "/Users/laptop/Dev/app/" + CARD},
              agent_id="agentPace2", state_dir=d, transcript_path=t, project_dir=proj)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)
        os.remove(t)

    # --- ticking a checkpoint box widens the PACE budget live, on the very next call, off
    # the same card file — no restart, no reset needed ---
    d = fresh_dir()
    proj = fixture_project({CARD: {"ticked": 0, "rate": 5}})  # relay 5, refuse 7
    t = fake_transcript([{"agentId": "agentWiden", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "establish card (rate 5, ticked 0)", "Read", {"file_path": "/tmp/x"},
              agent_id="agentWiden", state_dir=d, transcript_path=t, project_dir=proj)
        for i in range(4):
            check("allow", f"ordinary call {i+2}/5", "Bash", {"command": "echo x"},
                  agent_id="agentWiden", state_dir=d, transcript_path=t, project_dir=proj)
        check("deny", "6th total call crosses the relay budget of 5 (ticked still 0)",
              "Bash", {"command": "echo x"}, agent_id="agentWiden", state_dir=d,
              transcript_path=t, project_dir=proj, reason_contains="PACE rule (relay")

        # simulate the executor ticking one checkpoint box on the real card file — the
        # relay budget is now 5*(1+1)=10
        write_fixture_card(proj, CARD, ticked=1, rate=5)

        check("allow", "after the box tick widens the live budget to 5*(1+1)=10, the 7th "
                       "total call is allowed again with no other change",
              "Bash", {"command": "echo x"}, agent_id="agentWiden", state_dir=d,
              transcript_path=t, project_dir=proj)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)
        os.remove(t)

    # --- the PACE rule fails open, independently of the TOUCH rule, when the established
    # card's own file cannot be found on disk — the TOUCH rule still fires normally at its
    # own threshold, proving the two failure modes never interfere with each other ---
    d = fresh_dir()
    empty_proj2 = fixture_project()  # a real, empty project dir — CARD is not written here
    t = fake_transcript([{"agentId": "agentNoFile", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "establish card whose own file is not actually on disk", "Read",
              {"file_path": "/tmp/x"}, agent_id="agentNoFile", state_dir=d,
              transcript_path=t, project_dir=empty_proj2)
        for i in range(19):
            check("allow", f"ordinary call {i+2}/20 — PACE keeps failing open, no file to "
                           "read", "Bash", {"command": "echo x"}, agent_id="agentNoFile",
                  state_dir=d, transcript_path=t, project_dir=empty_proj2)
        check("deny", "21st call still refused by the TOUCH rule alone, PACE never spoke",
              "Bash", {"command": "echo x"}, agent_id="agentNoFile", state_dir=d,
              transcript_path=t, project_dir=empty_proj2, reason_contains="TOUCH rule",
              # the TOUCH message legitimately NAMES the PACE rule in passing; what must
              # NOT appear is the PACE rule's own denial actually firing
              reason_not_contains="Blocked by card-touch-gate's PACE rule")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(empty_proj2, ignore_errors=True)
        os.remove(t)

    # =====================================================================================
    # New for HRN-47 (AC7): the SEARCH-AGENT ceiling, a flat, card-independent budget for a
    # read-only agent (Explore/Plan/trace-audit), tracked in the same per-agent state file
    # under its own field, never mixed with the TOUCH or PACE rule's own fields.
    # =====================================================================================

    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentSearch1",
                           "prompt": "search the codebase for every caller of X"}])
    try:
        for i in range(28):
            check("allow", f"read-only search agent call {i+1}/28 within its own flat "
                           "ceiling", "Grep", {"pattern": "X"}, agent_id="agentSearch1",
                  state_dir=d, transcript_path=t, agent_type="Explore")
        check("deny", "29th call crosses the search agent's own flat ceiling of 28",
              "Grep", {"pattern": "X"}, agent_id="agentSearch1", state_dir=d,
              transcript_path=t, agent_type="Explore",
              reason_contains="SEARCH-AGENT rule")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- the search agent's own ceiling is completely independent of an executor's PACE/
    # TOUCH budget, even when both share the same state directory and the same transcript
    # file (the ordinary case: one executor spawning one search agent) ---
    d = fresh_dir()
    proj = fixture_project({CARD: {"ticked": 0}})
    t = fake_transcript([
        {"agentId": "agentExec", "prompt": f"Implement {CARD}"},
        {"agentId": "agentSearch2", "prompt": "search for callers of Y"},
    ])
    try:
        check("allow", "agentExec establishes its own card", "Read",
              {"file_path": "/tmp/x"}, agent_id="agentExec", state_dir=d,
              transcript_path=t, project_dir=proj)
        for i in range(28):
            check("allow", f"agentSearch2 call {i+1}/28 never touches agentExec's own "
                           "PACE/TOUCH state", "Grep", {"pattern": "Y"},
                  agent_id="agentSearch2", state_dir=d, transcript_path=t,
                  agent_type="trace-audit", project_dir=proj)
        check("deny", "agentSearch2 refused on its own 29th call, naming the "
                      "SEARCH-AGENT rule",
              "Grep", {"pattern": "Y"}, agent_id="agentSearch2", state_dir=d,
              transcript_path=t, agent_type="trace-audit", project_dir=proj,
              reason_contains="SEARCH-AGENT rule")
        check("allow", "agentExec is completely unaffected by agentSearch2 hitting its own "
                       "ceiling — still well within its own 20-call PACE relay budget",
              "Bash", {"command": "echo exec"}, agent_id="agentExec", state_dir=d,
              transcript_path=t, project_dir=proj)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)
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
