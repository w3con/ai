---
name: l
description: Park a side thought as its own parked session, without leaving the current one.
argument-hint: "<slug of the side subject> <short note capturing the thought>"
disable-model-invocation: true
---

Capture the side thought in $ARGUMENTS so it is not lost, WITHOUT leaving the current session. Create a new parked session for it: a `session/<date>-<slug>/current.md` from the template `templates/current.md` with `Status: parked`, and write the gist of the thought into it as a "don't forget" note.

This does not create a KB and does not scaffold a subject — only a parked session document. Creating a KB is the job of the `new-kb` skill, not this command.

After parking, return to exactly the current subject and the current loop. Do not switch your attention to the new subject, do not start work on it, do not research it — it is only parked, waiting until it is explicitly started with `/n`. The point of this command is to keep the session atomic — one subject at a time — without losing side thoughts.
