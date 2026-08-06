---
name: feedback-reported-failure-is-a-work-order
description: When Alex reports something broken in the real world (a failed deploy, a crashed build, an error he pasted), that IS the authorisation to fix it — do not ask whether to start
metadata:
  type: feedback
---

When Alex reports a live failure — a deploy that errored, a build that stopped, a pasted stack trace — that report is the work order. Diagnose it, and start the fix, including spawning the executor if the work needs one. Do not come back with an explanation plus a question about whether to proceed.

**Why:** on 2026-08-06 he pasted a failed container build and I answered with a diagnosis and then asked whether to hand it to an executor or fix it myself. His reply: «как думаешь, я чисто теоретически спросил, что словно на диплое? Или я что-то хотел от тебя?» The asking cost a full round trip while a deployment stayed broken.

**How to apply:** treat a reported real-world failure as already-granted authority for the repair, and say what you started rather than asking whether to start. Report the diagnosis and the action in the same message. Keep asking only where the fix itself needs a decision he has not made — which version to move to, whether to pin a base image, what to do about data already written — and ask that question while the repair is already under way, not instead of it.

**Not in tension with [[feedback_reviewer_agent]] and the "quote the yes" rule.** Those govern speculative or expensive work Alex has not asked for. A failure he brought to me himself is asked-for work; the yes is the report.
