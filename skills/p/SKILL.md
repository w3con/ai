---
name: p
description: Write a phased, resumable plan to ai/plans/<slug>.md — on disk, never only in chat.
argument-hint: "<slug or name of the subject to plan>"
disable-model-invocation: true
---

Write a phased, resumable plan for the subject named in $ARGUMENTS and save it to disk at `ai/plans/<slug>.md`. A plan never lives only in chat: the file on disk, not a chat message, is what survives the session dying and serves as the resume checkpoint.

Work in the current context — do not spawn a separate planner sub-agent. Each phase produces one artifact, carries explicit acceptance criteria, and is small enough to survive an interrupted session. If $ARGUMENTS does not yet name the subject, ask for it before writing.

After saving, show the plan to Alex and wait for his explicit word. Do not begin building.
