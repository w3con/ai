#!/usr/bin/env python3
"""Stop hook — carry a message submitted on the session page into the running session.

The cockpit (`bin/plan-ui` in the application checkout) appends every line the owner submits to
`ai/session/inbox.jsonl`. Nothing could deliver such a line into a session that was already
running: a background watcher only reports when it exits, so it caught one message and then
had to be armed again by hand. This hook removes that. It runs at the end of every turn,
drains whatever is unread, and — when there is something — refuses to let the turn end,
handing the message back as the reason, so the session answers it immediately.

It terminates because `bin/session-inbox --drain` advances its own read position: the same
line is never returned twice, so a turn that produced no new submission always ends.

It fails open on every error, like the other hooks in this directory: a hook that cannot
read its input, cannot find the repository or cannot run the command exits 0 and says
nothing, because a broken hook must never be able to freeze a session.
"""
import json
import os
import subprocess
import sys

# 2026-08-13: this used to be the literal /Users/laptop/Dev/app — one machine's home
# directory written into a file both machines run, so on the other machine this hook
# matched no working directory at all and silently never delivered anything. The repository
# is now named by AI_APP_REPO where it is set, and otherwise resolved to the first of the
# known checkout locations that actually exists on the machine running this file.
def _resolve_app_repo():
    named = os.environ.get("AI_APP_REPO")
    if named:
        return os.path.realpath(named)
    home = os.path.expanduser("~")
    for candidate in (os.path.join(home, "Dev", "app"),
                      os.path.join(home, "Dev", "validite", "validite-app"),
                      "/Volumes/SSD/Dev/validite/validite-app"):  # path-check: allow — one candidate among several, tested for existence before use
        if os.path.isdir(os.path.join(candidate, ".git")):
            return os.path.realpath(candidate)
    return os.path.realpath(os.path.join(home, "Dev", "app"))


REPO = _resolve_app_repo()


def format_line(raw):
    try:
        entry = json.loads(raw)
    except ValueError:
        return raw
    text = (entry.get("text") or "").strip()
    card = (entry.get("card") or "").strip()
    if not text:
        return ""
    return f"[{card}] {text}" if card else text


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    # 2026-08-13: this used to be os.path.abspath, while REPO above is built with
    # os.path.realpath — so the two sides of the comparison below resolved symbolic links
    # differently, and the hook then silently matched nothing. On this machine that was not
    # a theoretical mismatch but a total failure: ~/Dev is a symbolic link onto an external
    # volume, so REPO came out as /Volumes/SSD/Dev/validite/validite-app while a session
    # working in that very checkout reported its cwd as ~/Dev/validite/validite-app, and no
    # turn ever matched. Nothing was visible from the outside, because a Stop hook that
    # decides it has nothing to say looks exactly like a Stop hook that is working.
    # Both sides are resolved the same way now, and the suite pins it.
    cwd = os.path.realpath(payload.get("cwd") or "")
    if not (cwd == REPO or cwd.startswith(REPO + os.sep)):
        return 0

    command = os.path.join(REPO, "bin", "session-inbox")
    try:
        result = subprocess.run(
            [sys.executable, command, "--drain", "--root", REPO],
            capture_output=True, text=True, timeout=10)
    except Exception:
        return 0

    messages = [m for m in (format_line(l) for l in result.stdout.splitlines()) if m]
    if not messages:
        return 0

    reason = (
        "Сообщение от владельца, отправленное со страницы сессии, а не набранное в чате. "
        "Ответь на него и сделай то, что в нём просят, прежде чем закончить ход.\n\n"
        + "\n\n".join(messages))
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
