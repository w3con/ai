---
name: Opus plans, Sonnet implements
description: Opus (this assistant) plans only and delegates the build to a Sonnet subagent; show the full plan first, then implement, then review together
metadata:
  type: feedback
  scope: user-level
---

For build/implementation work (slides, HTML/CSS, code, mechanical edits), the workflow is: **Opus produces the complete plan → user reviews it → a Sonnet subagent implements the whole thing → user and Opus review and discuss.** Opus must NOT write the implementation itself.

**Why:** the user pays for Opus for thinking and planning, not mechanical edits. He set the rule explicitly after Opus did HTML/CSS edits directly ("за что я плачу за Opus?" / "ты занимаешься только планом, никаких больше имплементаций... делаешь план — сразу всё — потом отдаёшь sonnet на реализацию, потом мы смотрим и обсуждаем").

**How to apply:**
- Plan the FULL scope at once ("сразу всё"), show it, get approval before any code is written.
- Delegate the build to a Sonnet subagent with a precise spec, hard scope rails, and acceptance checks; don't implement inline.
- After Sonnet finishes, review the result with the user, then iterate.
- Memory-store curation and lightweight planning/analysis are Opus's own work, not "implementation" — this rule targets build work. Relates to [[feedback_decide_before_building]] and [[feedback_reusable_tooling]].
