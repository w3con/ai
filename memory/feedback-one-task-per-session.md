---
name: feedback-one-task-per-session
description: "One task per session so the conversation stays disposable; parallel work goes to a separate session cut by bin/session-start; and cut the number of tool calls, because every call re-sends the whole context"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 18177dfa-e88d-4183-a0b5-bf9bee50d5c8
  modified: 2026-08-15T21:32:45.279Z
---

A session carries exactly one task. Everything worth keeping already lives in the task card and in git, so once that task is accepted the whole conversation can be rewound or discarded without losing anything. Several tasks in one session destroy that property: the conversation becomes the only place where the loose ends of the other tasks are tied together, so it can be neither compacted nor rewound, and it grows without limit.

Sequential work — one task after another, which is the ordinary case — needs nothing but `/clear` in the same window once the task is accepted. A separate copy of the repository is needed only for genuine **simultaneity**, when a second conversation is to run while the first still does: two sessions sharing one working tree and one staging area interleaved three commits in two minutes on 2026-08-07. In the Validité DPP project that copy is cut by `bin/session-start`, and `/session` (`.claude/skills/session/`) is the shortcut that walks both cases.

**Why:** Alex, 2026-08-15 — «мне нужно, чтобы у нас не было запущено несколько задач в параллели. Тогда я могу легко делать /rewind с сохранением файлов… а когда у тебя несколько задач, я не успеваю делать ни /rewind ни /compact — боясь потерять информацию важную для других задач». And the cost driver behind it, in his words: «и таких вызовов может быть много — и все с контекстом в 100-200тыс. токенов… растет как снежный ком. потому что ты дорогой». Every tool call re-sends the entire session context, so a small session makes every call cheaper, and a large one multiplies the price of each idle probe.

**How to apply:**
- Take one task per session; when it is accepted, say so plainly and let Alex rewind. Start nothing new in that session.
- Do not poll a background agent — the harness notifies when it finishes.
- Verify an executor's report with machinery first, not by reading: run the acceptance command, which re-runs the card's own gates, and look at the diff **stat** rather than the diff. Read files only when one of those two shows something off. If reading keeps finding the same class of fault, turn that finding into a committed check instead of reading again next time — see [[feedback_reusable_tooling]].
- When a gate or script refuses and names its reason, that message is the instruction: act on it in one call. Do not re-derive it with a chain of status, stat and diff probes.
- Chain several shell commands into a single call instead of issuing them one by one.

Related: [[feedback-commit-by-naming-paths]], [[feedback-executor-card-size]], [[feedback-parallel-executors-shared-tree]].
