---
name: feedback-post-compaction-own-work
description: After a context compaction, uncommitted changes in the tree may be your own forgotten session work — verify authorship before calling them a parallel agent's
metadata:
  type: feedback
---

After the conversation is summarized/compacted, work you did earlier **in the same session** drops
out of your visible context. When you later run `git status` and find unexplained uncommitted
changes — staged renames, untracked dirs, modified files — do **not** assume they belong to a
parallel agent or a previous session. They may be your own, made hours ago this session and simply
forgotten by compaction.

**Why:** on 2026-07-19 I found the `cloud` repo mid-reorganization (staged `pilier.net/ops → ops`
renames, untracked `ai/`/`knowledge/`, a modified README) and reported it to Alex as "very likely a
parallel agent's work I can't explain," refusing to commit. Alex corrected me: "это ТВОИ ЖЕ
изменения в ЭТОЙ Же сессии, только часа 4-5 назад." It was all mine. The caution not to touch it was
right; the attribution was wrong, and it made me hand back a false explanation.

**How to apply:** when the tree holds changes you don't remember making, treat authorship as an open
question, not a settled "someone else." Check cheaply before concluding — `git log`/reflog timing,
whether the changes match your own style and this session's task, or just ask Alex "are these mine
from earlier?" State uncertainty as uncertainty. The staging discipline in [[feedback_git_staging]]
still holds either way: stage by name, never blind `git add -A`. This only corrects *whose* the
changes are, not whether to sweep them in — and once confirmed yours, they are safe to commit.
