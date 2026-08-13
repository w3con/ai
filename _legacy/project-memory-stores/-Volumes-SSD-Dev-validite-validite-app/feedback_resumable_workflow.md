---
name: feedback-resumable-workflow
description: "For multi-step design/interview work, every step must be independently resumable — the user expects to pause and continue across sessions without context loss."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 73abbe9e-e6ee-4495-bf5d-748c0104eb21
---

When running a multi-step process (e.g. a series of design interviews, a long refactor in phases), every step must be **independently resumable across sessions**. The user should be able to stop after any question or any phase and pick up days later with no context loss.

**Why:** User said "design the DESIGN process as a series of independent steps/interviews so I can interrupt it and continue later." Implicitly: a single monolithic chain that depends on conversational context will break the moment the session ends. They want sessions to be cheap to start and resume.

**How to apply:**
- Maintain an **INDEX.md** state board at the root of the working area, with one row per step + current status.
- Each working document (plan, log, draft) opens with a **state header**: current status, last action posted, what's pending, next step on resume.
- Number every question/decision point so it survives a crash mid-step (write Q4 into the plan file *before* posting it to the user).
- Write a **session log** per day (`logs/session_YYYY-MM-DD.md`): which steps were touched, what was decided, what's next.
- On a "continue" / "where were we" prompt: read INDEX.md → find the non-`done` non-`not-started` row → read that file's state header → restate the open action and proceed.
- Interview/step boundaries must be atomic — at the end of each step, INDEX + session log are updated. The work-product remains coherent even if the next step never happens.
- [[feedback-mvp-mode]] reinforces this — MVP demos slip, get interrupted by other priorities; the workflow must survive that.
