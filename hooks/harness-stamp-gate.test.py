#!/usr/bin/env python3
"""Test harness for the HRN-155 candidate of hooks/harness-stamp-gate.sh.

Founded directly under hooks/ rather than assembled as a candidate first, exactly as
hooks/README.md and bin/hook-install's own fifth refusal require: bin/hook-install refuses
to install a hook that has no test suite already sitting at hooks/<name>.test.py, so the
suite itself has to exist here before the rewritten hook can ever be installed through that
script. This is the one founding write HRN-155 names explicitly (checkpoint HRN-155.3);
every later change to either file goes back through bin/hook-install as usual.

HRN-155 replaces the pre-existing HARNESS_VERSION-vs-stamp comparison with one taken from a
SHA-256 digest of the rendered settings.json.template, so this suite never touches the real
checkout's own settings.json.template or the real ~/.claude/.harness-stamp: every scenario
below builds a scratch checkout directory (fixture_repo()) holding its own
settings.json.template and points the hook at it with HARNESS_STAMP_GATE_REPO_DIR, and a
scratch stamp file pointed to with HARNESS_STAMP_GATE_STAMP_FILE — both env-var overrides
the candidate under test reads for exactly this purpose (see its own header).

Run directly: python3 /Users/laptop/Dev/ai/hooks/harness-stamp-gate.test.py [candidate-path]
With no argument this runs against the installed hook at
/Users/laptop/Dev/ai/hooks/harness-stamp-gate.sh; given one argument it runs against that
file instead, which is what bin/hook-install uses to test a candidate before installing it.
Exit code 0 when every check passes, 1 when any fails (own PASS/FAIL harness, matching the
sibling *.test.py files in this directory rather than unittest).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else "/Users/laptop/Dev/ai/hooks/harness-stamp-gate.sh"

fails = 0


def fixture_repo(template_bytes):
    """A scratch checkout directory holding only settings.json.template, with the given
    bytes, and a bootstrap.sh present (its content is never read by the hook — only its
    path is named in a denial message — but the hook constructs that path unconditionally,
    so a real file there keeps a reader of the denial from being pointed at nothing)."""
    root = tempfile.mkdtemp(prefix="harness-stamp-gate-repo-")
    with open(os.path.join(root, "settings.json.template"), "wb") as f:
        f.write(template_bytes)
    with open(os.path.join(root, "bootstrap.sh"), "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env bash\necho stub\n")
    return root


def expected_digest(template_bytes, home):
    """The suite's OWN, independent re-implementation of the byte transformation
    bootstrap.sh performs — used only by scenarios that need to construct a KNOWN-CORRECT
    stamp without depending on the candidate's own computation of it. See
    real_bootstrap_digest() below for the separate, stronger proof that this transformation
    genuinely matches the real `sed`/`shasum` pipeline bootstrap.sh runs, rather than merely
    agreeing with itself."""
    rendered = template_bytes.replace(b"__HOME__", home.encode("utf-8"))
    rendered = rendered.rstrip(b"\n") + b"\n"
    return hashlib.sha256(rendered).hexdigest()


def real_bootstrap_digest(template_path, home):
    """Reproduces bootstrap.sh's own pipeline using the REAL `sed` and `shasum` binaries —
    the same tools and the same commands bootstrap.sh itself runs — rather than Python
    string methods, so a scenario using this helper proves the candidate's internal
    re-implementation of that pipeline agrees with the actual pipeline byte for byte, not
    merely with a second Python re-implementation of itself."""
    sed_out = subprocess.run(["sed", "s|__HOME__|%s|g" % home, template_path],
                              capture_output=True).stdout
    # A $(...) capture in bootstrap.sh strips every trailing newline from sed's output;
    # bootstrap.sh's own `printf '%s\n' "$rendered"` then adds exactly one back.
    rendered = sed_out.rstrip(b"\n") + b"\n"
    digest_out = subprocess.run(["shasum", "-a", "256"], input=rendered,
                                 capture_output=True).stdout
    return digest_out.decode().split()[0]


def call(tool_name, tool_input, repo_dir=None, stamp_file=None, extra_env=None):
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    env = dict(os.environ)
    if repo_dir is not None:
        env["HARNESS_STAMP_GATE_REPO_DIR"] = repo_dir
    else:
        env.pop("HARNESS_STAMP_GATE_REPO_DIR", None)
    if stamp_file is not None:
        env["HARNESS_STAMP_GATE_STAMP_FILE"] = stamp_file
    else:
        env.pop("HARNESS_STAMP_GATE_STAMP_FILE", None)
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(["bash", HOOK], input=json.dumps(payload),
                        capture_output=True, text=True, env=env)
    try:
        out = json.loads(r.stdout)["hookSpecificOutput"]
        return out["permissionDecision"], out.get("permissionDecisionReason")
    except Exception:
        return "PARSE_FAIL(" + r.stdout[:200] + ")", None


def check(expected, label, tool_name, tool_input, repo_dir=None, stamp_file=None,
          extra_env=None, reason_contains=None):
    global fails
    decision, reason = call(tool_name, tool_input, repo_dir=repo_dir, stamp_file=stamp_file,
                             extra_env=extra_env)
    ok = decision == expected
    if ok and reason_contains is not None:
        ok = bool(reason) and reason_contains in reason
    fails += 0 if ok else 1
    detail = "" if ok else f"  (expected {expected}, got {decision}, reason={reason!r})"
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{detail}")


HOME = os.path.expanduser("~")
TEMPLATE = (b'{\n  "_comment": "TEMPLATE",\n  "hooks": {"PreToolUse": []},\n'
            b'  "path": "__HOME__/Dev/ai"\n}\n')

try:
    # --- a matching stamp: allow, silently ---
    repo = fixture_repo(TEMPLATE)
    stamp_path = os.path.join(tempfile.mkdtemp(prefix="harness-stamp-gate-stamp-"), "stamp")
    try:
        digest = expected_digest(TEMPLATE, HOME)
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write(digest + "\n")
        check("allow", "matching stamp allows an ordinary Bash call, silently",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path)
        decision, reason = call("Bash", {"command": "echo hi"}, repo_dir=repo,
                                 stamp_file=stamp_path)
        ok = decision == "allow" and reason is None
        fails += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  matching stamp carries no reason at all"
              f"{'' if ok else f'  (reason={reason!r})'}")
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(os.path.dirname(stamp_path), ignore_errors=True)

    # --- a differing stamp: deny an ordinary call, naming the deploy command ---
    repo = fixture_repo(TEMPLATE)
    stamp_dir = tempfile.mkdtemp(prefix="harness-stamp-gate-stamp-")
    stamp_path = os.path.join(stamp_dir, "stamp")
    try:
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write("0" * 64 + "\n")
        check("deny", "a stamp holding a different digest denies an ordinary Bash call",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path,
              reason_contains="harness-stamp-gate")
        check("deny", "the refusal names the deploy command",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path,
              reason_contains=os.path.join(repo, "bootstrap.sh"))
        check("deny", "the refusal names the CLAUDE_HARNESS_BYPASS escape",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path,
              reason_contains="CLAUDE_HARNESS_BYPASS=1")
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(stamp_dir, ignore_errors=True)

    # --- a missing stamp: deny, naming that this machine has never been deployed at all ---
    repo = fixture_repo(TEMPLATE)
    stamp_dir = tempfile.mkdtemp(prefix="harness-stamp-gate-stamp-")
    stamp_path = os.path.join(stamp_dir, "stamp-that-does-not-exist")
    try:
        check("deny", "a missing stamp file denies an ordinary Bash call",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path,
              reason_contains="no harness stamp at all")
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(stamp_dir, ignore_errors=True)

    # --- an unreadable template: allow every call — this mechanism is simply not in use
    # here, which AC4 says is never the same thing as being stale ---
    repo_dir_missing = tempfile.mkdtemp(prefix="harness-stamp-gate-no-template-")
    stamp_dir = tempfile.mkdtemp(prefix="harness-stamp-gate-stamp-")
    stamp_path = os.path.join(stamp_dir, "stamp")
    try:
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write("0" * 64 + "\n")
        check("allow", "no settings.json.template at all in the checkout allows, even "
                       "with a stamp file present that would otherwise mismatch",
              "Bash", {"command": "echo hi"}, repo_dir=repo_dir_missing,
              stamp_file=stamp_path)
    finally:
        shutil.rmtree(repo_dir_missing, ignore_errors=True)
        shutil.rmtree(stamp_dir, ignore_errors=True)

    # --- the read-only allowances still get through while the stamp mismatches ---
    repo = fixture_repo(TEMPLATE)
    stamp_dir = tempfile.mkdtemp(prefix="harness-stamp-gate-stamp-")
    stamp_path = os.path.join(stamp_dir, "stamp")
    try:
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write("0" * 64 + "\n")
        for tool in ("Read", "Glob", "Grep", "NotebookRead", "TodoWrite"):
            check("allow", f"{tool} is allowed through a mismatched stamp",
                  tool, {"file_path": "/tmp/whatever"}, repo_dir=repo, stamp_file=stamp_path)
        check("deny", "a non-read-only tool (Edit) is still denied under the same "
                      "mismatch", "Edit", {"file_path": "/tmp/whatever"}, repo_dir=repo,
              stamp_file=stamp_path)
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(stamp_dir, ignore_errors=True)

    # --- the bootstrap.sh escape: a Bash call naming bootstrap.sh gets through a
    # mismatched stamp; an unrelated Bash call does not ---
    repo = fixture_repo(TEMPLATE)
    stamp_dir = tempfile.mkdtemp(prefix="harness-stamp-gate-stamp-")
    stamp_path = os.path.join(stamp_dir, "stamp")
    try:
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write("0" * 64 + "\n")
        check("allow", "a Bash call running bootstrap.sh is let through a mismatched stamp",
              "Bash", {"command": "~/Dev/ai/bootstrap.sh"}, repo_dir=repo,
              stamp_file=stamp_path)
        check("deny", "an unrelated Bash call is still denied under the same mismatch",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path)
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(stamp_dir, ignore_errors=True)

    # --- CLAUDE_HARNESS_BYPASS=1 always allows, even with a missing template and a
    # mismatched stamp ---
    repo = fixture_repo(TEMPLATE)
    stamp_dir = tempfile.mkdtemp(prefix="harness-stamp-gate-stamp-")
    stamp_path = os.path.join(stamp_dir, "stamp")
    try:
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write("0" * 64 + "\n")
        check("deny", "confirm this scenario is genuinely refused without the bypass",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path)
        check("allow", "CLAUDE_HARNESS_BYPASS=1 overrides that exact same refusal",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path,
              extra_env={"CLAUDE_HARNESS_BYPASS": "1"})
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(stamp_dir, ignore_errors=True)

    # --- byte-for-byte agreement of the two digests: a stamp built with the REAL `sed`
    # and `shasum` binaries — bootstrap.sh's own tools, not this suite's Python
    # re-implementation of them — is accepted by the candidate's own (Python) digest
    # computation, proving the two genuinely produce the same bytes rather than each
    # merely agreeing with itself ---
    repo = fixture_repo(TEMPLATE)
    stamp_dir = tempfile.mkdtemp(prefix="harness-stamp-gate-stamp-")
    stamp_path = os.path.join(stamp_dir, "stamp")
    try:
        real_digest = real_bootstrap_digest(
            os.path.join(repo, "settings.json.template"), HOME)
        python_digest = expected_digest(TEMPLATE, HOME)
        ok = real_digest == python_digest
        fails += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  the suite's own two independent digest "
              f"computations (real sed/shasum vs. Python re-implementation) agree"
              f"{'' if ok else f'  (real={real_digest!r}, python={python_digest!r})'}")
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write(real_digest + "\n")
        check("allow", "a stamp built from the real sed/shasum pipeline is accepted by "
                       "the candidate's own digest computation",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path)
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(stamp_dir, ignore_errors=True)

    # --- changing one character in the template makes a previously-matching stamp
    # mismatch, and the refusal names the deploy command; re-deriving the stamp from the
    # changed template makes the same call pass again (AC3, end to end) ---
    repo = fixture_repo(TEMPLATE)
    stamp_dir = tempfile.mkdtemp(prefix="harness-stamp-gate-stamp-")
    stamp_path = os.path.join(stamp_dir, "stamp")
    template_path = os.path.join(repo, "settings.json.template")
    try:
        digest_before = expected_digest(TEMPLATE, HOME)
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write(digest_before + "\n")
        check("allow", "the stamp matches the unchanged template", "Bash",
              {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path)

        changed = TEMPLATE.replace(b'"path"', b'"paths"')
        with open(template_path, "wb") as f:
            f.write(changed)
        check("deny", "changing one character in the template makes the old stamp "
                      "mismatch and refuses the very same call",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path,
              reason_contains="bootstrap.sh")

        digest_after = expected_digest(changed, HOME)
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write(digest_after + "\n")
        check("allow", "re-deriving the stamp from the changed template makes the same "
                       "call pass again",
              "Bash", {"command": "echo hi"}, repo_dir=repo, stamp_file=stamp_path)
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(stamp_dir, ignore_errors=True)

except Exception:
    fails += 1
    import traceback
    traceback.print_exc()

print(f"\n  harness-stamp-gate.test.py: {fails} failure(s)")
sys.exit(1 if fails else 0)
