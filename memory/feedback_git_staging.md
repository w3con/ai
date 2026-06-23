---
name: Stage exactly your own files — never blind `git add -A`
description: When committing, stage only the specific paths this task changed; never `git add -A`/`git add .` blindly, because the working tree may carry changes from prior or parallel sessions
metadata:
  type: feedback
  scope: user-level
---

When you commit, stage exactly the files this task changed, by name (`git add <path> <path>`), and never run a blind `git add -A` or `git add .`. The working tree is not guaranteed to contain only your work — it can hold changes left by an earlier session, or by a parallel agent working in the same repository at the same time. A blanket stage sweeps all of that into your commit.

**Why:** in one session I tore down a harness and committed with `git add -A`, which swept in three pre-existing plan-file deletions I had not made and had not verified. Two were harmless, but one (`repo-migration.md`) still had a deferred, not-yet-done phase, so committing its deletion erased the only on-disk checkpoint for unfinished work. Alex had also just told me a parallel agent was active in a sibling repo, which makes blind staging especially dangerous.

**How to apply:** before committing, run `git status` and read it; stage only the paths you deliberately changed for this task. If the tree shows unrelated or unexplained changes, do not bundle them — leave them alone and surface them to the user instead. This matters most in long-lived or shared repositories where prior sessions and parallel agents leave traces. Relates to [[feedback_decide_before_building]] (don't act beyond what was decided).
