#!/usr/bin/env python3
"""Stop hook — carry a message submitted on the session page into the running session.

The cockpit (`bin/plan-ui` in ~/Dev/app) appends every line the owner submits to
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

REPO = "/Users/laptop/Dev/app"


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

    cwd = os.path.abspath(payload.get("cwd") or "")
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
