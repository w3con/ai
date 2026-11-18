#!/usr/bin/env python3
"""Exercise work-gate decisions using synthetic payloads and temporary state.

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
# English template used for ordinary fixtures.
TEMPLATE_TEXT = """Command reference:

  Close a step:
      bin/work-note {{CARD_ID}} <step> "<status>"
  Commit step work:
      bin/work-commit <step> "<result>"
  question.md is stored in {{CARD_DIR}}, current phase: {{PHASE}}.

Executor behavior:
1. …
"""


def legacy_brief_template():
    """Build a synthetic legacy-format fixture using escaped schema headings."""
    reference = "\u0421\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a \u043a\u043e\u043c\u0430\u043d\u0434:"
    behavior = "\u041f\u043e\u0441\u0442\u043e\u044f\u043d\u043d\u043e\u0435 \u043f\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u0435 \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044f"
    return (reference + "\n\n  Close a step:\n      bin/work-note {{CARD_ID}} <step> \"<status>\"\n"
            "  Commit step work:\n      bin/work-commit <step> \"<result>\"\n\n"
            + behavior + "\n1. …\n")
PHASE = "TST-1.A"
# Marker used to compare the common boundary-denial text.
SHELL_SCOPE_NOTE_MARKER = "This boundary is judged on a shell write too"


def build_tree(base):
    """Create a synthetic card, state directory, and executor brief."""
    work_root = os.path.join(base, "ai")
    card_dir = os.path.join(work_root, "harness", "epic", CARD + "_probe")
    os.makedirs(card_dir)
    with open(os.path.join(card_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write("## Steps\n\n### %s — phase\n\n- [%s.1] one step\n\n## Acceptance criteria\n"
                % (PHASE, PHASE))
    with open(os.path.join(card_dir, "log.md"), "w", encoding="utf-8") as f:
        f.write("## %s.1 — step closed\n\noutput\n" % PHASE)
    state = os.path.join(base, "state")
    briefs = os.path.join(state, "briefs")
    os.makedirs(briefs)
    with open(os.path.join(briefs, "agent-%s.json" % AGENT), "w", encoding="utf-8") as f:
        json.dump({"role": "executor", "card": CARD, "phase": PHASE}, f)
    return work_root, state, card_dir


def decide(hook_env, tool_name, tool_input, agent_id=AGENT):
    payload = {"tool_name": tool_name, "tool_input": tool_input,
               "agent_id": agent_id, "session_id": "s-probe"}
    r = subprocess.run(["bash", HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=hook_env)
    try:
        out = json.loads(r.stdout)
    except Exception:
        return "unparsable", r.stdout + r.stderr
    spec = out.get("hookSpecificOutput", {})
    # Allow explanations may be returned as additional context; denials use their reason.
    reason = spec.get("permissionDecisionReason") or spec.get("additionalContext") or ""
    return spec.get("permissionDecision", "?"), reason



def reference_cases(base_env, base):
    """Verify English and legacy brief headings inject the reference exactly once."""
    failures = 0

    def verify_template(name, template_text):
        nonlocal failures
        work_root, state, card_dir = build_tree(os.path.join(base, name))
        with open(os.path.join(card_dir, "plan.md"), "w", encoding="utf-8") as f:
            f.write("## Steps\n\n### %s — phase\n\n- [%s.1] one\n- [%s.2] two\n"
                    % (PHASE, PHASE, PHASE))
        template_dir = os.path.join(os.path.dirname(work_root), "bin", "templates")
        os.makedirs(template_dir)
        with open(os.path.join(template_dir, "executor-brief.md"), "w", encoding="utf-8") as f:
            f.write(template_text)
        env = dict(base_env, WORK_GATE_WORK_ROOT=work_root, WORK_GATE_STATE_DIR=state)
        got, reason = decide(env, "Bash", {"command": 'bin/work-commit TST-1.A.1 "result"'})
        ok = got == "allow" and "bin/work-note" in reason and "bin/work-commit" in reason
        print(("  ok   " if ok else "  FAIL ") + name + " reference appears on first save call")
        if not ok:
            print("        decision: %s; reference: %s" % (got, reason[:300]))
        failures += 0 if ok else 1
        got2, reason2 = decide(env, "Bash", {"command": 'bin/work-commit TST-1.A.2 "result"'})
        ok2 = got2 == "allow" and "bin/work-note" not in (reason2 or "")
        print(("  ok   " if ok2 else "  FAIL ") + name + " reference is not repeated")
        failures += 0 if ok2 else 1

    verify_template("english-reference", TEMPLATE_TEXT)
    verify_template("legacy-reference", legacy_brief_template())

    work_root, state, _ = build_tree(os.path.join(base, "missing-template"))
    env = dict(base_env, WORK_GATE_WORK_ROOT=work_root, WORK_GATE_STATE_DIR=state)
    got, _ = decide(env, "Bash", {"command": 'bin/work-commit TST-1.A.1 "result"'})
    ok = got == "allow"
    print(("  ok   " if ok else "  FAIL ") + "missing template does not block the call")
    failures += 0 if ok else 1
    return failures


def ceiling_cases(base_env, base):
    """Verify handoffs pass the log-write ceiling without resetting the count."""
    work_root, state, card_dir = build_tree(os.path.join(base, "ceiling"))
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state

    ordinary = ("Bash", {"command": "go test ./..."})
    handoff = ("Bash", {"command": 'bin/work-note TST-1 --handoff TST-1.A "status"'})
    step_note = ("Bash", {"command": 'bin/work-note TST-1 TST-1.A.1 "status"'})

    failures = 0

    def expect(title, tool, ti, wanted):
        got, reason = decide(env, tool, ti)
        ok = got == wanted
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + str(got))
        if not ok:
            print("        expected " + wanted + "; reason: " + (reason or "")[:200])
        return 0 if ok else 1

    # 19 ordinary calls stay under the ceiling of 20; the 20th is the one refused.
    under = 0
    for _ in range(19):
        got, _ = decide(env, *ordinary)
        if got != "allow":
            under += 1
    ok = under == 0
    print(("  ok   " if ok else "  FAIL ") + "19 ordinary calls pass  → allow")
    failures += 0 if ok else 1

    failures += expect("20th ordinary call reaches the ceiling", *ordinary, "deny")
    failures += expect("--handoff passes the ceiling", *handoff, "allow")
    failures += expect("ordinary call is refused after handoff", *ordinary, "deny")
    failures += expect("step note passes", *step_note, "allow")
    failures += expect("ordinary call passes after step note", *ordinary, "allow")
    return failures


def search_cases(base_env, base):
    """Verify repeated searches attach guidance, refuse later attempts, and reset on Read."""
    work_root, state, card_dir = build_tree(os.path.join(base, "search"))
    with open(os.path.join(card_dir, "map.md"), "w", encoding="utf-8") as f:
        f.write("Source map.\n\nbin/work-who: closed_steps near line 695, "
                "first_open_step near 725.\n\nbin/work-note: refusals near 408 and 416.\n")
    repo_bin = os.path.join(os.path.dirname(work_root), "bin")
    os.makedirs(repo_bin, exist_ok=True)
    target = os.path.join(repo_bin, "work-who")
    with open(target, "w", encoding="utf-8") as f:
        f.write("\n".join("line %d" % i for i in range(1, 41)) + "\n")
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
            print("        expected " + wanted + "; reason: " + reason[:300])
        return 0 if ok else 1

    grep_call = ("Bash", {"command": 'grep -n "closed_steps" %s' % target})

    failures += probe("first search passes without guidance", *grep_call, "allow",
                      must_not_carry=["second search"])
    failures += probe("second search passes with map guidance", *grep_call, "allow",
                      must_carry=["second search", "closed_steps near line 695", "40 lines"])
    failures += probe("third search is refused", *grep_call, "deny",
                      must_carry=["whole-file Read has no limit", "closed_steps near line 695"])
    failures += probe("whole-file Read passes", "Read", {"file_path": target}, "allow")
    failures += probe("search is reset after Read", *grep_call, "allow",
                      must_not_carry=["second search"])
    failures += probe("Grep uses the same counter", "Grep",
                      {"pattern": "closed_steps", "path": target}, "allow",
                      must_carry=["second search"])
    failures += probe("directory search is not counted", "Bash",
                      {"command": 'grep -rn "closed_steps" %s' % repo_bin}, "allow",
                      must_not_carry=["second search"])
    failures += probe("non-search call is not counted", "Bash",
                      {"command": "go test ./..."}, "allow", must_not_carry=["second search"])
    return failures


def chain_cases(base_env, base):
    """Verify chained state-recording commands are refused."""
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
            print("        expected " + wanted + "; reason: " + reason[:300])
        return 0 if ok else 1

    abs_note = os.path.join(repo_root, "bin", "work-note")
    failures += probe(
        "chained work-note is refused and names its absolute path",
        'cd /tmp/copy && bin/work-note TST-1 TST-1.A.1 "status"', "deny",
        must_carry=["CHAINED RECORDING CALL", abs_note])
    failures += probe(
        "absolute-path invocation passes",
        '%s TST-1 TST-1.A.1 "status"' % abs_note, "allow")
    failures += probe(
        "heredoc command chain is refused",
        'cd /tmp/copy && bin/work-note TST-1 TST-1.A.1 "status" <<\'EOF\'\noutput\nEOF',
        "deny", must_carry=["CHAINED RECORDING CALL"])
    failures += probe(
        "heredoc without a chain passes",
        'bin/work-note TST-1 TST-1.A.1 "status" <<\'EOF\'\noutput\nEOF', "allow")
    failures += probe(
        "chained work-commit is refused",
        'cd /tmp/copy && bin/work-commit TST-1.A.1 "result"', "deny",
        must_carry=["CHAINED RECORDING CALL"])
    failures += probe(
        "quoted separator is not treated as a chain",
        'bin/work-note TST-1 TST-1.A.1 "did one && then another"', "allow")
    failures += probe(
        "command name outside program position is not an invocation",
        "ls && echo bin/work-note", "allow")
    return failures


def brief_quote_cases(base_env, base):
    """Verify quoted brief commands in heredocs are not executed or parsed as commands."""
    work_root, state, card_dir = build_tree(os.path.join(base, "briefquote"))
    briefs_dir = os.path.join(state, "briefs")
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state

    failures = 0
    own_brief_path = os.path.join(briefs_dir, "agent-%s.json" % AGENT)

    # A quoted brief command must not overwrite the existing brief.
    before = open(own_brief_path, encoding="utf-8").read()
    quoting_command = (
        'bin/work-note TST-1 TST-1.A.1 "status" <<\'EOF\'\n'
        'bin/work-agent-brief --role critic --card TST-9\nEOF'
    )
    got, _ = decide(env, "Bash", {"command": quoting_command})
    after = open(own_brief_path, encoding="utf-8").read()
    ok = got == "allow" and before == after
    print(("  ok   " if ok else "  FAIL ") +
          "quoted brief command in heredoc does not overwrite the active brief")
    if not ok:
        print("        before: %s\n        after: %s" % (before, after))
    failures += 0 if ok else 1

    # Also check an unpaired apostrophe in the heredoc body.
    before2 = open(own_brief_path, encoding="utf-8").read()
    quoting_command_apostrophe = (
        'bin/work-note TST-1 TST-1.A.1 "status" <<\'EOF\'\n'
        "l'exécuteur a cité bin/work-agent-brief --role critic --card TST-9\nEOF"
    )
    got7, reason7 = decide(env, "Bash", {"command": quoting_command_apostrophe})
    after2 = open(own_brief_path, encoding="utf-8").read()
    ok7 = got7 == "allow" and before2 == after2
    print(("  ok   " if ok7 else "  FAIL ") +
          "quoted brief command with an unmatched apostrophe leaves the brief unchanged")
    if not ok7:
        print("        before: %s\n        after: %s" % (before2, after2))
        print("        decision: %s; reason: %s" % (got7, (reason7 or "")[:200]))
    failures += 0 if ok7 else 1

    # A caller without a brief must not bypass the missing-brief decision by quoting a command.
    no_brief_agent = "agent-briefquote-nobrief"
    no_brief_command = (
        'bin/work-note TST-1 TST-1.A.1 "status" <<\'EOF\'\n'
        'bin/work-agent-brief --role executor --card TST-1\nEOF'
    )
    got2, reason2 = decide(env, "Bash", {"command": no_brief_command}, agent_id=no_brief_agent)
    ok2 = got2 == "deny" and "no caller-brief file" in (reason2 or "")
    print(("  ok   " if ok2 else "  FAIL ") +
          "caller without a brief is refused instead of entering the brief-writing branch")
    if not ok2:
        print("        decision: %s; reason: %s" % (got2, (reason2 or "")[:300]))
    failures += 0 if ok2 else 1

    return failures


def brief_real_call_cases(base_env, base):
    """Verify invocation forms create the requested role, card, phase, and work root.

    The cases cover a short path, an absolute path, and an environment-prefixed command.
    Each check compares all saved fields with the values supplied by that command.
    """
    _, state, _ = build_tree(os.path.join(base, "briefforms"))
    briefs_dir = os.path.join(state, "briefs")
    env = dict(base_env)
    env["WORK_GATE_STATE_DIR"] = state

    failures = 0
    wanted = {"role": "executor", "card": "TST-7", "phase": "TST-7.A",
              "work_root": "/tmp/root-7"}
    forms = (
        ("short path", "short",
         'bin/work-agent-brief --role executor --card TST-7 --phase TST-7.A '
         '--root /tmp/root-7'),
        ("absolute path", "full",
         '/some/where/bin/work-agent-brief --role executor --card TST-7 --phase TST-7.A '
         '--root /tmp/root-7'),
        ("environment-prefixed path", "envfirst",
         'FOO=bar bin/work-agent-brief --role executor --card TST-7 --phase TST-7.A '
         '--root /tmp/root-7'),
    )
    for title, tag, command in forms:
        agent_id = "agent-briefforms-" + tag
        got, _ = decide(env, "Bash", {"command": command}, agent_id=agent_id)
        path = os.path.join(briefs_dir, "agent-%s.json" % agent_id)
        content = None
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                try:
                    content = json.load(f)
                except Exception:
                    content = None
        ok = got == "allow" and content == wanted
        print(("  ok   " if ok else "  FAIL ") +
              "real %s invocation writes the requested role/card/phase/root" % title)
        if not ok:
            print("        decision: %s; saved: %s" % (got, content))
        failures += 0 if ok else 1
    return failures


def quoted_log_name_no_reset_cases(base_env, base):
    """Verify a quoted command mention does not reset the log-write ceiling."""
    work_root, state, card_dir = build_tree(os.path.join(base, "quotedlogname-ceiling"))
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state

    for i in range(19):
        got, _ = decide(env, "Bash", {"command": "go test ./..."})
        if got != "allow":
            print("  FAIL unexpected refusal on ordinary call %d" % (i + 1))
            return 1

    got, reason = decide(env, "Bash",
                         {"command": 'echo "record this later with bin/work-note"'})
    ok = got == "deny" and "LOG CEILING" in (reason or "")
    print(("  ok   " if ok else "  FAIL ") +
          "quoted work-note mention in an argument does not reset the log ceiling")
    if not ok:
        print("        decision: %s; reason: %s" % (got, (reason or "")[:200]))
    return 0 if ok else 1


def quoted_log_name_no_chain_refusal_cases(base_env, base):
    """Verify a quoted command mention does not trigger chained-call refusal."""
    work_root, state, card_dir = build_tree(os.path.join(base, "quotedlogname-chain"))
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state

    got, reason = decide(env, "Bash",
                         {"command": 'ls && echo "record with bin/work-note"'})
    ok = got == "allow"
    print(("  ok   " if ok else "  FAIL ") +
          "quoted work-note mention in a chain is not treated as a chained invocation")
    if not ok:
        print("        decision: %s; reason: %s" % (got, (reason or "")[:200]))
    return 0 if ok else 1


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
    """Exercise hard and soft context limits and their state-recording escapes."""
    work_root, state, card_dir = build_tree(os.path.join(base, "context"))
    # The linked working copy contains the alternate log path.
    copy_root = os.path.join(base, "context-copy")
    copy_card_dir = os.path.join(copy_root, "ai", "harness", "epic", CARD + "_probe")
    os.makedirs(copy_card_dir)
    copy_log = os.path.join(copy_card_dir, "log.md")
    with open(copy_log, "w", encoding="utf-8") as f:
        f.write("## %s.1 — step closed\n\noutput\n" % PHASE)

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
            print("        expected " + wanted + "; reason: " + reason[:400])
        return 0 if ok else 1

    soft_env = dict(env)
    soft_env["WORK_GATE_AGENT_TRANSCRIPT"] = soft_transcript
    failures += probe("between soft and hard ceilings, allow with warning",
                      "Bash", {"command": "go test ./..."}, "allow",
                      must_carry=["250000", "275000", "soft ceiling"],
                      env_override=soft_env)

    failures += probe("ordinary call reaches the context ceiling", "Bash",
                      {"command": "go test ./..."}, "deny",
                      must_carry=["CONTEXT SIZE", "385246"])
    failures += probe("work-note for this card passes", "Bash",
                      {"command": 'bin/work-note TST-1 --handoff TST-1.A "status"'},
                      "allow")
    failures += probe("work-note with check output passes", "Bash",
                      {"command": 'bin/work-note TST-1 TST-1.A.1 "status" <<\'EOF\'\n'
                                   'check output\nEOF'}, "allow")
    failures += probe("work-note for another card is refused", "Bash",
                      {"command": 'bin/work-note TST-9 --handoff TST-9.A "status"'},
                      "deny")
    failures += probe("work-commit passes", "Bash",
                      {"command": 'bin/work-commit TST-1.A.1 "result"'}, "allow")
    failures += probe("chained work-note is refused", "Bash",
                      {"command": 'cd /tmp/x && bin/work-note TST-1 TST-1.A.1 "status"'}, "deny")
    failures += probe("Read of linked-worktree log passes", "Read",
                      {"file_path": copy_log}, "allow")
    failures += probe("Write of linked-worktree log passes", "Write",
                      {"file_path": copy_log, "content": "x"}, "allow")
    failures += probe("Write of shared log also passes", "Write",
                      {"file_path": os.path.join(card_dir, "log.md"), "content": "x"},
                      "allow")
    failures += probe("Read of another card file is refused", "Read",
                      {"file_path": os.path.join(card_dir, "plan.md")}, "deny")
    failures += probe("Write of another card file is refused", "Write",
                      {"file_path": os.path.join(copy_card_dir, "map.md"), "content": "x"},
                      "deny")

    required = ["bin/work-note TST-1 --handoff TST-1.A", "bin/work-commit TST-1.A.<N>",
                copy_log]
    missing = [s for s in required if s not in denial]
    ok = not missing
    print(("  ok   " if ok else "  FAIL ") +
          "denial names both commands and the actual log path")
    if not ok:
        print("        missing from reason: " + ", ".join(missing))
        print("        reason: " + denial)
        failures += 1

    print("\n  Context-ceiling refusal:\n")
    print(denial)
    return failures


def sanction_cases(base_env, base):
    """Verify newest sanctions are matched and terminal cards are skipped."""
    root = os.path.join(base, "sanctions")
    work_root = os.path.join(root, "ai")
    epic = os.path.join(work_root, "harness", "epic")
    os.makedirs(epic)
    for card_id, done in (("TST-1", True), ("TST-2", False)):
        card_dir = os.path.join(epic, card_id + "_probe")
        os.makedirs(card_dir)
        if done:
            with open(os.path.join(card_dir, "done.md"), "w", encoding="utf-8") as f:
                f.write("accepted\n")
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
        ("prompt naming an active card and mentioning a completed card passes",
         "Work on card TST-2. Its text edits what TST-1 completed.", "allow"),
        ("prompt naming only a completed card is refused",
         "Work on card TST-1.", "deny"),
        ("prompt naming no card is refused",
         "Do the work.", "deny"),
    ]
    for title, prompt, wanted in cases:
        got, reason = spawn(prompt)
        ok = got == wanted
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + str(got))
        if not ok:
            print("        expected " + wanted + "; reason: " + (reason or "")[:200])
            failures += 1
    return failures


def _git(args, cwd):
    subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True, check=True)


def build_boundary_repo(base, linked=True):
    """Build linked or separate repositories for boundary tests."""
    shared_root = os.path.join(base, "shared")
    os.makedirs(shared_root)
    _git(["init", "-q"], cwd=shared_root)
    _git(["config", "user.email", "t@example.com"], cwd=shared_root)
    _git(["config", "user.name", "t"], cwd=shared_root)
    work_root = os.path.join(shared_root, "ai")
    card_dir = os.path.join(work_root, "harness", "epic", CARD + "_probe")
    os.makedirs(card_dir)
    with open(os.path.join(card_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write("plan\n")
    _git(["add", "-A"], cwd=shared_root)
    _git(["commit", "-q", "-m", "init"], cwd=shared_root)
    if linked:
        _git(["branch", "work/" + CARD.lower()], cwd=shared_root)
        own_root = os.path.join(base, "own-copy")
        _git(["worktree", "add", "-q", own_root, "work/" + CARD.lower()], cwd=shared_root)
    else:
        own_root = os.path.join(base, "own-copy-foreign")
        os.makedirs(own_root)
        _git(["init", "-q"], cwd=own_root)
        _git(["config", "user.email", "t@example.com"], cwd=own_root)
        _git(["config", "user.name", "t"], cwd=own_root)
        with open(os.path.join(own_root, ".gitkeep"), "w", encoding="utf-8") as f:
            f.write("x\n")
        _git(["add", "-A"], cwd=own_root)
        _git(["commit", "-q", "-m", "init"], cwd=own_root)
    state = os.path.join(base, "state")
    briefs = os.path.join(state, "briefs")
    os.makedirs(briefs)
    with open(os.path.join(briefs, "agent-%s.json" % AGENT), "w", encoding="utf-8") as f:
        json.dump({"role": "executor", "card": CARD, "phase": PHASE}, f)
    return work_root, state, card_dir, shared_root, own_root


def shell_write_boundary_cases(base_env, base):
    """Exercise shell-write boundary cases in a real linked worktree."""
    work_root, state, card_dir, shared_root, own_root = build_boundary_repo(
        os.path.join(base, "shellwrite"))
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state
    env["WORK_GATE_CARD_WORKTREE_ROOT"] = own_root
    env["WORK_GATE_SHELL_CWD"] = shared_root

    failures = 0

    def probe(title, command, wanted, must_carry=None, must_not_carry=None):
        got, reason = decide(env, "Bash", {"command": command})
        reason = reason or ""
        ok = got == wanted
        if ok and must_carry:
            ok = all(s in reason for s in must_carry)
        if ok and must_not_carry:
            ok = all(s not in reason for s in must_not_carry)
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + str(got))
        if not ok:
            print("        expected " + wanted + "; reason: " + reason[:400])
        return 0 if ok else 1

    # A.7: all six redirection spellings, relative target, no `cd` — each denied, each
    # naming "output redirection" as the caught form.
    for op in (">", ">>", ">|", "2>", "2>>", "&>"):
        failures += probe(
            "redirection %r into shared checkout is refused" % op,
            "echo hi %s runtime/src/lib.rs" % op, "deny",
            must_carry=["WORKING COPY BOUNDARY", "Caught by: output redirection"])

    # Check a heredoc with an output redirection.
    failures += probe(
        "heredoc output redirection is refused",
        "cat > runtime/src/lib.rs <<'EOF'\nbody\nEOF", "deny",
        must_carry=["Caught by: output redirection"])

    # tee on the right-hand side of a pipeline.
    failures += probe(
        "tee on the right side of a pipeline is refused",
        "echo hi | tee runtime/src/lib.rs", "deny",
        must_carry=["Caught by: tee"])

    # cp / mv destination, plain and via -t/--target-directory.
    failures += probe(
        "cp destination is refused",
        "cp /tmp/a.txt runtime/src/lib.rs", "deny",
        must_carry=["Caught by: cp/mv destination"])
    failures += probe(
        "mv destination is refused",
        "mv /tmp/a.txt runtime/src/lib.rs", "deny",
        must_carry=["Caught by: cp/mv destination"])
    failures += probe(
        "cp target-directory option is refused",
        "cp -t runtime/src /tmp/a.txt", "deny",
        must_carry=["Caught by: cp/mv destination"])

    # sed -i.
    failures += probe(
        "sed -i edit in shared checkout is refused",
        "sed -i 's/a/b/' runtime/src/lib.rs", "deny",
        must_carry=["Caught by: sed -i"])

    # Three exceptions: own working copy, the card's own folder, outside the shared checkout.
    failures += probe(
        "write in the card's own worktree passes",
        "cd %s && echo hi > runtime/src/lib.rs" % own_root, "allow")
    failures += probe(
        "write in the card folder passes",
        "echo hi > %s" % os.path.join(card_dir, "question.md"), "allow")
    failures += probe(
        "write outside the shared checkout passes",
        "echo hi > /tmp/synthetic-outside-probe.txt", "allow")

    # Relative target: without cd (denied above), after a literal cd into the own copy
    # (allowed above), after cd to a non-literal value (unresolved, skipped).
    failures += probe(
        "relative target after non-literal directory change is skipped",
        'cd "$SOME_VAR" && echo hi > runtime/src/lib.rs', "allow")

    # A quoted destination is still caught, and the denial carries no quote characters
    # around the path it names.
    got, reason = decide(env, "Bash", {"command": 'echo hi > "runtime/src/lib.rs"'})
    ok = got == "deny" and '"runtime/src/lib.rs"' not in (reason or "") and \
        "runtime/src/lib.rs" in (reason or "")
    print(("  ok   " if ok else "  FAIL ") +
          "quoted destination is refused without quotes in the reason")
    if not ok:
        print("        decision: %s; reason: %s" % (got, (reason or "")[:300]))
    failures += 0 if ok else 1

    # A `>` sitting inside a quoted argument is not a redirection at all.
    failures += probe(
        "redirection inside quotes is not a command redirection",
        'echo "a > b"', "allow")

    # A.8: the list of checked forms printed in the denial names exactly the four forms of
    # SHELL_WRITE_FORM_TABLE, and nothing else.
    got, reason = decide(env, "Bash", {"command": "echo hi > runtime/src/lib.rs"})
    reason = reason or ""
    table_forms = ["output redirection", "tee", "cp/mv destination", "sed -i"]
    ok = got == "deny" and all(name in reason for name in table_forms)
    print(("  ok   " if ok else "  FAIL ") +
          "denial lists the same write forms as the policy table")
    if not ok:
        print("        reason: " + reason[:600])
    failures += 0 if ok else 1

    # A.8: rule 6c's own denial and rule 6a's own denial, for the same target path, are
    # built by the same function — their base text (everything before the shell-only
    # "Caught by" line) matches exactly, in the same-repository layout this fixture builds.
    target_fp = os.path.join(shared_root, "runtime", "src", "lib.rs")
    shell_got, shell_reason = decide(env, "Bash", {"command": "echo hi > runtime/src/lib.rs"})
    write_got, write_reason = decide(env, "Write", {"file_path": target_fp, "content": "x"})
    shell_base = (shell_reason or "").split("\nCaught by:")[0]
    write_base = (write_reason or "").split("\n" + SHELL_SCOPE_NOTE_MARKER)[0] \
        if SHELL_SCOPE_NOTE_MARKER in (write_reason or "") else (write_reason or "")
    ok = (shell_got == "deny" and write_got == "deny" and shell_base == write_base)
    print(("  ok   " if ok else "  FAIL ") +
          "shell and direct-write denial text match for the same path")
    if not ok:
        print("        shell:  " + (shell_reason or "")[:400])
        print("        write:  " + (write_reason or "")[:400])
    failures += 0 if ok else 1

    return failures


def shell_write_boundary_cross_repository_cases(base_env, base):
    """The same comparison as above, in the cross-repository layout: the card's own working
    copy is a wholly separate repository, so same_repository() answers False and both rules
    must fall back to CROSS_REPOSITORY_BOUNDARY_TEMPLATE, with no address substituted."""
    work_root, state, card_dir, shared_root, own_root = build_boundary_repo(
        os.path.join(base, "shellwrite-cross"), linked=False)
    env = dict(base_env)
    env["WORK_GATE_WORK_ROOT"] = work_root
    env["WORK_GATE_STATE_DIR"] = state
    env["WORK_GATE_CARD_WORKTREE_ROOT"] = own_root
    env["WORK_GATE_SHELL_CWD"] = shared_root

    failures = 0
    target_fp = os.path.join(shared_root, "runtime", "src", "lib.rs")
    shell_got, shell_reason = decide(env, "Bash", {"command": "echo hi > runtime/src/lib.rs"})
    write_got, write_reason = decide(env, "Write", {"file_path": target_fp, "content": "x"})
    ok = (shell_got == "deny" and write_got == "deny" and
          "not confirmed to be the same repository" in (shell_reason or "") and
          "not confirmed to be the same repository" in (write_reason or ""))
    print(("  ok   " if ok else "  FAIL ") +
          "separate repositories: neither denial substitutes a destination")
    if not ok:
        print("        shell:  " + (shell_reason or "")[:400])
        print("        write:  " + (write_reason or "")[:400])
    failures += 0 if ok else 1

    shell_base = (shell_reason or "").split("\nCaught by:")[0]
    write_base = (write_reason or "").split("\n" + SHELL_SCOPE_NOTE_MARKER)[0] \
        if SHELL_SCOPE_NOTE_MARKER in (write_reason or "") else (write_reason or "")
    ok2 = shell_base == write_base
    print(("  ok   " if ok2 else "  FAIL ") +
          "separate repositories: the base denial text also matches")
    if not ok2:
        print("        shell:  " + (shell_reason or "")[:400])
        print("        write:  " + (write_reason or "")[:400])
    failures += 0 if ok2 else 1
    return failures


def scope_cases(base_env, base):
    """Rule 1b: the gate governs only the repository that carries the work-management
    system — an ai/ directory holding both card kinds as real directories of its own."""
    print("\nScope behavior:")
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
        ("repository with both card directories is in scope",
         make_repo("scope-app", ("harness", "timeline")), None, "deny"),
        ("repository without card directories is out of scope",
         make_repo("scope-plain", ()), None, "allow"),
        ("repository with only one card directory is out of scope",
         make_repo("scope-half", ("harness",)), None, "allow"),
        ("symlink is not accepted as a real card directory",
         make_repo("scope-link", ("harness", "timeline"), symlink=True), None, "allow"),
        ("WORK_GATE_SCOPE=off disables the gate in a matching repository",
         make_repo("scope-app2", ("harness", "timeline")), {"WORK_GATE_SCOPE": "off"}, "allow"),
        ("WORK_GATE_SCOPE=on enables the gate in another repository",
         make_repo("scope-plain2", ()), {"WORK_GATE_SCOPE": "on"}, "deny"),
    ]
    for title, repo, extra, expected in checks:
        got = decide_in(repo, extra)
        ok = got == expected
        failures += 0 if ok else 1
        print(("  ok   " if ok else "  FAIL ") + title + "  → " + got)
        if not ok:
            print("        expected " + expected)
    return failures


def main():
    base = tempfile.mkdtemp(prefix="gate-boundary-")
    env = dict(os.environ)
    work_config = os.path.join(base, "private-config.json")
    with open(work_config, "w", encoding="utf-8") as config_file:
        json.dump({"work_management": {"enabled": True}}, config_file)
    env["AI_TOOLKIT_CONFIG"] = work_config
    env.pop("CLAUDE_GATE_BYPASS", None)
    env.pop("CLAUDE_HARNESS_BYPASS", None)
    # Every case below exercises a RULE, not the scope question rule 1b answers, and the
    # fixture trees these cases build are not the application's own checkout, so the scope
    # rule would switch the gate off before any rule under test ever ran. Forced on here;
    # scope_cases() below is what actually tests rule 1b.
    env["WORK_GATE_SCOPE"] = "on"

    failures = 0

    print("\nCommand reference:")
    failures += reference_cases(env, base)

    print("\nLog-write ceiling:")
    failures += ceiling_cases(env, base)

    print("\nRepeated search of one file:")
    failures += search_cases(env, base)

    print("\nChained state-recording calls:")
    failures += chain_cases(env, base)

    print("\nQuoted brief command does not overwrite a brief:")
    failures += brief_quote_cases(env, base)

    print("\nBrief command forms:")
    failures += brief_real_call_cases(env, base)

    print("\nQuoted command name does not reset the log ceiling:")
    failures += quoted_log_name_no_reset_cases(env, base)

    print("\nQuoted command name does not trigger chained-call refusal:")
    failures += quoted_log_name_no_chain_refusal_cases(env, base)

    print("\nContext ceiling and recovery calls:")
    failures += context_ceiling_cases(env, base)

    print("\nExecutor spawn sanctions:")
    failures += sanction_cases(env, base)
    failures += scope_cases(env, base)

    print("\nShell-write boundary:")
    failures += shell_write_boundary_cases(env, base)
    failures += shell_write_boundary_cross_repository_cases(env, base)

    print("\n%d cases failed" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
