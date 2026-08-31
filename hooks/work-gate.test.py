#!/usr/bin/env python3
"""Synthetic check of work-gate.sh's PHASE BOUNDARY rule (rule 5), against a throwaway
state directory and a throwaway work root — nothing real is touched.

Each case: a payload as the hook receives it, and the decision expected of it.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work-gate.sh")
AGENT = "agent-testboundary"
CARD = "TST-1"
PHASE = "TST-1.A"


def build_tree(base):
    work_root = os.path.join(base, "ai")
    card_dir = os.path.join(work_root, "harness", "epic", CARD + "_probe")
    os.makedirs(card_dir)
    with open(os.path.join(card_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write("## Шаги\n\n### %s — фаза\n\n- [%s.1] один шаг\n\n## Критерии приёмки\n"
                % (PHASE, PHASE))
    with open(os.path.join(card_dir, "log.md"), "w", encoding="utf-8") as f:
        f.write("## %s.1 — шаг закрыт\n\nвывод\n" % PHASE)
    state = os.path.join(base, "state")
    briefs = os.path.join(state, "briefs")
    os.makedirs(briefs)
    with open(os.path.join(briefs, "agent-%s.json" % AGENT), "w", encoding="utf-8") as f:
        json.dump({"role": "executor", "card": CARD, "phase": PHASE}, f)
    return work_root, state, card_dir


def decide(hook_env, tool_name, tool_input):
    payload = {"tool_name": tool_name, "tool_input": tool_input,
               "agent_id": AGENT, "session_id": "s-probe"}
    r = subprocess.run(["bash", HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=hook_env)
    try:
        out = json.loads(r.stdout)
    except Exception:
        return "unparsable", r.stdout + r.stderr
    spec = out.get("hookSpecificOutput", {})
    return spec.get("permissionDecision", "?"), spec.get("permissionDecisionReason", "")


def main():
    base = tempfile.mkdtemp(prefix="gate-boundary-")
    work_root, state, card_dir = build_tree(base)
    env = dict(os.environ)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state
    env.pop("CLAUDE_GATE_BYPASS", None)
    env.pop("CLAUDE_HARNESS_BYPASS", None)

    log_md = os.path.join(card_dir, "log.md")
    cases = [
        ("git -C <копия> add — раньше отказ, теперь пропуск",
         "Bash", {"command": "git -C /tmp/copy add .githooks/pre-commit"}, "allow"),
        ("git -C <копия> commit",
         "Bash", {"command": "git -C /tmp/copy commit -m x"}, "allow"),
        ("голый git add",
         "Bash", {"command": "git add foo"}, "allow"),
        ("bin/work-commit без пути",
         "Bash", {"command": 'bin/work-commit TST-1.A.1 "итог"'}, "allow"),
        ("bin/work-note --handoff",
         "Bash", {"command": 'bin/work-note TST-1 --handoff TST-1.A "состояние"'}, "allow"),
        ("Write в log.md карточки",
         "Write", {"file_path": log_md, "content": "x"}, "allow"),
        ("git status — по-прежнему отказ",
         "Bash", {"command": "git status --short"}, "deny"),
        ("git -C <копия> status — тоже отказ",
         "Bash", {"command": "git -C /tmp/copy status --short"}, "deny"),
        ("git -C <копия> push — отказ",
         "Bash", {"command": "git -C /tmp/copy push"}, "deny"),
        ("cd && bin/work-commit — цепочка, отказ",
         "Bash", {"command": 'cd /tmp/copy && bin/work-commit TST-1.A.1 "итог"'}, "deny"),
        ("git add && git commit — цепочка, отказ",
         "Bash", {"command": "git add foo && git commit -m x"}, "deny"),
        ("Read чужого файла — отказ",
         "Read", {"file_path": os.path.join(card_dir, "plan.md")}, "deny"),
    ]

    failures = 0
    reason_seen = ""
    for title, tool, ti, expected in cases:
        got, reason = decide(env, tool, ti)
        ok = (got == expected)
        if expected == "deny" and got == "deny":
            reason_seen = reason
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + str(got))
        if not ok:
            failures += 1
            print("        ожидалось " + expected + "; текст: " + reason[:200])

    print("\nТекст отказа, который увидит исполнитель:\n")
    print(reason_seen)

    required = ["bin/work-commit", "bin/work-note", "--handoff", "git -C"]
    missing = [s for s in required if s not in reason_seen]
    if missing:
        print("\nFAIL: в тексте отказа нет: " + ", ".join(missing))
        failures += 1

    print("\n%d из %d случаев прошли" % (len(cases) - failures, len(cases)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
