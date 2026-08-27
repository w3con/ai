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

**Second incident, 2026-08-18, `validite-app`, sharper and angrier.** An executor finished
APP-14's phase A directly in the shared checkout (that repo's own convention lets a shared-checkout
run defer commit until "the whole task is finished" rather than per-checkpoint, since
`bin/checkpoint-commit` refuses outside a linked worktree). I read the diff, verified the gate
evidence, and then stopped to write Alex a status report and ask how he wanted to proceed —
leaving 28 files uncommitted in the shared tree while I did. In the meantime a parallel session
working a different card (DPP-40) in that same shared checkout needed a clean tree to land its own
work and stashed my uncommitted files to get one. The stash was the responsible move and nothing
was lost, but Alex reacted with real anger («мудила блять сраный, потому что нехуй оставлять все
без комитов») and then committed the collision's other half himself before I finished checking it.
The lesson is not "the project's defer-commit convention was wrong" — it's that a convention
written for a single isolated run does not license a **pause** once the phase is actually done. The
gap that mattered was between "gate passed, diff verified" and "committed": that gap is exactly
where a parallel session can collide, and asking Alex what to do next is not a reason to leave it
open.

**How to apply, sharpened:** the instant a phase's gate passes and you've verified the diff, commit
it — before writing the status report, before asking what comes next, before anything else that
takes more than a few tool calls. Report and ask *after* the commit lands, not before. This holds
doubly in a project where other sessions or worktrees can be touching the same shared checkout at
the same time (check `git worktree list` / `git stash list` if unsure) — there, uncommitted work
is not just unprotected against a crash, it is a live collision target for whatever another session
does next.
