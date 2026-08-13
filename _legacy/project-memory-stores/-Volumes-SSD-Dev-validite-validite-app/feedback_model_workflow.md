---
name: model-workflow
description: "User's preference for splitting work between Opus (planning) and Sonnet (execution) with /clear between"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 684aabf8-136e-4ec5-910c-b4e7d8b83847
---

User prefers to do heavy planning/design/interview work in Opus, then **persist the
plan to disk, `/clear` context, and switch to Sonnet to execute** against the written plan.

**Why:** cost — Sonnet is ~5x cheaper and the design work (the part needing Opus) is
already captured in the plan; clearing context also drops accumulated tokens so the
execution session runs lean.

**How to apply:**
- Make plans **self-contained on disk inside the repo** (not just the `~/.claude/plans/`
  scratch path, which a `/clear`'d session won't auto-load). Save into `ai/plans/` with a
  resume header + progress board, and point `ai/INDEX.md` at it. See [[feedback-resumable-workflow]].
- When a planning session ends, expect a model switch; don't assume the next session
  remembers conversation nuance — the plan file must stand alone.
- If asked "do I need Opus?" for execution-style work: recommend Sonnet, reserve Opus for
  the genuinely hard reasoning (e.g. tricky algorithm/state logic) if it gets stuck.
