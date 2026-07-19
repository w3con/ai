---
name: feedback-commit-periodically
description: Commit work at natural milestones and remind Alex to, rather than letting uncommitted changes pile up for hours
metadata:
  type: feedback
---

Don't let a session's work accumulate uncommitted. At every natural milestone — a phase done, a
document finished, a coherent unit of change — commit it (staging by name), and in a long session
proactively **remind Alex** that there are uncommitted changes worth landing. Treat "when did this
last get committed?" as a question worth raising, not waiting for.

**Why:** on 2026-07-19 a large body of `cloud` repo work (an `ops/` tree reorganization plus new
planning docs and a knowledge vault) sat uncommitted for 4–5 hours across a compaction. That caused
real friction — the pile looked foreign and unexplained — and it was unprotected: a crash would have
lost hours of work with no checkpoint. Alex's standing instruction is "значимые этапы — делай git
commit / push"; the failure was letting the pile grow instead of committing as I went.

**How to apply:** commit incrementally as coherent units land, don't batch a whole session into one
late commit. In long or multi-phase work, surface uncommitted state to Alex periodically ("N files
uncommitted in <repo> — want me to commit?") rather than silently carrying it. The on-disk plan is
the resume checkpoint, but only a commit protects finished work. Staging discipline is unchanged:
name the paths, never blind `git add -A` — see [[feedback_git_staging]].
