#!/usr/bin/env python3
"""Test harness for the HRN-203 candidate of hooks/plan-gate.sh (extends the HRN-109.1 suite
this file is copied from, adding coverage for the new second-task rule HRN-203 adds to the
same hook — see that file's own header, in this same candidates/ directory, for what the
marker check does and what the new rule adds alongside it).

The suite this file was copied from proved only the marker check: given a brief, does it
carry an accepted pass marker. Every one of those original scenarios is reproduced below
unchanged in substance, still passing against the candidate, because HRN-203 must never
change what the marker check itself decides — it can only turn an allow the marker check
already made into a deny, on its own separate grounds. New scenarios below key the new
rule's own per-conversation state on `transcript_path`, isolated from any live session's own
state through `$PLAN_GATE_STATE_DIR`, exactly as CARD_TOUCH_GATE_STATE_DIR isolates
card-touch-gate.test.py from live state and PLAN_GATE_SEARCH_ROOTS already isolates this
suite's own marker-check scenarios from the real ai/timeline/tasks and ai/harness/tasks
directories.

Run directly: python3 ~/Dev/ai/candidates/plan-gate.test.py [candidate-path]
With no argument this runs against the candidate at ~/Dev/ai/candidates/plan-gate.sh; given
one argument it runs against that file instead, which is what bin/hook-install uses to test a
candidate before installing it.
Exit code 0 when every check passes, 1 when any fails (own PASS/FAIL harness, matching the
sibling *.test.py files in hooks/ rather than unittest).
"""
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

_AI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CANDIDATES = os.path.join(_AI_ROOT, "candidates")

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_CANDIDATES, "plan-gate.sh")

fails = 0
_session_counter = (str(i) for i in itertools.count(1))


def call(tool_name, tool_input, roots=None, extra_env=None, transcript_path=None,
         state_dir=None):
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    env = dict(os.environ)
    if roots is not None:
        env["PLAN_GATE_SEARCH_ROOTS"] = roots
    if state_dir is not None:
        env["PLAN_GATE_STATE_DIR"] = state_dir
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(["bash", HOOK], input=json.dumps(payload),
                        capture_output=True, text=True, env=env)
    try:
        out = json.loads(r.stdout)["hookSpecificOutput"]
        return out["permissionDecision"], out.get("permissionDecisionReason")
    except Exception:
        return "PARSE_FAIL(" + r.stdout[:200] + ")", None


def check(expected, label, tool_name, tool_input, roots=None, extra_env=None,
          reason_contains=None, transcript_path=None, state_dir=None):
    global fails
    decision, reason = call(tool_name, tool_input, roots=roots, extra_env=extra_env,
                             transcript_path=transcript_path, state_dir=state_dir)
    ok = decision == expected
    if ok and reason_contains is not None:
        ok = bool(reason) and reason_contains in reason
    fails += 0 if ok else 1
    detail = "" if ok else f"  (expected {expected}, got {decision}, reason={reason!r})"
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{detail}")


def check_all_contains(expected, label, tool_name, tool_input, contains, roots=None,
                        transcript_path=None, state_dir=None):
    """Like check() above, but asserts every string in `contains` appears in the reason —
    used where a scenario wants to name both cards and both ways out in one assertion rather
    than one call per substring."""
    global fails
    decision, reason = call(tool_name, tool_input, roots=roots, transcript_path=transcript_path,
                             state_dir=state_dir)
    ok = decision == expected and bool(reason) and all(s in reason for s in contains)
    fails += 0 if ok else 1
    detail = ("" if ok else
              f"  (expected {expected} with reason containing {contains!r}, got {decision}, "
              f"reason={reason!r})")
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{detail}")


def fresh_root():
    return tempfile.mkdtemp(prefix="plan-gate-test-")


def fresh_state_dir():
    return tempfile.mkdtemp(prefix="plan-gate-test-state-")


def fresh_transcript_path(state_dir):
    """A transcript_path token unique to this scratch scenario — the hook never opens this
    file, it only sanitizes its basename to key state on, exactly as
    hooks/card-touch-gate.sh's own COORD rule does with a coordinator's real durable session
    transcript path. Rooting it inside state_dir keeps every scratch artefact this suite
    creates under the one directory a `finally` block cleans up."""
    return os.path.join(state_dir, "session-" + next(_session_counter) + ".jsonl")


def session_state_file(state_dir, transcript_path):
    """The exact path the hook itself would write this conversation's state to — a literal
    copy of the hook's own sanitization (non-alnum characters replaced with '_'), the same
    known, stated duplication hooks/card-touch-gate.test.py's own seed_coord_state() already
    carries against the hook it tests."""
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', os.path.basename(str(transcript_path)))
    return os.path.join(state_dir, safe + ".json")


def assert_no_state_file(state_dir, transcript_path, label):
    global fails
    path = session_state_file(state_dir, transcript_path)
    ok = not os.path.isfile(path)
    fails += 0 if ok else 1
    print(f"  {'PASS' if ok else 'FAIL'}  {label}"
          f"{'' if ok else f'  (unexpected state file at {path})'}")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


try:
    # =========================================================================================
    # Carried over from the pre-HRN-203 suite, unchanged in substance: none of these calls
    # carries a transcript_path, so the new rule's own _session_state_path() returns None
    # (no session identifier to key state on) and every verdict is exactly the marker check's
    # own, on its own original terms.
    # =========================================================================================

    # --- only Task/Agent spawns are gated; everything else is free, regardless of content ---
    check("allow", "a Bash call is never gated, even mentioning a bare .md token",
          "Bash", {"command": "cat some/plan.md"})
    check("allow", "an Edit call is never gated",
          "Edit", {"file_path": "/tmp/whatever.md"})

    # --- allowlisted read-only agent types need no brief at all ---
    check("allow", "Task with subagent_type Explore needs no brief",
          "Task", {"subagent_type": "Explore", "prompt": "look around, no .md anywhere"})
    check("allow", "Task with subagent_type Plan needs no brief",
          "Task", {"subagent_type": "Plan", "prompt": "plan something"})
    check("allow", "Task with subagent_type trace-audit needs no brief",
          "Task", {"subagent_type": "trace-audit", "prompt": "audit a trace"})
    check("allow", "Task with subagent_type card-critic needs no brief (HRN-94)",
          "Task", {"subagent_type": "card-critic", "prompt": "review HRN-1 alone"})
    check("allow", "Agent tool call with name matching an allowlisted type (case-insensitive)",
          "Agent", {"name": "EXPLORE", "prompt": "no brief needed"})
    check("allow", "Agent tool call with name card-critic (case-insensitive, HRN-94)",
          "Agent", {"name": "Card-Critic", "prompt": "no brief needed"})

    # --- a build agent whose prompt names no .md token at all is refused outright ---
    check("deny", "no .md token anywhere in the prompt",
          "Task", {"subagent_type": "general-purpose", "prompt": "just build the thing, no path"},
          reason_contains="names no brief")

    # --- a build agent whose prompt names a .md token that resolves to nothing on disk ---
    d = fresh_root()
    try:
        check("deny", "the named .md token does not exist anywhere under the search roots",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": "implement ai/harness/tasks/NOPE-1_missing.md"},
              roots=d, reason_contains="names no brief")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- the named .md file exists but carries no pass marker ---
    d = fresh_root()
    try:
        card = os.path.join(d, "ai/harness/tasks/ZZZ-1_unsigned.md")
        write(card, "# Some card\n\nno marker line here.\n")
        check("deny", "the named file exists but has no pass marker",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": f"implement {card}"},
              roots=d, reason_contains="no pass marker")
        check("deny", "the denial names the examined file",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": f"implement {card}"},
              roots=d, reason_contains=card)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- the named .md file exists and carries the card:ready marker ---
    d = fresh_root()
    try:
        card = os.path.join(d, "ai/harness/tasks/ZZZ-2_signed.md")
        write(card, "# Some card\n\nbody text.\n\n<!-- card:ready -->\n")
        check("allow", "the named file exists and carries <!-- card:ready -->",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": f"implement {card}"},
              roots=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- the legacy scope:pass marker on a plan file still works ---
    d = fresh_root()
    try:
        plan = os.path.join(d, "ai/plans/plan_legacy.md")
        write(plan, "# Legacy plan\n\n<!-- scope:pass -->\n")
        check("allow", "a legacy plan carrying <!-- scope:pass --> still allows",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": f"implement {plan}"},
              roots=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- a bare filename resolves via the BRIEF_DIRS convention ---
    d = fresh_root()
    try:
        card = os.path.join(d, "ai/harness/tasks/ZZZ-3_bare.md")
        write(card, "# Bare-name card\n\n<!-- card:ready -->\n")
        check("allow", "a bare filename (no directory) resolves under ai/harness/tasks",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": "implement ZZZ-3_bare.md"},
              roots=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- the description field is checked, not only the prompt ---
    d = fresh_root()
    try:
        card = os.path.join(d, "ai/harness/tasks/ZZZ-4_via-description.md")
        write(card, "# Card\n\n<!-- card:ready -->\n")
        check("allow", "a brief named only in description (not prompt) still allows",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": "no path mentioned here",
                        "description": f"implement {card}"},
              roots=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- multiple candidates named: an unsigned one first, a signed one second ---
    d = fresh_root()
    try:
        unsigned = os.path.join(d, "ai/harness/tasks/ZZZ-5a_unsigned.md")
        signed = os.path.join(d, "ai/harness/tasks/ZZZ-5b_signed.md")
        write(unsigned, "# Unsigned\n\nno marker.\n")
        write(signed, "# Signed\n\n<!-- card:ready -->\n")
        check("allow", "an unsigned candidate first, a signed one later in the same prompt, still allows",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": f"see {unsigned} then really implement {signed}"},
              roots=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # --- an absolute path works regardless of the search roots ---
    d = fresh_root()
    other = fresh_root()
    try:
        card = os.path.join(other, "somewhere-else/ZZZ-6_absolute.md")
        write(card, "# Absolute\n\n<!-- card:ready -->\n")
        check("allow", "an absolute path is found even outside every search root",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": f"implement {card}"},
              roots=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(other, ignore_errors=True)

    # --- CLAUDE_GATE_BYPASS=1 always allows ---
    check("allow", "CLAUDE_GATE_BYPASS=1 allows a build agent with no brief at all",
          "Task", {"subagent_type": "general-purpose", "prompt": "no brief"},
          extra_env={"CLAUDE_GATE_BYPASS": "1"})

    # =========================================================================================
    # HRN-203: the second-task rule — one conversation runs one task.
    # =========================================================================================

    # --- a payload carrying no conversation file gives exactly today's verdict (AC6) ---
    d = fresh_root()
    ss = fresh_state_dir()
    try:
        card = os.path.join(d, "ai/harness/tasks/ZZZ-10_no-transcript.md")
        other = os.path.join(d, "ai/harness/tasks/ZZZ-11_other.md")
        write(card, "# Card\n\n<!-- card:ready -->\n")
        write(other, "# Other\n\n<!-- card:ready -->\n")
        check("allow", "no transcript_path at all: the marker-signed card still allows",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {card}"},
              roots=d, state_dir=ss)
        check("allow", "a second spawn on a DIFFERENT card, still with no transcript_path, "
                       "also allows — there is no session to key a second-task refusal on",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {other}"},
              roots=d, state_dir=ss)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss, ignore_errors=True)

    # --- first spawn in a conversation is remembered; a repeat on the same card always
    # allows, including once written with a different (executor worktree) prefix (AC1, AC3)
    # ---
    d = fresh_root()
    ss = fresh_state_dir()
    t = fresh_transcript_path(ss)
    try:
        card = os.path.join(d, "ai/harness/tasks/ZZZ-20_owned.md")
        write(card, "# Owned card\n\n<!-- card:ready -->\n")
        check("allow", "first spawn in this conversation, naming a signed card, allows",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {card}"},
              roots=d, transcript_path=t, state_dir=ss)
        for i in range(5):
            check("allow", f"repeat spawn {i+1}/5 on the SAME card in the same conversation "
                            "still allows, without limit",
                  "Task", {"subagent_type": "general-purpose", "prompt": f"implement {card}"},
                  roots=d, transcript_path=t, state_dir=ss)
        worktree_card = os.path.join(
            d, ".claude/worktrees/agent-x/ai/harness/tasks/ZZZ-20_owned.md")
        write(worktree_card, "# Owned card, worktree copy\n\n<!-- card:ready -->\n")
        check("allow", "a repeat spawn naming the SAME card via an executor's own worktree "
                       "path still allows — the canonical suffix is what is compared",
              "Task", {"subagent_type": "general-purpose",
                        "prompt": f"implement {worktree_card}"},
              roots=d, transcript_path=t, state_dir=ss)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss, ignore_errors=True)

    # --- a later spawn in the same conversation naming a DIFFERENT card is refused, and the
    # refusal names both cards, /clear, /parallel and the bypass variable (AC1, AC2) ---
    d = fresh_root()
    ss = fresh_state_dir()
    t = fresh_transcript_path(ss)
    try:
        first = os.path.join(d, "ai/harness/tasks/ZZZ-30_first.md")
        second = os.path.join(d, "ai/harness/tasks/ZZZ-31_second.md")
        write(first, "# First\n\n<!-- card:ready -->\n")
        write(second, "# Second\n\n<!-- card:ready -->\n")
        check("allow", "first spawn on the first card allows and is remembered",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {first}"},
              roots=d, transcript_path=t, state_dir=ss)
        check_all_contains(
            "deny",
            "a spawn naming a DIFFERENT, also-signed card in the same conversation is "
            "refused, naming both cards, /clear, /parallel and the bypass variable",
            "Task", {"subagent_type": "general-purpose", "prompt": f"implement {second}"},
            contains=["ai/harness/tasks/ZZZ-30_first.md", "ai/harness/tasks/ZZZ-31_second.md",
                      "/clear", "/parallel", "CLAUDE_GATE_BYPASS=1"],
            roots=d, transcript_path=t, state_dir=ss)
        check("allow", "after the refusal, a further spawn on the ORIGINAL card still allows",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {first}"},
              roots=d, transcript_path=t, state_dir=ss)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss, ignore_errors=True)

    # --- two different conversations never interfere with each other ---
    d = fresh_root()
    ss = fresh_state_dir()
    t1 = fresh_transcript_path(ss)
    t2 = fresh_transcript_path(ss)
    try:
        cardA = os.path.join(d, "ai/harness/tasks/ZZZ-40_a.md")
        cardB = os.path.join(d, "ai/harness/tasks/ZZZ-41_b.md")
        write(cardA, "# A\n\n<!-- card:ready -->\n")
        write(cardB, "# B\n\n<!-- card:ready -->\n")
        check("allow", "conversation 1 starts on card A",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {cardA}"},
              roots=d, transcript_path=t1, state_dir=ss)
        check("allow", "conversation 2 starts on card B — a different conversation, so this "
                       "is that conversation's own first spawn, not a second task",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {cardB}"},
              roots=d, transcript_path=t2, state_dir=ss)
        check("deny", "conversation 1 attempting card B is still refused",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {cardB}"},
              roots=d, transcript_path=t1, state_dir=ss)
        check("deny", "conversation 2 attempting card A is still refused",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {cardA}"},
              roots=d, transcript_path=t2, state_dir=ss)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss, ignore_errors=True)

    # --- the five situations that must keep today's verdict and record nothing (AC5) ---

    # 1. a legacy plan file brief: never card-shaped, so canonical_card() returns it
    #    unchanged and it is never tracked at all, even across two "different" legacy plans
    d = fresh_root()
    ss = fresh_state_dir()
    t = fresh_transcript_path(ss)
    try:
        plan1 = os.path.join(d, "ai/plans/plan_one.md")
        plan2 = os.path.join(d, "ai/plans/plan_two.md")
        write(plan1, "# Plan one\n\n<!-- scope:pass -->\n")
        write(plan2, "# Plan two\n\n<!-- scope:pass -->\n")
        check("allow", "a legacy plan-file brief allows, exactly as today",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {plan1}"},
              roots=d, transcript_path=t, state_dir=ss)
        check("allow", "a second, DIFFERENT legacy plan-file brief in the same conversation "
                       "still allows — a legacy plan is never card-shaped, so it is never "
                       "remembered and can never trigger a second-task refusal",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {plan2}"},
              roots=d, transcript_path=t, state_dir=ss)
        assert_no_state_file(ss, t, "a conversation that only ever named legacy plan files "
                                     "has no per-conversation state file at all")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss, ignore_errors=True)

    # 2. an allowlisted read-only agent type: exits before the new rule is ever reached
    d = fresh_root()
    ss = fresh_state_dir()
    t = fresh_transcript_path(ss)
    try:
        check("allow", "a read-only agent type allows with a conversation file present, "
                       "exactly as today",
              "Task", {"subagent_type": "Explore", "prompt": "look around"},
              roots=d, transcript_path=t, state_dir=ss)
        assert_no_state_file(ss, t, "a read-only agent spawn records nothing for this "
                                     "conversation")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss, ignore_errors=True)

    # 3. a brief carrying no marker: denied before the new rule is ever reached
    d = fresh_root()
    ss = fresh_state_dir()
    t = fresh_transcript_path(ss)
    try:
        card = os.path.join(d, "ai/harness/tasks/ZZZ-50_unsigned.md")
        write(card, "# Unsigned\n\nno marker.\n")
        check("deny", "an unsigned brief still denies with a conversation file present, "
                      "exactly as today",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {card}"},
              roots=d, transcript_path=t, state_dir=ss, reason_contains="no pass marker")
        assert_no_state_file(ss, t, "an unsigned-brief denial records nothing for this "
                                     "conversation")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss, ignore_errors=True)

    # 4. no brief named at all: denied before the new rule is ever reached
    d = fresh_root()
    ss = fresh_state_dir()
    t = fresh_transcript_path(ss)
    try:
        check("deny", "no brief named at all still denies with a conversation file present, "
                      "exactly as today",
              "Task", {"subagent_type": "general-purpose", "prompt": "just build it"},
              roots=d, transcript_path=t, state_dir=ss, reason_contains="names no brief")
        assert_no_state_file(ss, t, "a no-brief-named denial records nothing for this "
                                     "conversation")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss, ignore_errors=True)

    # 5. CLAUDE_GATE_BYPASS=1: both spawns allowed, nothing recorded for the conversation
    #    (AC4) — the bypass returns before the new rule's own code is ever reached
    d = fresh_root()
    ss = fresh_state_dir()
    t = fresh_transcript_path(ss)
    try:
        cardA = os.path.join(d, "ai/harness/tasks/ZZZ-60_a.md")
        cardB = os.path.join(d, "ai/harness/tasks/ZZZ-61_b.md")
        write(cardA, "# A\n\n<!-- card:ready -->\n")
        write(cardB, "# B\n\n<!-- card:ready -->\n")
        check("allow", "with the bypass set, a spawn on card A allows",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {cardA}"},
              roots=d, transcript_path=t, state_dir=ss,
              extra_env={"CLAUDE_GATE_BYPASS": "1"})
        check("allow", "with the bypass still set, a spawn on a DIFFERENT card B in the "
                       "same conversation also allows",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {cardB}"},
              roots=d, transcript_path=t, state_dir=ss,
              extra_env={"CLAUDE_GATE_BYPASS": "1"})
        assert_no_state_file(ss, t, "neither bypassed spawn recorded anything for this "
                                     "conversation")
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss, ignore_errors=True)

    # 6. any internal error of the new rule's own body falls through to an allowance, and
    #    records nothing — simulated by pointing PLAN_GATE_STATE_DIR at a path that cannot be
    #    used as a directory (an ordinary file sitting where the state dir would go), so
    #    os.makedirs() inside _session_state_path() raises
    d = fresh_root()
    ss_parent = fresh_state_dir()
    blocked = os.path.join(ss_parent, "blocked-state-dir")
    write(blocked, "not a directory")
    t = fresh_transcript_path(ss_parent)
    try:
        cardA = os.path.join(d, "ai/harness/tasks/ZZZ-70_a.md")
        cardB = os.path.join(d, "ai/harness/tasks/ZZZ-71_b.md")
        write(cardA, "# A\n\n<!-- card:ready -->\n")
        write(cardB, "# B\n\n<!-- card:ready -->\n")
        check("allow", "an internal error establishing the state directory falls through to "
                       "an allowance rather than denying (the marker check already decided "
                       "to allow)",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {cardA}"},
              roots=d, transcript_path=t, state_dir=blocked)
        check("allow", "with the same broken state directory, a second, different card "
                       "still allows too — nothing was ever recorded to compare against",
              "Task", {"subagent_type": "general-purpose", "prompt": f"implement {cardB}"},
              roots=d, transcript_path=t, state_dir=blocked)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(ss_parent, ignore_errors=True)

finally:
    pass

# --- fail CLOSED on empty stdin (deliberately the opposite of card-touch-gate.sh — see
# plan-gate.sh's own header comment: this gate protects one narrow action, so failing
# closed denies one spawn rather than freezing every tool call on the machine) ---
r = subprocess.run(["bash", HOOK], input="", capture_output=True, text=True)
ok = '"deny"' in r.stdout and "failing closed" in r.stdout
fails += 0 if ok else 1
print(f"  {'PASS' if ok else 'FAIL'}  empty stdin -> deny, failing closed")

r = subprocess.run(["bash", HOOK], input="{not json", capture_output=True, text=True)
ok = '"deny"' in r.stdout and "failing closed" in r.stdout
fails += 0 if ok else 1
print(f"  {'PASS' if ok else 'FAIL'}  malformed JSON -> deny, failing closed")

print(f"\n  total passed, failures: {fails}")
sys.exit(1 if fails else 0)
