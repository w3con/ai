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
# A stand-in for bin/templates/executor-brief.md in the validite-app repository: this
# test must not depend on that repository being checked out beside this one, so it writes
# its own template carrying the same two headings the hook slices between.
TEMPLATE_TEXT = """Справочник команд: этим ты работаешь.

  Закрыть шаг:
      bin/work-note {{CARD_ID}} <шаг> "<состояние>"
  Закоммитить код шага:
      bin/work-commit <шаг> "<итог>"
  question.md кладётся в {{CARD_DIR}}, фаза сейчас {{PHASE}}.

Постоянное поведение исполнителя:
1. …
"""
PHASE = "TST-1.A"


def build_tree(base, phase_closed=False):
    """HRN-63.B: the boundary no longer reads log.md's own headings at all — it reads one
    fact, whether `<phase>.closed` sits in the card's own folder. `phase_closed=True` lays
    that marker directly (no gate is actually run in this synthetic tree), giving the
    boundary the same "this phase is done" state the old fixture used to fake by writing a
    closing heading; `phase_closed=False` (the default) leaves the phase open, exactly as no
    marker on disk always means."""
    work_root = os.path.join(base, "ai")
    card_dir = os.path.join(work_root, "harness", "epic", CARD + "_probe")
    os.makedirs(card_dir)
    with open(os.path.join(card_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write("## Шаги\n\n### %s — фаза\n\n- [%s.1] один шаг\n\n## Критерии приёмки\n"
                % (PHASE, PHASE))
    with open(os.path.join(card_dir, "log.md"), "w", encoding="utf-8") as f:
        f.write("## %s.1 — шаг закрыт\n\nвывод\n" % PHASE)
    if phase_closed:
        with open(os.path.join(card_dir, PHASE + ".closed"), "w", encoding="utf-8"):
            pass
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



def reference_cases(base_env, base):
    """The command reference must reach the first save-shaped call of a run whose phase is
    still open, exactly once, and must never turn an allow into a refusal."""
    work_root, state, card_dir = build_tree(os.path.join(base, "open"))
    # no <фаза>.closed marker on disk → the phase is open, the boundary stays silent
    with open(os.path.join(card_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write("## Шаги\n\n### %s — фаза\n\n- [%s.1] один\n- [%s.2] два\n"
                % (PHASE, PHASE, PHASE))
    repo_bin = os.path.join(os.path.dirname(work_root), "bin", "templates")
    os.makedirs(repo_bin)
    with open(os.path.join(repo_bin, "executor-brief.md"), "w",
              encoding="utf-8") as f:
        f.write(TEMPLATE_TEXT)
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state

    failures = 0
    got, reason = decide(env, "Bash", {"command": 'bin/work-commit TST-1.A.1 "итог"'})
    ok = got == "allow" and "bin/work-note" in reason and "bin/work-commit" in reason
    print(("  ok   " if ok else "  FAIL ") + "первый вызов-сохранение получает справочник")
    failures += 0 if ok else 1

    got2, reason2 = decide(env, "Bash", {"command": 'bin/work-commit TST-1.A.2 "итог"'})
    ok2 = got2 == "allow" and "bin/work-note" not in (reason2 or "")
    print(("  ok   " if ok2 else "  FAIL ") + "второй вызов справочник не повторяет")
    failures += 0 if ok2 else 1

    work_root3, state3, card_dir3 = build_tree(os.path.join(base, "other"))
    with open(os.path.join(card_dir3, "plan.md"), "w", encoding="utf-8") as f:
        f.write("## Шаги\n\n### %s — фаза\n\n- [%s.1] один\n- [%s.2] два\n"
                % (PHASE, PHASE, PHASE))
    env3 = dict(base_env)
    env3["WORK_GATE_WORK_ROOT"] = work_root3
    env3["WORK_GATE_STATE_DIR"] = state3
    got3, _ = decide(env3, "Bash", {"command": "go test ./..."})
    ok3 = got3 == "allow"
    print(("  ok   " if ok3 else "  FAIL ") + "обычный вызов не трогается")
    failures += 0 if ok3 else 1

    got4, _ = decide(env3, "Bash", {"command": 'bin/work-commit TST-1.A.1 "итог"'})
    ok4 = got4 == "allow"
    print(("  ok   " if ok4 else "  FAIL ") + "без шаблона вызов всё равно проходит")
    failures += 0 if ok4 else 1
    return failures


def ceiling_cases(base_env, base):
    """The LOG-WRITE CEILING (rule 7) resets only on a call that records a closed step.
    A --handoff call passes the ceiling — a run that has hit it must always be able to
    record its own state — but resets nothing, so the very next ordinary call is refused
    again. Before this was narrowed, --handoff reset the count like any other work-note
    call, and an executor bought itself twenty fresh calls with a call that built nothing
    (measured 2026-09-01 on HRN-63.C, six consecutive --handoff calls).
    """
    work_root, state, card_dir = build_tree(os.path.join(base, "ceiling"))
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state

    ordinary = ("Bash", {"command": "go test ./..."})
    handoff = ("Bash", {"command": 'bin/work-note TST-1 --handoff TST-1.A "состояние"'})
    step_note = ("Bash", {"command": 'bin/work-note TST-1 TST-1.A.1 "состояние"'})

    failures = 0

    def expect(title, tool, ti, wanted):
        got, reason = decide(env, tool, ti)
        ok = got == wanted
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + str(got))
        if not ok:
            print("        ожидалось " + wanted + "; текст: " + (reason or "")[:200])
        return 0 if ok else 1

    # 19 ordinary calls stay under the ceiling of 20; the 20th is the one refused.
    under = 0
    for _ in range(19):
        got, _ = decide(env, *ordinary)
        if got != "allow":
            under += 1
    ok = under == 0
    print(("  ok   " if ok else "  FAIL ") + "19 обычных вызовов проходят  → allow")
    failures += 0 if ok else 1

    failures += expect("20-й обычный вызов упирается в потолок", *ordinary, "deny")
    failures += expect("--handoff проходит потолок", *handoff, "allow")
    failures += expect("после --handoff обычный вызов снова отказан", *ordinary, "deny")
    failures += expect("запись с именем шага проходит", *step_note, "allow")
    failures += expect("после записи шага обычный вызов проходит", *ordinary, "allow")
    return failures


def main():
    base = tempfile.mkdtemp(prefix="gate-boundary-")
    work_root, state, card_dir = build_tree(base, phase_closed=True)
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

    print("\nСправочник команд:")
    failures += reference_cases(env, base)

    print("\nПотолок вызовов без записи в журнал:")
    failures += ceiling_cases(env, base)

    print("\n%d случаев не прошли" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
