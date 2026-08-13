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

Run directly: python3 ~/Dev/ai/hooks/card-touch-gate.test.py [candidate-path]
With no argument this runs against the installed hook at
~/Dev/ai/hooks/card-touch-gate.sh; given one argument it runs against that file
instead, which is what bin/hook-install uses to test a candidate before installing it.
Exit code 0 when every check passes, 1 when any fails (own PASS/FAIL harness, matching the
sibling *.test.py files in this directory rather than unittest).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

_AI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.join(os.path.expanduser("~"), "Dev", "app")  # synthetic root for payload fixtures
_HOOKS = os.path.join(_AI_ROOT, "hooks")

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HOOKS, "card-touch-gate.sh")

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


def seed_coord_state(state_dir, transcript_path, count):
    """Pre-loads the COORD rule's own per-session counter to `count` by writing the same
    coord-<session>.json file the hook itself would (HRN-123 phase B), keyed on the same
    sanitized basename of transcript_path the hook computes — so a scenario can prove
    behaviour right at the measured ceiling (761) without spawning 761 real subprocess
    calls, which would make this suite impractically slow. The sanitization below is a
    literal copy of the hook's own (non-alnum characters replaced with '_'); if the
    hook's own version ever changes, this one has to change with it by hand — the same
    known duplication SEARCH_AGENT_TYPES already carries against plan-gate.sh's own
    allowlist, stated once here rather than hidden."""
    safe_session = re.sub(r'[^A-Za-z0-9_-]', '_', os.path.basename(str(transcript_path)))
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, f"coord-{safe_session}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"coord_count": count}, f)


def seed_pace_state(state_dir, agent_id, card, total_count, count=0, search_count=0,
                     path_edits=None):
    """Pre-loads an agent's own per-agent state file directly (card, count, total_count,
    search_count, path_edits) — analogous to seed_coord_state() above, for the same reason:
    HRN-123.8's starting allowance (102) widens the PACE relay/refuse budgets by enough
    that reaching them by looping real subprocess calls one at a time, the way the
    pre-HRN-123.8 scenarios below used to, would make this suite impractically slow. Since
    the hook only calls establish_card() when state["card"] is not already truthy, seeding
    "card" here directly means a scenario using this helper for its own boundary checks
    needs no transcript_path or fake_transcript() at all unless it also wants to test the
    TOUCH rule in the same breath."""
    os.makedirs(state_dir, exist_ok=True)
    safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', agent_id)
    path = os.path.join(state_dir, safe_id + ".json")
    state = {"card": card, "count": count, "total_count": total_count,
             "search_count": search_count, "path_edits": path_edits or {}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def check_all_contains(expected, label, tool_name, tool_input, contains, agent_id=None,
                        state_dir=None, transcript_path=None):
    """Like check() above, but asserts every string in `contains` appears in the reason,
    in one subprocess call rather than one call per substring — used where a scenario's
    own call count is itself part of what is being proved (HRN-148's BRAKE-rule sequence
    below), so re-checking the same decision twice would silently advance the shared
    per-path count check() already advances on every call it makes."""
    global fails
    decision, reason = call(tool_name, tool_input, agent_id=agent_id, state_dir=state_dir,
                             transcript_path=transcript_path)
    ok = decision == expected and bool(reason) and all(s in reason for s in contains)
    fails += 0 if ok else 1
    detail = "" if ok else f"  (expected {expected} with reason containing {contains!r}, got {decision}, reason={reason!r})"
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{detail}")


def check_no_reason(expected, label, tool_name, tool_input, agent_id=None, state_dir=None,
                     transcript_path=None):
    """Like check() above, but for the one assertion check()'s own reason_not_contains
    cannot make: that a call carries NO reason at all (reason is None), rather than a
    reason that merely lacks some substring — reason_not_contains requires a truthy
    reason to compare against, which is exactly what an ordinary allow decision with no
    warning attached (HRN-148) does not have."""
    global fails
    decision, reason = call(tool_name, tool_input, agent_id=agent_id, state_dir=state_dir,
                             transcript_path=transcript_path)
    ok = decision == expected and reason is None
    fails += 0 if ok else 1
    detail = "" if ok else f"  (expected {expected} with no reason, got {decision}, reason={reason!r})"
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{detail}")


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
              {"file_path": _APP + "/" + CARD}, agent_id="agentA",
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
                           "prompt": f"Implement {_APP}/{CARD}"}])
    try:
        check("allow", "card established from the brief's shared-checkout path",
              "Read", {"file_path": _APP + "/README.md"}, agent_id="agentW",
              state_dir=d, transcript_path=t)
        worktree_path = (_APP + "/.claude/worktrees/agent-agentW/" + CARD)
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
              "Read", {"file_path": _APP + "/" + OTHER_CARD},
              agent_id="agentP", state_dir=d, transcript_path=t)
        check("allow", "call 2/20: Grep across the unrelated card never establishes it",
              "Grep", {"pattern": "status", "path": _APP + "/" + OTHER_CARD},
              agent_id="agentP", state_dir=d, transcript_path=t)
        check("allow", "call 3/20: an actual Edit to the unrelated card does not steal "
                       "the tracked identity — the card was already established from the "
                       "brief on call 1 and is never replaced",
              "Edit", {"file_path": _APP + "/" + OTHER_CARD},
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
                  "Edit", {"file_path": _APP + "/" + CARD},
                  agent_id="agentPace1", state_dir=d, transcript_path=t, project_dir=proj)

        # total is now 16 (1 + 3*5); 4 more ordinary calls bring it to 17, 18, 19, 20 — all
        # still within even the OLD PACE relay budget of 20 (rate 20 x (0 ticked + 1)),
        # let alone HRN-123.8's own widened one
        for i in range(4):
            check("allow", f"post-cycles ordinary call {i+1}/4, PACE total now "
                           f"{17+i}/20, TOUCH's own count only {i+1}/20",
                  "Bash", {"command": "echo x"}, agent_id="agentPace1", state_dir=d,
                  transcript_path=t, project_dir=proj)

        # HRN-123.8: the starting allowance (102) widens this run's own relay budget from
        # 20 to 20+102=122 — jump total_count ahead via seed_pace_state() rather than
        # looping ~100 more real calls, keeping the TOUCH rule's own count (4, from the
        # loop above) exactly where the real calls left it, so the "nowhere near its own
        # threshold" claim below still holds under the new arithmetic
        seed_pace_state(d, "agentPace1", CARD, total_count=121, count=4)

        check("allow", "call 122/122 — exactly at the widened relay budget of "
                       "20*(0+1)+102=122 — still allows",
              "Bash", {"command": "echo x"}, agent_id="agentPace1", state_dir=d,
              transcript_path=t, project_dir=proj)

        # call 123 crosses the widened relay budget (122) while the TOUCH rule's own count
        # is only 6 — nowhere near ITS OWN threshold of 20 — so this denial must be the
        # PACE rule's, not the TOUCH rule's
        check("deny", "call 123 crosses the widened relay budget (122) while the TOUCH "
                      "rule's own count is only 6/20 — proof the two rules are still "
                      "independent under the new arithmetic",
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
              "Edit", {"file_path": _APP + "/" + CARD},
              agent_id="agentPace1", state_dir=d, transcript_path=t, project_dir=proj)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)
        os.remove(t)

    # --- the PACE rule's relay tier and refuse tier, and the optional per-card `rate:`
    # override (AC5), proved together against a card that overrides the default rate.
    # HRN-123.8: START_ALLOWANCE (102) is a FLAT addition, unscaled by the card's own rate,
    # so this card's own relay budget becomes 5*(0+1)+102=107 and its refuse budget becomes
    # 5*1.4*(0+1)+102=109, rather than the pre-HRN-123.8 5/7 ---
    d = fresh_dir()
    proj = fixture_project({CARD: {"ticked": 0, "rate": 5}})  # relay 5+102=107, refuse 109
    t = fake_transcript([{"agentId": "agentPace2", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "agentPace2 establishes the card under its own rate:5 (total "
                       "1/107)", "Read", {"file_path": "/tmp/x"}, agent_id="agentPace2",
              state_dir=d, transcript_path=t, project_dir=proj)

        # jump total_count ahead via seed_pace_state() rather than looping ~105 more real
        # calls to reach the widened budget
        seed_pace_state(d, "agentPace2", CARD, total_count=105)

        check("allow", "call 106/107, still within the widened relay budget "
                       "(5*(0+1)+102=107)", "Bash", {"command": "echo x"},
              agent_id="agentPace2", state_dir=d, transcript_path=t, project_dir=proj)
        check("allow", "call 107/107 — exactly at the widened relay budget — still allows",
              "Bash", {"command": "echo x"}, agent_id="agentPace2", state_dir=d,
              transcript_path=t, project_dir=proj)
        check("deny", "call 108 crosses the widened relay budget (107) — relay tier, not "
                      "refuse (widened refuse ceiling is 5*1.4*(0+1)+102=109)",
              "Bash", {"command": "echo x"}, agent_id="agentPace2", state_dir=d,
              transcript_path=t, project_dir=proj, reason_contains="PACE rule (relay")
        check("deny", "call 109 is still within the widened refuse ceiling (109) — relay "
                      "tier again, not refuse", "Bash", {"command": "echo x"},
              agent_id="agentPace2", state_dir=d, transcript_path=t, project_dir=proj,
              reason_contains="PACE rule (relay")
        check("deny", "call 110 crosses the widened refuse ceiling (109) — refuse tier",
              "Bash", {"command": "echo x"}, agent_id="agentPace2", state_dir=d,
              transcript_path=t, project_dir=proj, reason_contains="PACE rule (refuse")
        check("allow", "an Edit to the tracked card is still allowed through even at the "
                       "refuse tier", "Edit", {"file_path": _APP + "/" + CARD},
              agent_id="agentPace2", state_dir=d, transcript_path=t, project_dir=proj)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)
        os.remove(t)

    # --- ticking a checkpoint box widens the PACE budget live, on the very next call, off
    # the same card file — no restart, no reset needed. HRN-123.8: this scenario is also
    # this suite's proof that the starting allowance is spent only once per run rather than
    # once per checkpoint — the ticked=1 budget below is exactly `rate` (5) higher than the
    # ticked=0 budget, never `rate + START_ALLOWANCE` again ---
    d = fresh_dir()
    proj = fixture_project({CARD: {"ticked": 0, "rate": 5}})  # relay 5+102=107, refuse 109
    t = fake_transcript([{"agentId": "agentWiden", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "establish card (rate 5, ticked 0)", "Read", {"file_path": "/tmp/x"},
              agent_id="agentWiden", state_dir=d, transcript_path=t, project_dir=proj)

        # jump ahead to the widened ticked=0 relay budget's own boundary rather than
        # looping ~105 real calls
        seed_pace_state(d, "agentWiden", CARD, total_count=106)
        check("allow", "call 107 — exactly at the widened relay budget of "
                       "5*(0+1)+102=107 (ticked still 0) — still allows",
              "Bash", {"command": "echo x"}, agent_id="agentWiden", state_dir=d,
              transcript_path=t, project_dir=proj)
        check("deny", "call 108 crosses the widened relay budget (107) (ticked still 0)",
              "Bash", {"command": "echo x"}, agent_id="agentWiden", state_dir=d,
              transcript_path=t, project_dir=proj, reason_contains="PACE rule (relay")

        # simulate the executor ticking one checkpoint box on the real card file — the
        # relay budget is now 5*(1+1)+102=112: exactly 5 (the rate) higher than the
        # ticked=0 budget of 107, never 107+102=209 — proof the starting allowance was
        # granted once, at the run's own start, and is not re-added at this second
        # checkpoint
        write_fixture_card(proj, CARD, ticked=1, rate=5)

        check("allow", "after the box tick widens the live budget to 5*(1+1)+102=112, the "
                       "next total call (109) is allowed again with no other change",
              "Bash", {"command": "echo x"}, agent_id="agentWiden", state_dir=d,
              transcript_path=t, project_dir=proj)

        # jump ahead again, to the new ticked=1 boundary itself, to prove it sits exactly
        # at 112 and not at 112+102=214
        seed_pace_state(d, "agentWiden", CARD, total_count=111)
        check("allow", "call 112 — exactly at the ticked=1 budget of 5*(1+1)+102=112 — "
                       "still allows", "Bash", {"command": "echo x"},
              agent_id="agentWiden", state_dir=d, transcript_path=t, project_dir=proj)
        check("deny", "call 113 crosses the ticked=1 budget (112) — proof the allowance "
                      "was spent only once, not re-granted at this second checkpoint",
              "Bash", {"command": "echo x"}, agent_id="agentWiden", state_dir=d,
              transcript_path=t, project_dir=proj, reason_contains="PACE rule (relay")
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

    # =====================================================================================
    # New for HRN-123: the BRAKE rule, a fourth rule independent of TOUCH/PACE/SEARCH-AGENT,
    # refusing the Nth Edit or Write of one and the same path within a single run. Set from
    # the measured per-path edit distribution across archived executor-run transcripts only
    # (HRN-123.1: p50=3, p75=5, p90=9, p95=13, p99=26, p100=34) — N=9, the p90 point.
    # =====================================================================================

    # --- the Nth same-path edit is refused once a card IS established for this run (AC2:
    # "a run whose card is established ... is still refused the ninth edit of any other
    # file, with that refusal's wording unchanged"). HRN-139 moved the "no card at all"
    # fail-open check ahead of the BRAKE rule, so this scenario now establishes its own
    # card from a real spawn brief first — the no-card-at-all case this used to exercise by
    # omission is covered on its own terms in the HRN-139 block further below instead ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentBrake1", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "agentBrake1 establishes its own card first, so the BRAKE rule "
                       "below is exercised with a card established, not the no-card-at-"
                       "all case HRN-139 covers separately",
              "Read", {"file_path": "/tmp/x"}, agent_id="agentBrake1", state_dir=d,
              transcript_path=t)
        for i in range(8):
            check("allow", f"edit {i+1}/8 of the same unrelated path allows",
                  "Edit", {"file_path": "/tmp/repeatedly-edited.vue"},
                  agent_id="agentBrake1", state_dir=d, transcript_path=t)
        check("deny", "the 9th edit of the same path is refused by the BRAKE rule",
              "Edit", {"file_path": "/tmp/repeatedly-edited.vue"},
              agent_id="agentBrake1", state_dir=d, transcript_path=t,
              reason_contains="BRAKE rule")
        check("deny", "the refusal names the path",
              "Edit", {"file_path": "/tmp/repeatedly-edited.vue"},
              agent_id="agentBrake1", state_dir=d, transcript_path=t,
              reason_contains="/tmp/repeatedly-edited.vue")
        check("deny", "the refusal names the count and the threshold",
              "Edit", {"file_path": "/tmp/repeatedly-edited.vue"},
              agent_id="agentBrake1", state_dir=d, transcript_path=t,
              reason_contains="threshold of 9")
        check("deny", "the refusal names the alternative: rewrite in one call",
              "Edit", {"file_path": "/tmp/repeatedly-edited.vue"},
              agent_id="agentBrake1", state_dir=d, transcript_path=t,
              reason_contains="rewrite the file in a single call")
        # a different path is tracked completely separately and still allows
        check("allow", "a DIFFERENT path's own edit count is unaffected by the first "
                       "path's having crossed the brake",
              "Edit", {"file_path": "/tmp/a-different-file.vue"},
              agent_id="agentBrake1", state_dir=d, transcript_path=t)
        # Write is braked exactly the same as Edit — the rule fires on either tool
        check("allow", "Write calls against a third path start their own count at 1/9",
              "Write", {"file_path": "/tmp/a-third-file.vue", "content": "x"},
              agent_id="agentBrake1", state_dir=d, transcript_path=t)
        # the run's own tracked card stays exempt even after another path has already
        # crossed the brake — AC2's other half, proved in the same run
        check("allow", "the run's own card is still exempt from the brake even after "
                       "another path has already crossed it",
              "Edit", {"file_path": _APP + "/" + CARD},
              agent_id="agentBrake1", state_dir=d, transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- the run's own card is never braked, no matter how many times it is edited —
    # exercised with the card established from the spawn brief, exactly the way a real
    # executor's checkpoint-ticking edits happen ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentBrake2", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "agentBrake2 establishes its own card",
              "Read", {"file_path": "/tmp/x"}, agent_id="agentBrake2", state_dir=d,
              transcript_path=t)
        for i in range(15):
            check("allow", f"card edit {i+1}/15 — well past the BRAKE threshold of 9 — "
                           "still allows, because a card touch never reaches the BRAKE "
                           "rule at all",
                  "Edit", {"file_path": _APP + "/" + CARD},
                  agent_id="agentBrake2", state_dir=d, transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # --- fail open on a malformed payload reaching the BRAKE rule specifically: a
    # non-string file_path, and an Edit whose tool_input carries no file_path key at all —
    # neither crashes the hook nor is ever counted, both simply allow. Card established
    # first, same reason as agentBrake1 above: this scenario also proves the real-path
    # denial at the end, which HRN-139 makes conditional on a card being established. ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentBrake3", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "agentBrake3 establishes its own card first",
              "Read", {"file_path": "/tmp/x"}, agent_id="agentBrake3", state_dir=d,
              transcript_path=t)
        check("allow", "a non-string file_path is not trackable and falls through to "
                       "allow rather than erroring",
              "Edit", {"file_path": 12345}, agent_id="agentBrake3", state_dir=d,
              transcript_path=t)
        check("allow", "an Edit with no file_path key at all falls through to allow",
              "Edit", {}, agent_id="agentBrake3", state_dir=d, transcript_path=t)
        # neither malformed call above was ever counted against a real path, so nine
        # further ordinary edits of a real path still take the full count to deny
        for i in range(8):
            check("allow", f"edit {i+1}/8 of a real path after the malformed calls above "
                           "still allows",
                  "Edit", {"file_path": "/tmp/after-malformed.vue"},
                  agent_id="agentBrake3", state_dir=d, transcript_path=t)
        check("deny", "the 9th edit of the real path still denies normally — the "
                      "malformed calls above were never counted towards it",
              "Edit", {"file_path": "/tmp/after-malformed.vue"},
              agent_id="agentBrake3", state_dir=d, transcript_path=t,
              reason_contains="BRAKE rule")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # =====================================================================================
    # HRN-148: past BRAKE_THRESHOLD an Edit still denies exactly as before (AC2), but a
    # Write is now let through exactly once — the whole-file rewrite the Edit refusal's own
    # message already asks for — and refused on the second Write of the same path past the
    # threshold (AC1). The two kinds of call still advance one shared per-path count (AC3).
    # From the seventh call against a path onward, any call the BRAKE rule itself does not
    # refuse now carries a warning naming the path, the count and the ceiling on its own
    # "allow" decision (AC4), and that warning never turns an allow into a deny and never
    # touches any other rule's own judgment (AC5).
    # =====================================================================================
    # Exact call-by-call shape of this scenario, since the sequence's own call count is
    # part of what is being proved (each check below, whether check(), check_no_reason()
    # or check_all_contains(), is exactly one subprocess call and advances
    # path_edits[path] by one): calls 1-6 (Edit) stay below the 7-call warning point;
    # calls 7-8 (Edit) are allowed and now warn; call 9 (Write) reaches BRAKE_THRESHOLD
    # and is the one exempted rewrite; calls 10-11 (Write) are refused, the exemption
    # already used; call 12 (Edit) is refused on the unchanged Edit message; the final
    # Bash call touches neither Edit nor Write and carries no reason of its own.
    d = fresh_dir()
    t = fake_transcript([{"agentId": "agentBrakeWrite1", "prompt": f"Implement {CARD}"}])
    path = "/tmp/hrn148-mixed.vue"
    try:
        check("allow", "agentBrakeWrite1 establishes its own card first",
              "Read", {"file_path": "/tmp/x"}, agent_id="agentBrakeWrite1", state_dir=d,
              transcript_path=t)

        for i in range(6):
            check_no_reason("allow", f"edit {i+1}/6 of the path — below the 7th-call "
                            "warning point — carries no reason at all",
                            "Edit", {"file_path": path}, agent_id="agentBrakeWrite1",
                            state_dir=d, transcript_path=t)

        # AC4: calls 7 and 8 (still Edit, still below the threshold of 9) are allowed and
        # now carry a warning naming the path, the count and the ceiling
        check_all_contains("allow", "call 7 (an Edit) is allowed and now warns, naming "
                           "the path, the count and the ceiling",
                           "Edit", {"file_path": path},
                           ["BRAKE rule", "7 times", "ceiling of 9", path],
                           agent_id="agentBrakeWrite1", state_dir=d, transcript_path=t)
        check_all_contains("allow", "call 8 (an Edit) is allowed and still warns, one "
                           "call below the threshold",
                           "Edit", {"file_path": path}, ["8 times", "ceiling of 9"],
                           agent_id="agentBrakeWrite1", state_dir=d, transcript_path=t)

        # AC1 (first half) + AC4: call 9 — a Write — reaches the threshold and is exactly
        # the one consolidating rewrite the Edit refusal's own message already asks for:
        # allowed, not refused, and it too carries the warning
        check_all_contains("allow", "call 9 (a Write) reaches the threshold and is the "
                           "one consolidating rewrite BRAKE_TEMPLATE's own Edit message "
                           "already asks for — allowed, not refused",
                           "Write", {"file_path": path, "content": "whole file"},
                           ["9 times", "ceiling of 9"],
                           agent_id="agentBrakeWrite1", state_dir=d, transcript_path=t)

        # AC1 (second half): call 10, a further Write of the same path, now that the one
        # allowed rewrite has already been used, is refused — the refusal tells the run
        # to record where it stopped and stop, rather than reach for yet another rewrite
        check_all_contains("deny", "call 10 (a second Write of the same path) is refused "
                           "— the one allowed rewrite was already used",
                           "Write", {"file_path": path, "content": "whole file again"},
                           ["BRAKE rule", "call number 10"],
                           agent_id="agentBrakeWrite1", state_dir=d, transcript_path=t)
        check_all_contains("deny", "call 11's refusal tells the run to record where it "
                           "stopped and stop, rather than reach for yet another rewrite",
                           "Write", {"file_path": path, "content": "x"},
                           ["Record where this run has stopped"],
                           agent_id="agentBrakeWrite1", state_dir=d, transcript_path=t)

        # AC2 + AC3: call 12, an Edit of the same path, after the Write exemption has
        # already been used, keeps denying on the exact same message as before this card
        # — proving the Edit rule is untouched by HRN-148, and that the count behind it
        # is the honest combined total of every Edit and Write this run has made against
        # this one path (11 calls above plus this one is 12, matched in the message)
        check_all_contains("deny", "call 12 (an Edit), after the Write exemption is "
                           "used, is still refused with the unchanged Edit message",
                           "Edit", {"file_path": path},
                           ["rewrite the file in a single call", "12"],
                           agent_id="agentBrakeWrite1", state_dir=d, transcript_path=t)

        # AC5: an entirely unrelated call (not Edit/Write, so the BRAKE rule is never even
        # reached for it) right after the sequence above carries no reason of its own —
        # the warning never leaks into a call it has nothing to do with
        check_no_reason("allow", "an unrelated Bash call right after the sequence above "
                        "carries no reason at all",
                        "Bash", {"command": "echo unrelated"}, agent_id="agentBrakeWrite1",
                        state_dir=d, transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # =====================================================================================
    # HRN-139: the BRAKE rule must never fire at all for a run whose card could never be
    # established — the reported defect (this card's own origin field): an unidentified
    # run (no recoverable brief, e.g. because the spawning coordinator session was cleared
    # mid-run — see HRN-134) edited its own task card ten times and was refused by the
    # BRAKE rule, despite the rule's own stated exemption for a run's own card, which never
    # took effect because the run was never recognised as having a card at all. AC1: "A run
    # whose card cannot be established edits one and the same file twenty times and is
    # refused none of them." AC3: this is the test that reproduces the defect before the
    # repair — it fails (asserts allow, gets deny) against the unrepaired candidate and
    # passes once HRN-139.4 moves the no-card fail-open check ahead of the BRAKE rule.
    # =====================================================================================

    # --- no transcript_path at all, the plainest "brief cannot be recovered" shape ---
    d = fresh_dir()
    try:
        for i in range(19):
            check("allow", f"edit {i+1}/19 of the same path, no recoverable brief at all "
                           "(no transcript_path given), still allows",
                  "Edit", {"file_path": "/tmp/hrn139-repeatedly-edited.vue"},
                  agent_id="agentHRN139", state_dir=d)
        check("allow", "the 20th edit of the same path is still allowed — a run whose "
                       "card could never be established is never braked at all, exactly "
                       "as the touch and pace rules already fail open for it",
              "Edit", {"file_path": "/tmp/hrn139-repeatedly-edited.vue"},
              agent_id="agentHRN139", state_dir=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- the same defect, reproduced against a transcript that DOES exist but never names
    # this agent_id — the concrete shape HRN-139's own Working state found for the affected
    # run (its per-agent state file's own "card" field was null even though a transcript
    # file existed, because the record it needed lived in a different coordinator session
    # — see HRN-134) ---
    d = fresh_dir()
    t = fake_transcript([{"agentId": "some-other-agent", "prompt": f"Implement {CARD}"}])
    try:
        for i in range(9):
            check("allow", f"edit {i+1}/9 of the same path, transcript exists but holds "
                           "no spawn record for THIS agent_id, still allows",
                  "Edit", {"file_path": "/tmp/hrn139-other-transcript.vue"},
                  agent_id="agentHRN139b", state_dir=d, transcript_path=t)
        check("allow", "the 10th edit is still allowed, for the same reason",
              "Edit", {"file_path": "/tmp/hrn139-other-transcript.vue"},
              agent_id="agentHRN139b", state_dir=d, transcript_path=t)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t)

    # =====================================================================================
    # HRN-123 phase B: the COORD rule — the coordinator's own per-session ceiling.
    # coord_count is seeded directly via seed_coord_state() rather than reached by looping
    # 761 real subprocess calls (see that helper's own docstring for why); every scenario
    # below still exercises the hook's real decision path for the one or two calls each
    # one actually needs to prove.
    # =====================================================================================

    # --- a coordinator call past the ceiling is refused, naming the COORD rule and the
    # ceiling; the call that crosses it is the one right after the seeded count, proving
    # the arithmetic (760 seeded + 1 this call = 761, not yet over; +1 more = 762, over) ---
    d = fresh_dir()
    t1 = "/fake/session/coord-session-one.jsonl"
    try:
        seed_coord_state(d, t1, 760)
        check("allow", "coordinator call 761/761 — right at the ceiling — still allows",
              "Bash", {"command": "echo hi"}, agent_id=None, state_dir=d, transcript_path=t1)
        check("deny", "coordinator call 762 crosses the ceiling of 761 and is refused",
              "Bash", {"command": "echo hi"}, agent_id=None, state_dir=d, transcript_path=t1,
              reason_contains="COORD rule")
        check("deny", "the refusal names bin/session-start as the way out",
              "Bash", {"command": "echo hi"}, agent_id=None, state_dir=d, transcript_path=t1,
              reason_contains="bin/session-start")

        # --- an exempted landing call is allowed even past the ceiling: version control,
        # an Edit/Write under ai/ or kb/, and the bin/session-start call itself ---
        check("allow", "a git command is exempt and still allowed past the ceiling",
              "Bash", {"command": "git status"}, agent_id=None, state_dir=d, transcript_path=t1)
        check("allow", "a git command with a leading path is still recognised as git",
              "Bash", {"command": "/usr/bin/git commit -m x"}, agent_id=None, state_dir=d,
              transcript_path=t1)
        check("allow", "an Edit under ai/ is exempt and still allowed past the ceiling",
              "Edit", {"file_path": _APP + "/ai/harness/tasks/ZZZ-3.md"},
              agent_id=None, state_dir=d, transcript_path=t1)
        check("allow", "a Write under kb/ is exempt and still allowed past the ceiling",
              "Write", {"file_path": _APP + "/kb/observability/overview.md"},
              agent_id=None, state_dir=d, transcript_path=t1)
        check("allow", "a bin/session-start call is exempt and still allowed past the ceiling",
              "Bash", {"command": "bin/session-start"}, agent_id=None, state_dir=d,
              transcript_path=t1)

        # --- exempted calls are never counted: an ordinary call right after them still
        # denies on exactly the same terms, proving they never advanced or reset coord_count ---
        check("deny", "an ordinary call right after the exempt ones above still denies — "
                      "the exempt calls were never counted",
              "Bash", {"command": "echo still-over"}, agent_id=None, state_dir=d,
              transcript_path=t1, reason_contains="COORD rule")

        # --- CLAUDE_GATE_BYPASS overrides the COORD refusal, exactly as it already does
        # for the TOUCH and PACE rules ---
        check("allow", "CLAUDE_GATE_BYPASS=1 overrides the COORD refusal",
              "Bash", {"command": "echo hi"}, agent_id=None, state_dir=d, transcript_path=t1,
              extra_env={"CLAUDE_GATE_BYPASS": "1"})
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- per-session isolation: a second, unrelated coordinator session (a different
    # transcript_path) starts its own count from zero and is completely unaffected by the
    # first session having already crossed its own ceiling ---
    d = fresh_dir()
    t1 = "/fake/session/coord-session-two-a.jsonl"
    t2 = "/fake/session/coord-session-two-b.jsonl"
    try:
        seed_coord_state(d, t1, 900)  # session A is already deep past its own ceiling
        check("deny", "session A, already past its own ceiling, is refused",
              "Bash", {"command": "echo hi"}, agent_id=None, state_dir=d, transcript_path=t1,
              reason_contains="COORD rule")
        for i in range(10):
            check("allow", f"session B, an entirely different session, call {i+1}/10 — "
                           "its own count starts fresh, unaffected by session A",
                  "Bash", {"command": "echo hi"}, agent_id=None, state_dir=d,
                  transcript_path=t2)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- fail open when no transcript_path is present at all: no session identifier to
    # key a ceiling against, so every call allows, uncounted — this is the pre-existing
    # "coordinator call N/30 is never gated" loop's own condition, restated here once more
    # explicitly against the COORD rule by name, at a count well past COORD_CEILING ---
    d = fresh_dir()
    try:
        for i in range(40):
            check("allow", f"coordinator call {i+1}/40 with no transcript_path at all "
                           "is never gated by the COORD rule",
                  "Bash", {"command": "echo hi"}, agent_id=None, state_dir=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- an executor's own call is never affected by the COORD rule or by any coordinator
    # session's own state, even when it shares the very same state_dir and the very same
    # transcript_path a coordinator session used above ---
    d = fresh_dir()
    t_shared = "/fake/session/coord-session-three.jsonl"
    t_exec = fake_transcript([{"agentId": "agentCoord1", "prompt": f"Implement {CARD}"}])
    try:
        seed_coord_state(d, t_shared, 900)  # this "session" is already deep past COORD_CEILING
        check("allow", "an executor call using the SAME transcript_path a refused "
                       "coordinator session used is still allowed — it carries an "
                       "agent_id, so it never reaches the COORD rule at all",
              "Read", {"file_path": "/tmp/x"}, agent_id="agentCoord1", state_dir=d,
              transcript_path=t_exec)
        for i in range(15):
            check("allow", f"executor agentCoord1 ordinary call {i+2}/20 — well within its "
                           "own TOUCH/PACE budget, completely unaffected by the "
                           "coordinator's own COORD ceiling",
                  "Bash", {"command": "echo hi"}, agent_id="agentCoord1", state_dir=d,
                  transcript_path=t_exec)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        os.remove(t_exec)

    # =====================================================================================
    # HRN-123.8: the starting allowance — a fixed number of calls (measured at 102,
    # HRN-123.7) granted once per run and added, unscaled, to both the relay and the refuse
    # budget, so a run's very first checkpoint is not held to the archive's own median
    # per-checkpoint rate while it is still paying the one-time cost of arriving. The
    # rewritten agentPace1/agentPace2/agentWiden scenarios above already prove the exact
    # new boundary numbers, including that the allowance is spent only once (agentWiden);
    # this block adds the direct old-arithmetic-vs-new-arithmetic comparison at one fixed
    # call count that the card's own acceptance criterion asks for by name.
    # =====================================================================================
    d = fresh_dir()
    proj = fixture_project({CARD: {"ticked": 0}})  # default rate 20: old budget 20, new 122
    t = fake_transcript([{"agentId": "agentAllowance", "prompt": f"Implement {CARD}"}])
    try:
        check("allow", "agentAllowance establishes the card (rate 20, ticked 0)", "Read",
              {"file_path": "/tmp/x"}, agent_id="agentAllowance", state_dir=d,
              transcript_path=t, project_dir=proj)

        # jump total_count to 20 directly rather than looping 19 more real calls — this
        # scenario is about the PACE rule's own arithmetic, not the TOUCH rule, and the
        # TOUCH rule's own count is reset to 0 here for exactly that reason: at 20 real
        # non-touching calls the TOUCH rule (its own, unrelated 20-call threshold) would
        # otherwise deny this same 21st call first, for a completely different reason
        seed_pace_state(d, "agentAllowance", CARD, total_count=20, count=0)

        check("allow", "call 21 — exactly the call count the OLD arithmetic "
                       "(rate*(ticked+1)=20, no starting allowance) would have refused, "
                       "as the pre-HRN-123.8 version of this same scenario used to assert "
                       "— is allowed under the NEW arithmetic (20+102=122) at this same "
                       "call count", "Bash", {"command": "echo x"},
              agent_id="agentAllowance", state_dir=d, transcript_path=t, project_dir=proj)
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
