---
name: l
description: Later — create a new parked session for another subject without switching into it.
argument-hint: "<slug of the later subject> <short note capturing the thought>"
disable-model-invocation: true
---

Capture a subject to handle *later*, from $ARGUMENTS, WITHOUT leaving the current session. Create a new session document for it — `session/<date>-<slug>/current.md` from `templates/current.md`, with `Status: parked` — and write the gist of the thought into its Problem / Open Questions so nothing is lost.

Then stay in the current session: do not switch your attention to the new subject, do not start work on it, do not research it. The parked session waits until it is explicitly entered with `/n`. "Later" names the behaviour — queue the subject, do not act on it.

This creates a session, not a KB.
