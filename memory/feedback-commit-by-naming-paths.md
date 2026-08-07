---
name: feedback-commit-by-naming-paths
description: Never stage and then commit in two steps — name the paths on the git commit itself, because a parallel session's blind stage sweeps up anything left staged in a shared checkout
metadata:
  type: feedback
---

Commit with `git commit -m "…" -- <path> <path>`, which stages and commits those paths in one operation. Never run `git add <path>` and then `git commit` as a separate call.

**Why:** on 2026-08-07 two Claude Code sessions shared one checkout of `~/Dev/app`, which means one working tree and one staging area. Twice within half an hour, a file I had staged by name was carried into the *other* session's commit, because that session ran a blanket stage in the fraction of a second between my `git add` and my `git commit`. Nothing was lost, but a card's closure landed inside an unrelated commit about a different subject, and my own commit failed with `cannot lock ref 'HEAD'`. Staging by name — which [[feedback_git_staging]] already requires and still requires — protects against sweeping *other* people's work into mine; it does nothing at all against mine being swept into theirs. The gap is the window between the two commands, and naming paths on the commit closes it.

**How to apply:** `git commit -m "…" -- <paths>` for every commit. For a rename, `git mv` still stages, so follow it with a commit naming the new path in the same shell invocation joined by `&&` — and be aware `git mv` moves the *index* entry, so working-tree edits made before the move are not included and need their own commit. When a commit fails with `cannot lock ref 'HEAD'`, another session committed at the same instant: re-read `git status` before retrying, never blindly re-run.

The real fix is separation rather than care: a second coordinator session on a project starts through that project's own session-start command so it gets its own copy of the repository. Careful commit habits are the fallback for when it has not.
