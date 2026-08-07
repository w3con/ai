#!/usr/bin/env python3
"""Test harness for hooks/plan-gate.sh (HRN-109.1).

plan-gate.sh has never had a test file since it was first built (2026-07-10, path-bound
2026-08-01). This suite pins the verdicts it gives TODAY, before HRN-109.2 moves its
brief-path-reading code into a shared helper — so that refactor can be checked against a
fixed, known-correct set of allow/deny decisions rather than trusted by inspection alone.

Every scenario runs against a scratch fixture root, never the real ai/timeline/tasks or
ai/harness/tasks directories, via PLAN_GATE_SEARCH_ROOTS — the env var the hook already
reads to override its search roots, exactly as CARD_TOUCH_GATE_STATE_DIR isolates
card-touch-gate.test.py from live state.

Run directly: python3 /Users/laptop/Dev/ai/hooks/plan-gate.test.py
Exit code 0 when every check passes, 1 when any fails (own PASS/FAIL harness, matching the
sibling *.test.py files in this directory rather than unittest).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = "/Users/laptop/Dev/ai/hooks/plan-gate.sh"

fails = 0


def call(tool_name, tool_input, roots=None, extra_env=None):
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    env = dict(os.environ)
    if roots is not None:
        env["PLAN_GATE_SEARCH_ROOTS"] = roots
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
          reason_contains=None):
    global fails
    decision, reason = call(tool_name, tool_input, roots=roots, extra_env=extra_env)
    ok = decision == expected
    if ok and reason_contains is not None:
        ok = bool(reason) and reason_contains in reason
    fails += 0 if ok else 1
    detail = "" if ok else f"  (expected {expected}, got {decision}, reason={reason!r})"
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{detail}")


def fresh_root():
    return tempfile.mkdtemp(prefix="plan-gate-test-")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


try:
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
    check("allow", "Agent tool call with name matching an allowlisted type (case-insensitive)",
          "Agent", {"name": "EXPLORE", "prompt": "no brief needed"})

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
