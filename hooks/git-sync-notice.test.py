#!/usr/bin/env python3
"""Test harness for the HRN-155 hook hooks/git-sync-notice.sh.

Founded directly under hooks/, exactly as hooks/README.md and bin/hook-install's own
fifth refusal require for hooks/git-sync-notice.sh itself (checkpoint HRN-155.9 founds
that file the same way, since bin/hook-install cannot install onto a live path that does
not exist yet); this test suite is what that founding hook, and the fetch-carrying
candidate HRN-155.10 later installs on top of it, are both proved against.

Every scenario below builds its own scratch "remote" — a bare git repository created with
`git init --bare` — and one or more scratch clones of it, entirely under a temporary
directory this suite creates and removes; it never reads or writes the real ~/Dev/ai or
~/Dev/app, and never touches any real remote over the network. GIT_SYNC_NOTICE_REPOS
points the hook at exactly the scratch clone(s) each scenario built, and
GIT_SYNC_NOTICE_STATE_DIR (once HRN-155.10 lands) points its own per-repository
fetch-attempt bookkeeping at a scratch directory too, so no scenario here ever touches the
real ~/.claude either.

Run directly: python3 /Users/laptop/Dev/ai/hooks/git-sync-notice.test.py [candidate-path]
With no argument this runs against the installed hook at
/Users/laptop/Dev/ai/hooks/git-sync-notice.sh; given one argument it runs against that
file instead, which is what bin/hook-install uses to test a candidate before installing
it. Exit code 0 when every check passes, 1 when any fails (own PASS/FAIL harness, matching
the sibling *.test.py files in this directory rather than unittest).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HOOK = sys.argv[1] if len(sys.argv) > 1 else "/Users/laptop/Dev/ai/hooks/git-sync-notice.sh"

fails = 0


def state_path_for(state_dir, repo):
    """The per-repository state file path, computed with the SAME sanitisation the hook
    itself applies to a repo path (non alnum/underscore/hyphen characters replaced with
    '_') — used so a scenario can pre-seed or read back a specific repository's own
    fetch-attempt record directly, rather than discovering the filename by inspecting
    whatever the hook happens to write."""
    key = re.sub(r'[^A-Za-z0-9_-]', '_', repo)
    return os.path.join(state_dir, "git-sync-notice-%s.json" % key)


def run_git(cwd, *args, check=True):
    r = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError("git -C %s %s failed: %s" % (cwd, " ".join(args), r.stderr))
    return r.stdout.strip()


def write_and_commit(repo, name, content, message):
    with open(os.path.join(repo, name), "w", encoding="utf-8") as f:
        f.write(content)
    run_git(repo, "add", name)
    run_git(repo, "commit", "-q", "-m", message)


def make_remote_and_clone(root, branch="main"):
    """Build the fixture every scenario below starts from: a bare repository (the
    'remote') seeded with one commit, and a clone of it that tracks origin/<branch>.
    Returns (bare_path, clone_path)."""
    bare = os.path.join(root, "remote.git")
    subprocess.run(["git", "init", "--quiet", "--bare", "-b", branch, bare], check=True)

    seed = os.path.join(root, "seed")
    run_git(root, "clone", "--quiet", bare, seed)
    run_git(seed, "config", "user.email", "test@example.com")
    run_git(seed, "config", "user.name", "Test")
    write_and_commit(seed, "file.txt", "one\n", "initial commit")
    run_git(seed, "push", "--quiet", "origin", "HEAD:%s" % branch)

    clone = os.path.join(root, "clone")
    run_git(root, "clone", "--quiet", "-b", branch, bare, clone)
    run_git(clone, "config", "user.email", "test@example.com")
    run_git(clone, "config", "user.name", "Test")
    return bare, clone


def advance_remote(bare, root, branch="main", n=1, tag=""):
    """Push N more commits to the bare repo through a second, throwaway clone — never
    through the fixture's own primary clone, so the primary clone's remote-tracking ref
    stays exactly where it was at its last fetch (never), proving the hook reads only
    refs already on disk."""
    pusher = tempfile.mkdtemp(prefix="git-sync-notice-pusher-", dir=root)
    run_git(root, "clone", "--quiet", "-b", branch, bare, pusher)
    run_git(pusher, "config", "user.email", "test@example.com")
    run_git(pusher, "config", "user.name", "Test")
    for i in range(n):
        write_and_commit(pusher, "remote-advance%s.txt" % tag, "advance %d\n" % i,
                          "remote-only commit %d%s" % (i, tag))
    run_git(pusher, "push", "--quiet", "origin", "HEAD:%s" % branch)


def advance_local(clone, n=1):
    for i in range(n):
        write_and_commit(clone, "local-advance.txt", "local %d\n" % i,
                          "local-only commit %d" % i)


def call(repos, state_dir=None, fetch_interval=None, extra_env=None):
    payload = {"hook_event_name": "SessionStart", "source": "startup"}
    env = dict(os.environ)
    env["GIT_SYNC_NOTICE_REPOS"] = " ".join(repos)
    if state_dir is not None:
        env["GIT_SYNC_NOTICE_STATE_DIR"] = state_dir
    if fetch_interval is not None:
        env["GIT_SYNC_NOTICE_FETCH_INTERVAL"] = str(fetch_interval)
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(["bash", HOOK], input=json.dumps(payload),
                        capture_output=True, text=True, env=env, timeout=15)
    return r.returncode, r.stdout


def check(label, condition, detail=""):
    global fails
    fails += 0 if condition else 1
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else '  ' + detail}")


try:
    root = tempfile.mkdtemp(prefix="git-sync-notice-test-")

    # --- ahead: local has an unpushed commit, remote unchanged ---
    scen = os.path.join(root, "ahead")
    os.makedirs(scen)
    bare, clone = make_remote_and_clone(scen)
    advance_local(clone, 1)
    code, out = call([clone])
    check("ahead: exit code is 0", code == 0, f"got {code}")
    check("ahead: names the repo, 1 ahead, 0 behind",
          (clone in out and "1 commit(s) ahead" in out and "0 commit(s) behind" in out),
          f"stdout={out!r}")

    # --- behind: the remote advances, and a PRIOR fetch (simulated here, in the fixture's
    # own setup, standing in for an earlier session's background fetch) already brought
    # the new commits onto disk as the local remote-tracking ref — never a fetch made by
    # the hook's own call below, which reads only what is already there ---
    scen = os.path.join(root, "behind")
    os.makedirs(scen)
    bare, clone = make_remote_and_clone(scen)
    advance_remote(bare, scen, n=2, tag="-behind")
    run_git(clone, "fetch", "--quiet")
    code, out = call([clone])
    check("behind: exit code is 0", code == 0, f"got {code}")
    check("behind: names the repo, 0 ahead, 2 behind",
          (clone in out and "0 commit(s) ahead" in out and "2 commit(s) behind" in out),
          f"stdout={out!r}")

    # --- both at once: local has an unpushed commit AND a prior fetch already brought the
    # remote's own further advance onto disk ---
    scen = os.path.join(root, "both")
    os.makedirs(scen)
    bare, clone = make_remote_and_clone(scen)
    advance_remote(bare, scen, n=3, tag="-both")
    run_git(clone, "fetch", "--quiet")
    advance_local(clone, 1)
    code, out = call([clone])
    check("both: exit code is 0", code == 0, f"got {code}")
    check("both: names the repo, 1 ahead, 3 behind",
          (clone in out and "1 commit(s) ahead" in out and "3 commit(s) behind" in out),
          f"stdout={out!r}")

    # --- agreement: freshly cloned, nothing diverged — prints nothing ---
    scen = os.path.join(root, "agree")
    os.makedirs(scen)
    bare, clone = make_remote_and_clone(scen)
    code, out = call([clone])
    check("agreement: exit code is 0", code == 0, f"got {code}")
    check("agreement: prints nothing at all", out.strip() == "", f"stdout={out!r}")

    # --- a missing directory: never crashes, never named, exit 0 ---
    missing = os.path.join(root, "does-not-exist-at-all")
    code, out = call([missing])
    check("missing directory: exit code is 0", code == 0, f"got {code}")
    check("missing directory: prints nothing", out.strip() == "", f"stdout={out!r}")

    # --- a repository with no remote at all ---
    scen = os.path.join(root, "no-remote")
    os.makedirs(scen)
    run_git(root, "init", "--quiet", scen)
    run_git(scen, "config", "user.email", "test@example.com")
    run_git(scen, "config", "user.name", "Test")
    write_and_commit(scen, "file.txt", "one\n", "only commit")
    code, out = call([scen])
    check("no remote: exit code is 0", code == 0, f"got {code}")
    check("no remote: prints nothing", out.strip() == "", f"stdout={out!r}")

    # --- a detached head, even with real drift against its own remote ---
    scen = os.path.join(root, "detached")
    os.makedirs(scen)
    bare, clone = make_remote_and_clone(scen)
    advance_remote(bare, scen, n=1, tag="-detached")
    run_git(clone, "fetch", "--quiet")
    head_sha = run_git(clone, "rev-parse", "HEAD")
    run_git(clone, "checkout", "--quiet", "--detach", head_sha)
    code, out = call([clone])
    check("detached head: exit code is 0", code == 0, f"got {code}")
    check("detached head: prints nothing even though the branch it left behind is behind",
          out.strip() == "", f"stdout={out!r}")

    # --- several repositories in one call: each is judged independently ---
    scen = os.path.join(root, "multi")
    os.makedirs(scen)
    bare1, clone1 = make_remote_and_clone(os.path.join(scen, "one"))
    bare2, clone2 = make_remote_and_clone(os.path.join(scen, "two"))
    advance_local(clone1, 1)
    code, out = call([clone1, clone2])
    check("multi-repo: exit code is 0", code == 0, f"got {code}")
    check("multi-repo: the drifted repo is named", clone1 in out, f"stdout={out!r}")
    check("multi-repo: the agreeing repo is never named", clone2 not in out,
          f"stdout={out!r}")

    # =====================================================================================
    # HRN-155.10: the rate-limited background fetch. These scenarios only pass once the
    # fetch-carrying candidate is installed on top of the founding (report-only) hook —
    # they prove the state file that records a fetch ATTEMPT is written synchronously,
    # in the foreground, before the actual `git fetch` is backgrounded, which is what
    # makes checking it immediately after the hook process exits reliable rather than
    # racy against a detached child process.
    # =====================================================================================

    # --- no prior state at all: an attempt is recorded now ---
    scen = os.path.join(root, "fetch-fresh")
    os.makedirs(scen)
    bare, clone = make_remote_and_clone(scen)
    state_dir = os.path.join(scen, "state")
    before = time.time()
    code, out = call([clone], state_dir=state_dir, fetch_interval=100)
    after = time.time()
    check("fetch interval, no prior state: exit code is 0", code == 0, f"got {code}")
    state_files = [f for f in os.listdir(state_dir)] if os.path.isdir(state_dir) else []
    check("fetch interval, no prior state: a state file was written",
          len(state_files) == 1, f"found {state_files!r}")
    if state_files:
        with open(os.path.join(state_dir, state_files[0]), encoding="utf-8") as f:
            recorded = json.load(f).get("last_attempt")
        check("fetch interval, no prior state: recorded timestamp is roughly now",
              recorded is not None and before - 5 <= recorded <= after + 5,
              f"recorded={recorded!r}, window=({before - 5}, {after + 5})")

    # --- a recent attempt (well inside the interval): no new attempt is recorded ---
    scen = os.path.join(root, "fetch-recent")
    os.makedirs(scen)
    bare, clone = make_remote_and_clone(scen)
    state_dir = os.path.join(scen, "state")
    os.makedirs(state_dir)
    real_state_path = state_path_for(state_dir, clone)
    recent_ts = time.time() - 10  # 10s ago, well inside a 100s interval
    with open(real_state_path, "w", encoding="utf-8") as f:
        json.dump({"last_attempt": recent_ts}, f)
    code, out = call([clone], state_dir=state_dir, fetch_interval=100)
    check("fetch interval, recent attempt: exit code is 0", code == 0, f"got {code}")
    with open(real_state_path, encoding="utf-8") as f:
        after_recorded = json.load(f).get("last_attempt")
    check("fetch interval, recent attempt: timestamp is left untouched (no new attempt)",
          abs(after_recorded - recent_ts) < 0.5, f"before={recent_ts!r}, after={after_recorded!r}")

    # --- a stale attempt (older than the interval): a new attempt IS recorded ---
    scen = os.path.join(root, "fetch-stale")
    os.makedirs(scen)
    bare, clone = make_remote_and_clone(scen)
    state_dir = os.path.join(scen, "state")
    os.makedirs(state_dir)
    real_state_path = state_path_for(state_dir, clone)
    stale_ts = time.time() - 200  # older than the 100s interval below
    with open(real_state_path, "w", encoding="utf-8") as f:
        json.dump({"last_attempt": stale_ts}, f)
    before = time.time()
    code, out = call([clone], state_dir=state_dir, fetch_interval=100)
    after = time.time()
    check("fetch interval, stale attempt: exit code is 0", code == 0, f"got {code}")
    with open(real_state_path, encoding="utf-8") as f:
        after_recorded = json.load(f).get("last_attempt")
    check("fetch interval, stale attempt: timestamp is updated to roughly now",
          after_recorded is not None and before - 5 <= after_recorded <= after + 5,
          f"recorded={after_recorded!r}, window=({before - 5}, {after + 5})")

    shutil.rmtree(root, ignore_errors=True)

except Exception:
    fails += 1
    import traceback
    traceback.print_exc()

print(f"\n  git-sync-notice.test.py: {fails} failure(s)")
sys.exit(1 if fails else 0)
