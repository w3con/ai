---
name: f
description: Append one entry about a mistake to harness/fuckups.md (append-only).
argument-hint: "<which mistake to record; may be empty — I'll take the one just discussed>"
disable-model-invocation: true
---

Append one entry about a mistake to the end of `harness/fuckups.md` — about whatever $ARGUMENTS names, or, if it is empty, about the mistake just discussed in the conversation. The file is strictly append-only: only add to the end, never rewrite or delete anything in it.

The entry follows the structure used in that file: what happened · which rule or memory it broke · the consequence · the root cause · what to change. Write honestly and concretely, in developed sentences, without softening and without excuses — the point of the log is that the root cause stays visible and recognisable next time.
