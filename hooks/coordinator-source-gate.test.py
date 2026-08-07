#!/usr/bin/env python3
"""coordinator-source-gate.test.py — the test suite for coordinator-source-gate.sh.

Built for ai/harness/tasks/HRN-117_the-coordinator-cannot-edit-product-source-code-with-
its-own-hand-because-only-an-executor-may.md in the app repository (Dev/app). Read that
card for the full "why" this hook exists; this file only proves that the hook script it
is run against actually behaves the way that card's acceptance criteria describe.

Usage:
    python3 coordinator-source-gate.test.py [path-to-hook-script]

With no argument, the hook script tested is the one sitting next to this file —
candidates/coordinator-source-gate.sh — which is how the card's own gate line runs it:

    python3 candidates/coordinator-source-gate.test.py candidates/coordinator-source-gate.sh

With an argument, that path is tested instead. This is what lets bin/hook-install prove a
candidate against this same suite before installing it (it invokes this file as
`python3 <this-file> <candidate>`), and what lets this suite equally be pointed at the
live hook once installed, without a second copy of itself.

Each test feeds one JSON payload to the hook's own standard input, exactly the shape a
real PreToolUse hook call carries, and reads back the one line of JSON the hook prints —
a hookSpecificOutput object whose permissionDecision is either "allow" or "deny". Exit
code 0 means every test passed; a non-zero exit prints which test failed and why, and is
what makes bin/hook-install refuse to install a candidate that regresses any of this.
"""
import json
import os
import subprocess
import sys

if len(sys.argv) > 1:
    HOOK_PATH = sys.argv[1]
else:
    HOOK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "coordinator-source-gate.sh")

if not os.path.isfile(HOOK_PATH):
    print("coordinator-source-gate.test.py: no such hook script: %s" % HOOK_PATH)
    sys.exit(1)

FAILURES = []
RUN = [0]


def run_hook(payload, env_overrides=None, raw_stdin=None):
    """Runs the hook script once, feeding it `raw_stdin` verbatim if given, or the JSON
    encoding of `payload` otherwise. Returns (returncode, stdout, stderr). env_overrides
    is applied on top of a copy of this process's own environment, with
    CLAUDE_GATE_BYPASS always removed first so a bypass left set in the ambient
    environment can never leak into a test that did not ask for it."""
    env = dict(os.environ)
    env.pop("CLAUDE_GATE_BYPASS", None)
    if env_overrides:
        env.update(env_overrides)
    stdin_data = raw_stdin if raw_stdin is not None else json.dumps(payload)
    proc = subprocess.run(
        ["bash", HOOK_PATH],
        input=stdin_data,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    return proc.returncode, proc.stdout, proc.stderr


def decision_of(stdout):
    """Parses the hook's one line of JSON output and returns the permissionDecision
    string, or raises AssertionError with the raw output if it is not shaped that way —
    every call this hook makes must end in a real decision, never silence or a stray
    traceback on stdout."""
    line = stdout.strip()
    assert line, "hook printed nothing on stdout"
    try:
        obj = json.loads(line)
    except Exception as exc:
        raise AssertionError("hook stdout is not valid JSON: %r (%s)" % (line, exc))
    try:
        return obj["hookSpecificOutput"]["permissionDecision"]
    except Exception:
        raise AssertionError("hook stdout has no permissionDecision: %r" % (obj,))


def reason_of(stdout):
    obj = json.loads(stdout.strip())
    return obj["hookSpecificOutput"].get("permissionDecisionReason", "")


def check(name, fn):
    """Runs one test function, recording a pass or a failure. A test function raises
    AssertionError (or lets one propagate from decision_of) to fail; returning normally
    is a pass."""
    RUN[0] += 1
    try:
        fn()
        print("ok   - %s" % name)
    except AssertionError as exc:
        print("FAIL - %s: %s" % (name, exc))
        FAILURES.append(name)
    except Exception as exc:
        print("FAIL - %s: unexpected %s: %s" % (name, type(exc).__name__, exc))
        FAILURES.append(name)


def edit(path):
    return {"tool_name": "Edit", "tool_input": {"file_path": path}}


def write(path):
    return {"tool_name": "Write", "tool_input": {"file_path": path}}


def notebook_edit(path):
    return {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": path}}


def as_executor(payload, agent_id="test-agent-0001"):
    out = dict(payload)
    out["agent_id"] = agent_id
    return out


# ---------------------------------------------------------------------------
# HRN-117.1 — the coordinator's own Edit/Write/NotebookEdit of a guarded path is refused,
# naming the path and the alternative.
# ---------------------------------------------------------------------------

def test_deny_edit_backend():
    rc, out, err = run_hook(edit("/Users/laptop/Dev/app/dpp_demo/app/internal/bom/bom.go"))
    assert decision_of(out) == "deny", "expected deny, got stdout=%r stderr=%r" % (out, err)


def test_deny_write_backend():
    rc, out, err = run_hook(write("/Users/laptop/Dev/app/dpp_demo/app/main.go"))
    assert decision_of(out) == "deny"


def test_deny_write_frontend_src():
    rc, out, err = run_hook(write("/Users/laptop/Dev/app/dpp_frontend/src/vendor/qrcode.js"))
    assert decision_of(out) == "deny"


def test_deny_edit_vldt_src():
    rc, out, err = run_hook(edit("/Users/laptop/Dev/app/dpp-vldt/src/App.vue"))
    assert decision_of(out) == "deny"


def test_deny_notebookedit_backend():
    rc, out, err = run_hook(notebook_edit("/Users/laptop/Dev/app/dpp_demo/app/scratch.ipynb"))
    assert decision_of(out) == "deny"


def test_deny_reason_names_path_and_alternative():
    path = "/Users/laptop/Dev/app/dpp_demo/app/internal/bom/bom.go"
    rc, out, err = run_hook(edit(path))
    assert decision_of(out) == "deny"
    reason = reason_of(out)
    assert path in reason, "reason does not name the refused path: %r" % (reason,)
    assert "executor" in reason.lower(), \
        "reason does not name the alternative (hand it to an executor): %r" % (reason,)
    # One full sentence — acceptance criterion 2 — so it must at least end the way a
    # sentence does, not trail off as a bare fragment.
    assert reason.strip().endswith("."), "reason does not read as a full sentence: %r" % (reason,)


def test_deny_relative_guarded_path():
    # A relative path already naming a guarded directory from the repository root, with
    # no leading slash at all, must be caught the same way an absolute one is.
    rc, out, err = run_hook(edit("dpp_demo/app/main.go"))
    assert decision_of(out) == "deny"


def test_deny_guarded_path_inside_a_linked_worktree():
    # The coordinator's own copy of the repository can itself be a linked worktree cut
    # under .claude/worktrees/ (per EnterWorktree); the guarded directories must still be
    # recognised however much checkout-specific prefix comes before them.
    path = "/Users/laptop/Dev/app/.claude/worktrees/some-session/dpp_demo/app/main.go"
    rc, out, err = run_hook(edit(path))
    assert decision_of(out) == "deny"


# ---------------------------------------------------------------------------
# HRN-117.2 — an executor's call passes untouched, and every path outside the three
# directories passes for the coordinator too.
# ---------------------------------------------------------------------------

def test_allow_executor_on_guarded_backend_path():
    payload = as_executor(edit("/Users/laptop/Dev/app/dpp_demo/app/internal/bom/bom.go"))
    rc, out, err = run_hook(payload)
    assert decision_of(out) == "allow"


def test_allow_executor_on_guarded_frontend_path():
    payload = as_executor(write("/Users/laptop/Dev/app/dpp_frontend/src/main.ts"))
    rc, out, err = run_hook(payload)
    assert decision_of(out) == "allow"


def test_allow_executor_notebookedit_guarded_path():
    payload = as_executor(notebook_edit("/Users/laptop/Dev/app/dpp-vldt/src/scratch.ipynb"))
    rc, out, err = run_hook(payload)
    assert decision_of(out) == "allow"


def test_allow_coordinator_task_card():
    rc, out, err = run_hook(edit(
        "/Users/laptop/Dev/app/ai/harness/tasks/HRN-117_the-coordinator-cannot-edit.md"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_epic():
    rc, out, err = run_hook(edit("/Users/laptop/Dev/app/ai/timeline/epics/EPIC-1.md"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_feature_page():
    rc, out, err = run_hook(write("/Users/laptop/Dev/app/kb/features/FEAT-05.md"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_anywhere_under_ai():
    rc, out, err = run_hook(edit("/Users/laptop/Dev/app/ai/decisions/some-subject.md"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_anywhere_under_kb():
    rc, out, err = run_hook(edit("/Users/laptop/Dev/app/kb/domain/composition.md"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_anywhere_under_bin():
    rc, out, err = run_hook(write("/Users/laptop/Dev/app/bin/stage-report"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_anywhere_under_githooks():
    rc, out, err = run_hook(write("/Users/laptop/Dev/app/.githooks/pre-commit"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_hooks_directory_itself():
    rc, out, err = run_hook(edit("/Users/laptop/Dev/ai/hooks/README.md"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_frontend_build_output():
    # dpp_frontend/dist is generated output, not the frontend's own source under src/, and
    # this hook is deliberately scoped only to src/ for both frontends.
    rc, out, err = run_hook(edit("/Users/laptop/Dev/app/dpp_frontend/dist/index.html"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_frontend_root_config():
    # A file directly under dpp_frontend/ but outside its src/ subdirectory (a config
    # file at the package root, for instance) is likewise out of this hook's scope.
    rc, out, err = run_hook(edit("/Users/laptop/Dev/app/dpp_frontend/vite.config.ts"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_other_project_entirely():
    # A session working in a project that never names any of the three guarded
    # directories at all must be completely unaffected (acceptance criterion 5).
    rc, out, err = run_hook(edit("/Users/laptop/Dev/other-project/src/main.py"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_lookalike_directory_not_a_real_segment_match():
    # dpp_demo/appendix is not dpp_demo/app: the marker must match a whole path segment,
    # never a bare string prefix that happens to share the same letters.
    rc, out, err = run_hook(edit("/Users/laptop/Dev/app/dpp_demo/appendix/notes.md"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_lookalike_src_suffix_not_a_real_segment_match():
    rc, out, err = run_hook(edit("/Users/laptop/Dev/app/dpp-vldt/srcfoo/bar.js"))
    assert decision_of(out) == "allow"


def test_allow_coordinator_non_gated_tool_on_guarded_path():
    # Only Edit, Write and NotebookEdit are gated at all; a Bash call naming the same
    # guarded path in its command text is not this hook's concern.
    payload = {"tool_name": "Bash",
               "tool_input": {"command": "cat /Users/laptop/Dev/app/dpp_demo/app/main.go"}}
    rc, out, err = run_hook(payload)
    assert decision_of(out) == "allow"


def test_allow_coordinator_read_on_guarded_path():
    payload = {"tool_name": "Read",
               "tool_input": {"file_path": "/Users/laptop/Dev/app/dpp_demo/app/main.go"}}
    rc, out, err = run_hook(payload)
    assert decision_of(out) == "allow"


# ---------------------------------------------------------------------------
# HRN-117.3 — the named override, and fail-open on any internal error.
# ---------------------------------------------------------------------------

def test_bypass_env_var_allows_guarded_edit():
    rc, out, err = run_hook(
        edit("/Users/laptop/Dev/app/dpp_demo/app/main.go"),
        env_overrides={"CLAUDE_GATE_BYPASS": "1"},
    )
    assert decision_of(out) == "allow"


def test_bypass_env_var_wrong_value_still_denies():
    # The override must be taken deliberately (the exact value "1"), never by the mere
    # presence of the variable, so a stray CLAUDE_GATE_BYPASS=0 or =true left in an
    # environment cannot silently punch a hole.
    rc, out, err = run_hook(
        edit("/Users/laptop/Dev/app/dpp_demo/app/main.go"),
        env_overrides={"CLAUDE_GATE_BYPASS": "true"},
    )
    assert decision_of(out) == "deny"


def test_fail_open_on_empty_stdin():
    rc, out, err = run_hook(None, raw_stdin="")
    assert decision_of(out) == "allow"


def test_fail_open_on_malformed_json():
    rc, out, err = run_hook(None, raw_stdin="this is not json at all {")
    assert decision_of(out) == "allow"


def test_fail_open_on_missing_tool_input():
    rc, out, err = run_hook({"tool_name": "Edit"})
    assert decision_of(out) == "allow"


def test_fail_open_on_null_tool_input():
    rc, out, err = run_hook({"tool_name": "Edit", "tool_input": None})
    assert decision_of(out) == "allow"


def test_fail_open_on_missing_file_path_key():
    rc, out, err = run_hook({"tool_name": "Write", "tool_input": {"content": "x"}})
    assert decision_of(out) == "allow"


def test_hook_never_crashes_the_shell_wrapper():
    # Whatever the payload, the wrapper always exits 0 and always prints exactly one
    # decision line — a PreToolUse hook that exits non-zero or prints nothing is read as
    # a refusal by the harness, which this hook must never cause by accident.
    for raw in ("", "{}", "null", "[1,2,3]", '{"tool_name": 5}', "{\"tool_input\": 9}"):
        rc, out, err = run_hook(None, raw_stdin=raw)
        assert rc == 0, "hook exited %r for input %r (stderr=%r)" % (rc, raw, err)
        decision_of(out)  # raises if this is not a real decision


# ---------------------------------------------------------------------------

TESTS = [
    test_deny_edit_backend,
    test_deny_write_backend,
    test_deny_write_frontend_src,
    test_deny_edit_vldt_src,
    test_deny_notebookedit_backend,
    test_deny_reason_names_path_and_alternative,
    test_deny_relative_guarded_path,
    test_deny_guarded_path_inside_a_linked_worktree,
    test_allow_executor_on_guarded_backend_path,
    test_allow_executor_on_guarded_frontend_path,
    test_allow_executor_notebookedit_guarded_path,
    test_allow_coordinator_task_card,
    test_allow_coordinator_epic,
    test_allow_coordinator_feature_page,
    test_allow_coordinator_anywhere_under_ai,
    test_allow_coordinator_anywhere_under_kb,
    test_allow_coordinator_anywhere_under_bin,
    test_allow_coordinator_anywhere_under_githooks,
    test_allow_coordinator_hooks_directory_itself,
    test_allow_coordinator_frontend_build_output,
    test_allow_coordinator_frontend_root_config,
    test_allow_coordinator_other_project_entirely,
    test_allow_coordinator_lookalike_directory_not_a_real_segment_match,
    test_allow_coordinator_lookalike_src_suffix_not_a_real_segment_match,
    test_allow_coordinator_non_gated_tool_on_guarded_path,
    test_allow_coordinator_read_on_guarded_path,
    test_bypass_env_var_allows_guarded_edit,
    test_bypass_env_var_wrong_value_still_denies,
    test_fail_open_on_empty_stdin,
    test_fail_open_on_malformed_json,
    test_fail_open_on_missing_tool_input,
    test_fail_open_on_null_tool_input,
    test_fail_open_on_missing_file_path_key,
    test_hook_never_crashes_the_shell_wrapper,
]

if __name__ == "__main__":
    print("coordinator-source-gate.test.py: testing %s" % HOOK_PATH)
    for t in TESTS:
        check(t.__name__, t)
    print("")
    print("%d/%d passed" % (RUN[0] - len(FAILURES), RUN[0]))
    if FAILURES:
        print("FAILED: %s" % ", ".join(FAILURES))
        sys.exit(1)
    sys.exit(0)
