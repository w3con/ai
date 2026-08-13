#!/usr/bin/env python3
"""Test harness for the Stop hook hooks/inbox-stop.py.

Why this file exists. Until 2026-08-13 this hook was the only file in this directory with
no test suite of its own, and that had a consequence beyond the missing coverage:
bin/hook-install refuses to install any hook that has no suite, so the one prescribed,
atomic, tested route for changing a live hook was closed for this file, and the only way
to change it at all was to edit it in place — precisely the thing hooks/README.md and
bin/hook-install exist to forbid. Founding this suite reopens that route.

What it proves. Two things, and the first matters more than it looks. The hook has to
decide which checkout is "the application repository", and that checkout does not sit at
the same path on the two machines this configuration is deployed to. It used to answer
that question with one machine's literal home directory written into the file, so on the
other machine it matched no working directory at all and silently delivered nothing —
silently, because a Stop hook that decides it has nothing to say is indistinguishable
from a Stop hook that is working. The scenarios below pin the resolution order it now
uses: an explicit AI_APP_REPO wins outright, and with that unset the first of the known
checkout locations that actually exists on the running machine wins. The second thing is
the hook's ordinary behaviour — that it blocks the turn when a message is waiting, passes
the message through in the shape the cockpit sends it, and stays silent and exits zero on
every kind of breakage, because a hook that cannot do its job must never be able to
freeze a session.

Every scenario builds its own scratch home directory and its own scratch checkout under a
temporary directory this suite creates and removes, including a stand-in `bin/session-inbox`
that prints whatever that scenario wants drained. Nothing here reads or writes the real
~/Dev/ai, the real application checkout, or the real ~/.claude.

Run directly: python3 ~/Dev/ai/hooks/inbox-stop.test.py [candidate-path]
With no argument this runs against the installed hook at ~/Dev/ai/hooks/inbox-stop.py;
given one argument it runs against that file instead, which is what bin/hook-install uses
to test a candidate before installing it. Exit code 0 when every check passes, 1 when any
fails (own PASS/FAIL harness, matching the sibling *.test.py files in this directory).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

_AI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HOOKS = os.path.join(_AI_ROOT, "hooks")

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HOOKS, "inbox-stop.py")

fails = 0


def check(label, condition, detail=""):
    global fails
    if condition:
        print("  PASS  %s" % label)
    else:
        fails += 1
        print("  FAIL  %s%s" % (label, (" — " + detail) if detail else ""))


def make_checkout(path, drain_output="", exit_code=0, broken=False):
    """Build a scratch stand-in for the application checkout: a directory that looks like
    a git working tree, holding a bin/session-inbox that prints exactly what this scenario
    wants drained. When `broken` is true the stand-in is left out entirely, which is how a
    missing or unrunnable command is simulated."""
    os.makedirs(os.path.join(path, ".git"), exist_ok=True)
    if broken:
        return path
    os.makedirs(os.path.join(path, "bin"), exist_ok=True)
    script = os.path.join(path, "bin", "session-inbox")
    with open(script, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env python3\n"
                "import sys\n"
                "sys.stdout.write(%r)\n"
                "sys.exit(%d)\n" % (drain_output, exit_code))
    os.chmod(script, 0o755)
    return path


def call(payload, env_extra=None, raw_stdin=None):
    """Run the hook with one Stop-hook payload on standard input, in an environment this
    scenario controls. Returns (exit code, standard output)."""
    env = dict(os.environ)
    # Both are cleared first so a scenario always states its own answer rather than
    # inheriting whatever the machine running this suite happens to have set.
    env.pop("AI_APP_REPO", None)
    env.update(env_extra or {})
    stdin = raw_stdin if raw_stdin is not None else json.dumps(payload)
    result = subprocess.run([sys.executable, HOOK], input=stdin,
                            capture_output=True, text=True, timeout=30, env=env)
    return result.returncode, result.stdout


def decision_of(out):
    """The parsed hook decision, or None when the hook said nothing at all."""
    if not out.strip():
        return None
    return json.loads(out)


root = tempfile.mkdtemp(prefix="inbox-stop-test-")
try:
    # ---------------------------------------------------------------------------
    # Resolving which checkout is the application repository. This is the group that
    # guards against the machine-specific path this hook once carried.
    # ---------------------------------------------------------------------------
    print("\nresolving the application checkout")

    # An explicit AI_APP_REPO wins outright, even when it is nowhere near a known location.
    scen = os.path.join(root, "named")
    named_repo = make_checkout(os.path.join(scen, "somewhere", "entirely", "else"),
                               drain_output='{"text": "from the named repo"}\n')
    code, out = call({"cwd": named_repo}, {"AI_APP_REPO": named_repo})
    d = decision_of(out)
    check("AI_APP_REPO names the checkout: the hook blocks the turn",
          code == 0 and d is not None and d.get("decision") == "block",
          "exit=%r out=%r" % (code, out))
    check("AI_APP_REPO names the checkout: the message is carried through",
          d is not None and "from the named repo" in d.get("reason", ""),
          "out=%r" % out)

    # With AI_APP_REPO unset, the first known checkout location that exists here wins.
    # ~/Dev/app is tried before ~/Dev/validite/validite-app, so a scratch home holding
    # only the second must still resolve — this is the case that used to fail outright.
    scen = os.path.join(root, "second-candidate")
    home = os.path.join(scen, "home")
    second = make_checkout(os.path.join(home, "Dev", "validite", "validite-app"),
                           drain_output='{"text": "from the second candidate"}\n')
    code, out = call({"cwd": second}, {"HOME": home})
    d = decision_of(out)
    check("no AI_APP_REPO: the second known checkout location is found",
          code == 0 and d is not None and "from the second candidate" in d.get("reason", ""),
          "exit=%r out=%r" % (code, out))

    # When the first candidate does exist, it is the one chosen.
    scen = os.path.join(root, "first-candidate")
    home = os.path.join(scen, "home")
    first = make_checkout(os.path.join(home, "Dev", "app"),
                          drain_output='{"text": "from the first candidate"}\n')
    make_checkout(os.path.join(home, "Dev", "validite", "validite-app"),
                  drain_output='{"text": "from the second candidate"}\n')
    code, out = call({"cwd": first}, {"HOME": home})
    d = decision_of(out)
    check("no AI_APP_REPO: the first known checkout location wins when it exists",
          code == 0 and d is not None and "from the first candidate" in d.get("reason", ""),
          "exit=%r out=%r" % (code, out))

    # No candidate exists anywhere: the hook must simply stay silent, not fail.
    scen = os.path.join(root, "no-candidate")
    home = os.path.join(scen, "home")
    os.makedirs(home)
    code, out = call({"cwd": home}, {"HOME": home})
    check("no checkout anywhere: exits 0 and says nothing",
          code == 0 and out.strip() == "", "exit=%r out=%r" % (code, out))

    # ---------------------------------------------------------------------------
    # Which turns the hook speaks on at all.
    # ---------------------------------------------------------------------------
    print("\nchoosing which turns to speak on")

    scen = os.path.join(root, "outside")
    repo = make_checkout(os.path.join(scen, "repo"),
                         drain_output='{"text": "should never be delivered"}\n')
    elsewhere = os.path.join(scen, "unrelated")
    os.makedirs(elsewhere)
    code, out = call({"cwd": elsewhere}, {"AI_APP_REPO": repo})
    check("a turn outside the checkout: exits 0 and says nothing",
          code == 0 and out.strip() == "", "exit=%r out=%r" % (code, out))

    code, out = call({"cwd": os.path.join(repo, "deep", "inside")}, {"AI_APP_REPO": repo})
    check("a turn in a subdirectory of the checkout: still speaks",
          code == 0 and decision_of(out) is not None, "exit=%r out=%r" % (code, out))

    scen = os.path.join(root, "empty-drain")
    repo = make_checkout(os.path.join(scen, "repo"), drain_output="")
    code, out = call({"cwd": repo}, {"AI_APP_REPO": repo})
    check("nothing waiting in the inbox: exits 0 and says nothing",
          code == 0 and out.strip() == "", "exit=%r out=%r" % (code, out))

    # ---------------------------------------------------------------------------
    # The shape of what it hands back.
    # ---------------------------------------------------------------------------
    print("\nthe shape of the message handed back")

    scen = os.path.join(root, "with-card")
    repo = make_checkout(os.path.join(scen, "repo"),
                         drain_output='{"text": "check the totals", "card": "HRN-9"}\n')
    code, out = call({"cwd": repo}, {"AI_APP_REPO": repo})
    d = decision_of(out)
    check("a message carrying a card identifier is prefixed with it",
          d is not None and "[HRN-9] check the totals" in d.get("reason", ""),
          "out=%r" % out)

    scen = os.path.join(root, "several")
    repo = make_checkout(
        os.path.join(scen, "repo"),
        drain_output='{"text": "first message"}\n{"text": "second message"}\n')
    code, out = call({"cwd": repo}, {"AI_APP_REPO": repo})
    d = decision_of(out)
    check("several waiting messages are all carried through",
          d is not None and "first message" in d.get("reason", "")
          and "second message" in d.get("reason", ""), "out=%r" % out)

    scen = os.path.join(root, "blank")
    repo = make_checkout(os.path.join(scen, "repo"),
                         drain_output='{"text": "   "}\n')
    code, out = call({"cwd": repo}, {"AI_APP_REPO": repo})
    check("a message whose text is only whitespace is not delivered",
          code == 0 and out.strip() == "", "exit=%r out=%r" % (code, out))

    scen = os.path.join(root, "not-json")
    repo = make_checkout(os.path.join(scen, "repo"),
                         drain_output='a plain line that is not json\n')
    code, out = call({"cwd": repo}, {"AI_APP_REPO": repo})
    d = decision_of(out)
    check("a drained line that is not JSON is passed through verbatim",
          d is not None and "a plain line that is not json" in d.get("reason", ""),
          "out=%r" % out)

    scen = os.path.join(root, "unicode")
    repo = make_checkout(os.path.join(scen, "repo"),
                         drain_output='{"text": "проверь итоги"}\n')
    code, out = call({"cwd": repo}, {"AI_APP_REPO": repo})
    d = decision_of(out)
    check("a message in Cyrillic survives unescaped",
          d is not None and "проверь итоги" in d.get("reason", ""), "out=%r" % out)

    # ---------------------------------------------------------------------------
    # Failing open. Every one of these must exit 0 and print nothing, because a Stop
    # hook that errors is read as a refusal and would freeze the session.
    # ---------------------------------------------------------------------------
    print("\nfailing open on every kind of breakage")

    scen = os.path.join(root, "bad-stdin")
    repo = make_checkout(os.path.join(scen, "repo"), drain_output='{"text": "x"}\n')
    code, out = call(None, {"AI_APP_REPO": repo}, raw_stdin="this is not json at all")
    check("standard input is not JSON: exits 0 and says nothing",
          code == 0 and out.strip() == "", "exit=%r out=%r" % (code, out))

    code, out = call(None, {"AI_APP_REPO": repo}, raw_stdin="")
    check("standard input is empty: exits 0 and says nothing",
          code == 0 and out.strip() == "", "exit=%r out=%r" % (code, out))

    code, out = call({}, {"AI_APP_REPO": repo})
    check("the payload carries no cwd at all: exits 0 and says nothing",
          code == 0 and out.strip() == "", "exit=%r out=%r" % (code, out))

    scen = os.path.join(root, "no-command")
    repo = make_checkout(os.path.join(scen, "repo"), broken=True)
    code, out = call({"cwd": repo}, {"AI_APP_REPO": repo})
    check("bin/session-inbox is missing: exits 0 and says nothing",
          code == 0 and out.strip() == "", "exit=%r out=%r" % (code, out))

    scen = os.path.join(root, "command-fails")
    repo = make_checkout(os.path.join(scen, "repo"), drain_output="", exit_code=3)
    code, out = call({"cwd": repo}, {"AI_APP_REPO": repo})
    check("bin/session-inbox exits non-zero with nothing to say: exits 0 and says nothing",
          code == 0 and out.strip() == "", "exit=%r out=%r" % (code, out))

except Exception:
    fails += 1
    import traceback
    traceback.print_exc()
finally:
    shutil.rmtree(root, ignore_errors=True)

print("\n  inbox-stop.test.py: %d failure(s)" % fails)
sys.exit(1 if fails else 0)
