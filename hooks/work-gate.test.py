#!/usr/bin/env python3
"""Synthetic check of work-gate.sh's own rules, against a throwaway state directory and a
throwaway work root — nothing real is touched. HRN-82.A: the PHASE BOUNDARY rule (old rule 5)
this file used to check first and foremost is gone from the hook, and every case built on top
of a closed-phase fixture went with it; what remains checks the rules the hook still carries —
the command reference, the log-write ceiling, repeated search, chained recording calls, the
context/soft-context ceilings, sanction matching and scope.

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


def build_tree(base):
    """A throwaway card folder: plan.md declaring one phase with one step, log.md holding
    that step's own closed heading, and the session's own agent brief. HRN-82.A: there is no
    `<phase>.closed` marker to lay here any more — the hook read that marker only for the
    PHASE BOUNDARY rule, removed along with the phase boundary itself, and no fixture in this
    file builds one."""
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
    # HRN-82.A.3: an "allow" decision can carry text of its own now — the command reference,
    # the repeated-search map, the soft context-ceiling warning — and none of it ever reaches
    # permissionDecisionReason, which the Claude Code hooks reference shows only "when you
    # deny or ask". allow_and_exit(reason) writes that text into
    # hookSpecificOutput.additionalContext instead, so a caller reading only
    # permissionDecisionReason saw every one of these allow-with-text calls as carrying no
    # text at all. permissionDecisionReason is checked first, since a deny never sets
    # additionalContext and this keeps a deny's own reason exactly as it always read.
    reason = spec.get("permissionDecisionReason") or spec.get("additionalContext") or ""
    return spec.get("permissionDecision", "?"), reason



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


def search_cases(base_env, base):
    """The REPEATED SEARCH rule (rule 14) counts searches of one named file: the second one
    is allowed with the card's own map.md attached to it, the third and every later one is
    refused, and a whole-file Read of that path wipes the count. A search of a directory is
    never counted at all. Measured 2026-09-01 on HRN-63.C, six consecutive greps of one file.
    """
    work_root, state, card_dir = build_tree(os.path.join(base, "search"))
    with open(os.path.join(card_dir, "map.md"), "w", encoding="utf-8") as f:
        f.write("Карта источников.\n\nbin/work-who: closed_steps на строке 695, "
                "first_open_step на 725.\n\nbin/work-note: отказы на 408 и 416.\n")
    repo_bin = os.path.join(os.path.dirname(work_root), "bin")
    os.makedirs(repo_bin, exist_ok=True)
    target = os.path.join(repo_bin, "work-who")
    with open(target, "w", encoding="utf-8") as f:
        f.write("\n".join("строка %d" % i for i in range(1, 41)) + "\n")
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state

    failures = 0

    def probe(title, tool, ti, wanted, must_carry=None, must_not_carry=None):
        got, reason = decide(env, tool, ti)
        reason = reason or ""
        ok = got == wanted
        if ok and must_carry:
            ok = all(s in reason for s in must_carry)
        if ok and must_not_carry:
            ok = all(s not in reason for s in must_not_carry)
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + str(got))
        if not ok:
            print("        ожидалось " + wanted + "; текст: " + reason[:300])
        return 0 if ok else 1

    grep_call = ("Bash", {"command": 'grep -n "closed_steps" %s' % target})

    failures += probe("первый поиск проходит молча", *grep_call, "allow",
                      must_not_carry=["второй раз"])
    failures += probe("второй поиск проходит и несёт map.md", *grep_call, "allow",
                      must_carry=["второй раз", "closed_steps на строке 695", "40 строк"])
    failures += probe("третий поиск отказан", *grep_call, "deny",
                      must_carry=["Read этого файла не ограничен", "closed_steps на строке 695"])
    failures += probe("Read целиком проходит", "Read", {"file_path": target}, "allow")
    failures += probe("после Read счёт обнулён, поиск снова молчит", *grep_call, "allow",
                      must_not_carry=["второй раз"])
    failures += probe("инструмент Grep считается тем же счётом", "Grep",
                      {"pattern": "closed_steps", "path": target}, "allow",
                      must_carry=["второй раз"])
    failures += probe("поиск по каталогу не считается", "Bash",
                      {"command": 'grep -rn "closed_steps" %s' % repo_bin}, "allow",
                      must_not_carry=["второй раз"])
    failures += probe("вызов без поиска не считается", "Bash",
                      {"command": "go test ./..."}, "allow", must_not_carry=["второй раз"])
    return failures


def chain_cases(base_env, base):
    """The CHAINED RECORDING CALL rule (rule 15): a real bin/work-note or bin/work-commit
    invocation sitting inside a chain is refused aloud, because every rule that reads those
    commands counts a chained one as no call at all — the log-write ceiling never resets and
    the command itself works. Measured 2026-09-01 on HRN-63.C: one `cd <копия> && bin/work-note
    … --handoff` spent the run's whole ceiling this way. The phase here is open, so nothing
    but this rule could refuse any of these calls.
    """
    work_root, state, card_dir = build_tree(os.path.join(base, "chain"))
    repo_root = os.path.dirname(work_root)
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state

    failures = 0

    def probe(title, command, wanted, must_carry=None):
        got, reason = decide(env, "Bash", {"command": command})
        reason = reason or ""
        ok = got == wanted
        if ok and must_carry:
            ok = all(s in reason for s in must_carry)
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + str(got))
        if not ok:
            print("        ожидалось " + wanted + "; текст: " + reason[:300])
        return 0 if ok else 1

    abs_note = os.path.join(repo_root, "bin", "work-note")
    failures += probe(
        "cd && bin/work-note — отказ, называющий абсолютный путь",
        'cd /tmp/copy && bin/work-note TST-1 TST-1.A.1 "состояние"', "deny",
        must_carry=["CHAINED RECORDING CALL", abs_note])
    failures += probe(
        "тот же вызов абсолютным путём проходит",
        '%s TST-1 TST-1.A.1 "состояние"' % abs_note, "allow")
    failures += probe(
        "цепочка с heredoc — отказ",
        'cd /tmp/copy && bin/work-note TST-1 TST-1.A.1 "состояние" <<\'EOF\'\nвывод\nEOF',
        "deny", must_carry=["CHAINED RECORDING CALL"])
    failures += probe(
        "heredoc без цепочки проходит",
        'bin/work-note TST-1 TST-1.A.1 "состояние" <<\'EOF\'\nвывод\nEOF', "allow")
    failures += probe(
        "cd && bin/work-commit — отказ",
        'cd /tmp/copy && bin/work-commit TST-1.A.1 "итог"', "deny",
        must_carry=["CHAINED RECORDING CALL"])
    failures += probe(
        "`&&` внутри кавычек цепочкой не считается",
        'bin/work-note TST-1 TST-1.A.1 "сделал одно && второе"', "allow")
    failures += probe(
        "упоминание имени команды не в начале звена не считается вызовом",
        "ls && echo bin/work-note", "allow")
    return failures


def _transcript_line(context):
    return json.dumps({
        "type": "assistant",
        "message": {"usage": {"input_tokens": 246,
                               "cache_creation_input_tokens": 10_000,
                               "cache_read_input_tokens": context - 10_246,
                               "output_tokens": 500},
                     "content": [{"type": "text", "text": "…"}]},
    }) + "\n"


def context_ceiling_cases(base_env, base):
    """The CONTEXT SIZE ceiling (rule 8), its soft threshold (HRN-82.A.3), and the escape the
    hard ceiling leaves open. Until HRN-73/HRN-80 that escape was a Write/Edit of this card's
    own log.md and nothing else, and no road reached it: bin/work-note goes through Bash and
    was refused, the editor refuses to write a file the session has not read, the read itself
    was refused by this same ceiling, and the address the rule compared against stopped
    holding the file when HRN-61 moved the journal into the card's own working copy. Measured
    live on HRN-19.A, 2026-09-01: four steps of five closed and not one of them recorded.

    HRN-82.A.3 gave the hard ceiling a soft one below it, 250,000 against 300,000: between the
    two every call still allows, but the JSON carries a warning in
    hookSpecificOutput.additionalContext instead of ever refusing — the replacement for the
    phase boundary's own way of letting a run stop itself of its own will.

    The phase here is open and the log-write ceiling untouched, so nothing but rule 8 can
    refuse any of these calls.
    """
    work_root, state, card_dir = build_tree(os.path.join(base, "context"))
    # The card's own working copy: the journal's real address since HRN-61.
    copy_root = os.path.join(base, "context-copy")
    copy_card_dir = os.path.join(copy_root, "ai", "harness", "epic", CARD + "_probe")
    os.makedirs(copy_card_dir)
    copy_log = os.path.join(copy_card_dir, "log.md")
    with open(copy_log, "w", encoding="utf-8") as f:
        f.write("## %s.1 — шаг закрыт\n\nвывод\n" % PHASE)

    # A transcript whose last turn holds more than the 300,000-token hard ceiling.
    transcript = os.path.join(base, "context-transcript.jsonl")
    with open(transcript, "w", encoding="utf-8") as f:
        for context in (120_000, 385_246):
            f.write(_transcript_line(context))

    # A second transcript whose last turn sits between the 250,000 soft ceiling and the
    # 300,000 hard one — every call here still allows.
    soft_transcript = os.path.join(base, "context-soft-transcript.jsonl")
    with open(soft_transcript, "w", encoding="utf-8") as f:
        for context in (120_000, 275_000):
            f.write(_transcript_line(context))

    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state
    env["WORK_GATE_CARD_WORKTREE_ROOT"] = copy_root
    env["WORK_GATE_AGENT_TRANSCRIPT"] = transcript

    failures = 0
    denial = ""

    def probe(title, tool, ti, wanted, must_carry=None, env_override=None):
        nonlocal denial
        got, reason = decide(env_override or env, tool, ti)
        reason = reason or ""
        if got == "deny":
            denial = reason
        ok = got == wanted
        if ok and must_carry:
            ok = all(s in reason for s in must_carry)
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + str(got))
        if not ok:
            print("        ожидалось " + wanted + "; текст: " + reason[:400])
        return 0 if ok else 1

    soft_env = dict(env)
    soft_env["WORK_GATE_AGENT_TRANSCRIPT"] = soft_transcript
    failures += probe("между мягким и жёстким потолком — allow с предупреждением",
                      "Bash", {"command": "go test ./..."}, "allow",
                      must_carry=["250000", "275000", "soft ceiling"],
                      env_override=soft_env)

    failures += probe("обычный вызов упирается в потолок контекста", "Bash",
                      {"command": "go test ./..."}, "deny",
                      must_carry=["CONTEXT SIZE", "385246"])
    failures += probe("bin/work-note своей карточки проходит", "Bash",
                      {"command": 'bin/work-note TST-1 --handoff TST-1.A "состояние"'},
                      "allow")
    failures += probe("bin/work-note с текстом проверки на входе проходит", "Bash",
                      {"command": 'bin/work-note TST-1 TST-1.A.1 "состояние" <<\'EOF\'\n'
                                   'вывод проверки\nEOF'}, "allow")
    failures += probe("bin/work-note чужой карточки отказан", "Bash",
                      {"command": 'bin/work-note TST-9 --handoff TST-9.A "состояние"'},
                      "deny")
    failures += probe("bin/work-commit проходит", "Bash",
                      {"command": 'bin/work-commit TST-1.A.1 "итог"'}, "allow")
    failures += probe("цепочка с bin/work-note отказана", "Bash",
                      {"command": 'cd /tmp/x && bin/work-note TST-1 TST-1.A.1 "с"'}, "deny")
    failures += probe("Read журнала в рабочей копии проходит", "Read",
                      {"file_path": copy_log}, "allow")
    failures += probe("Write журнала в рабочей копии проходит", "Write",
                      {"file_path": copy_log, "content": "x"}, "allow")
    failures += probe("Write журнала в общем каталоге тоже проходит", "Write",
                      {"file_path": os.path.join(card_dir, "log.md"), "content": "x"},
                      "allow")
    failures += probe("Read чужого файла отказан", "Read",
                      {"file_path": os.path.join(card_dir, "plan.md")}, "deny")
    failures += probe("Write чужого файла отказан", "Write",
                      {"file_path": os.path.join(copy_card_dir, "map.md"), "content": "x"},
                      "deny")

    required = ["bin/work-note TST-1 --handoff TST-1.A", "bin/work-commit TST-1.A.<N>",
                copy_log]
    missing = [s for s in required if s not in denial]
    ok = not missing
    print(("  ok   " if ok else "  FAIL ") +
          "отказ называет обе команды и настоящий адрес журнала")
    if not ok:
        print("        нет в тексте: " + ", ".join(missing))
        print("        текст: " + denial)
        failures += 1

    print("\n  Текст отказа по потолку контекста:\n")
    print(denial)
    return failures


def sanction_cases(base_env, base):
    """An executor spawn is judged against every sanction this conversation wrote, newest
    first, and a card that has already reached a terminal state never counts as the match.
    Measured 2026-09-01: a spawn for a live card was refused outright because its brief
    mentioned an already-accepted card whose sanction file happens to sort first by name.
    """
    root = os.path.join(base, "sanctions")
    work_root = os.path.join(root, "ai")
    epic = os.path.join(work_root, "harness", "epic")
    os.makedirs(epic)
    for card_id, done in (("TST-1", True), ("TST-2", False)):
        card_dir = os.path.join(epic, card_id + "_probe")
        os.makedirs(card_dir)
        if done:
            with open(os.path.join(card_dir, "done.md"), "w", encoding="utf-8") as f:
                f.write("принято\n")
    session = "s-sanction"
    state = os.path.join(root, "state")
    sdir = os.path.join(state, "sanctions", session)
    os.makedirs(sdir)
    for card_id, when in (("TST-1", 100.0), ("TST-2", 200.0)):
        with open(os.path.join(sdir, card_id + ".json"), "w", encoding="utf-8") as f:
            json.dump({"card": card_id, "phase": card_id + ".A", "time": when,
                       "estimate": 1, "short": True}, f)
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state

    def spawn(prompt):
        payload = {"tool_name": "Agent",
                   "tool_input": {"subagent_type": "executor", "prompt": prompt,
                                   "description": ""},
                   "session_id": session}
        r = subprocess.run(["bash", HOOK], input=json.dumps(payload),
                           capture_output=True, text=True, env=env)
        try:
            spec = json.loads(r.stdout).get("hookSpecificOutput", {})
        except Exception:
            return "unparsable", r.stdout + r.stderr
        return spec.get("permissionDecision", "?"), spec.get("permissionDecisionReason", "")

    failures = 0
    cases = [
        ("задание живой карточки, упоминающее законченную, проходит",
         "Работай карточку TST-2. Её текст правит то, что закрыла TST-1.", "allow"),
        ("задание, называющее только законченную карточку, отказано",
         "Работай карточку TST-1.", "deny"),
        ("задание, не называющее ни одной карточки, отказано",
         "Просто поработай.", "deny"),
    ]
    for title, prompt, wanted in cases:
        got, reason = spawn(prompt)
        ok = got == wanted
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + str(got))
        if not ok:
            print("        ожидалось " + wanted + "; текст: " + (reason or "")[:200])
            failures += 1
    return failures


def scope_cases(base_env, base):
    """Rule 1b: the gate governs only the repository that carries the work-management
    system — an ai/ directory holding both card kinds as real directories of its own."""
    print("\nОбласть действия (правило 1b):")
    failures = 0
    payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"},
                          "agent_id": "probe", "session_id": "s-scope"})

    def decide_in(repo, env_extra=None):
        env = dict(base_env)
        env.pop("WORK_GATE_SCOPE", None)
        env.update(env_extra or {})
        r = subprocess.run(["bash", HOOK], input=payload, capture_output=True,
                           text=True, env=env, cwd=repo)
        try:
            out = json.loads(r.stdout)["hookSpecificOutput"]
        except Exception:
            return "allow"
        return out.get("permissionDecision", "allow")

    def make_repo(name, kinds, symlink=False):
        repo = os.path.join(base, name)
        os.makedirs(os.path.join(repo, "ai"), exist_ok=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, capture_output=True)
        for kind in kinds:
            d = os.path.join(repo, "ai", kind)
            if symlink:
                os.makedirs(os.path.join(repo, "ai", "_real_" + kind), exist_ok=True)
                if not os.path.islink(d):
                    os.symlink("_real_" + kind, d)
            else:
                os.makedirs(d, exist_ok=True)
        return repo

    checks = [
        ("репозиторий с обеими папками карточек судится",
         make_repo("scope-app", ("harness", "timeline")), None, "deny"),
        ("репозиторий без папок карточек не судится",
         make_repo("scope-plain", ()), None, "allow"),
        ("репозиторий только с harness не судится",
         make_repo("scope-half", ("harness",)), None, "allow"),
        ("симлинк вместо настоящей папки не считается",
         make_repo("scope-link", ("harness", "timeline"), symlink=True), None, "allow"),
        ("WORK_GATE_SCOPE=off выключает даже в нужном репозитории",
         make_repo("scope-app2", ("harness", "timeline")), {"WORK_GATE_SCOPE": "off"}, "allow"),
        ("WORK_GATE_SCOPE=on включает в постороннем репозитории",
         make_repo("scope-plain2", ()), {"WORK_GATE_SCOPE": "on"}, "deny"),
    ]
    for title, repo, extra, expected in checks:
        got = decide_in(repo, extra)
        ok = got == expected
        failures += 0 if ok else 1
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + got)
        if not ok:
            print("        ожидалось " + expected)
    return failures


def main():
    base = tempfile.mkdtemp(prefix="gate-boundary-")
    env = dict(os.environ)
    env.pop("CLAUDE_GATE_BYPASS", None)
    env.pop("CLAUDE_HARNESS_BYPASS", None)
    # Every case below exercises a RULE, not the scope question rule 1b answers, and the
    # fixture trees these cases build are not the application's own checkout, so the scope
    # rule would switch the gate off before any rule under test ever ran. Forced on here;
    # scope_cases() below is what actually tests rule 1b.
    env["WORK_GATE_SCOPE"] = "on"

    failures = 0

    print("\nСправочник команд:")
    failures += reference_cases(env, base)

    print("\nПотолок вызовов без записи в журнал:")
    failures += ceiling_cases(env, base)

    print("\nПовторный поиск по одному файлу:")
    failures += search_cases(env, base)

    print("\nВызов записи, собранный цепочкой:")
    failures += chain_cases(env, base)

    print("\nПотолок размера контекста и выход из-под него:")
    failures += context_ceiling_cases(env, base)

    print("\nРазрешение на подъём исполнителя:")
    failures += sanction_cases(env, base)
    failures += scope_cases(env, base)

    print("\n%d случаев не прошли" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
