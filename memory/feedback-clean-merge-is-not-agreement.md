---
name: feedback-clean-merge-is-not-agreement
description: A conflict-free merge proves only that two sides edited different files — after any divergence, compare what each side's work actually produces, not whether git complained.
metadata:
  type: feedback
---

When two checkouts of the same repository have diverged, a merge that reports no conflict is
not evidence that the two sides agree. Git compares text within a file; it cannot see two
sides doing the same job in two different files, which is exactly the case where it stays
silent and the result is broken.

**Why:** on 2026-08-13 `~/Dev/ai` held 21 local commits registering new hooks directly in the
committed `settings.json`, while the server held 5 commits replacing that file with a
`settings.json.template` rendered per machine. No file was touched on both sides, so the merge
was perfectly clean — and produced a checkout in which running the deploy script would have
silently switched off two live hooks. The defect was found only by rendering the template by
hand and diffing the hook list against the live file, which git had no reason to do.

**How to apply:** after merging a divergence, do not stop at "no conflicts". Ask what each side
was *trying to achieve* and check the produced artefact — render the config and compare the
effective settings, list the registered hooks or routes on both sides, run the test suites.
Overlapping *files* are what git checks; overlapping *purposes* are what you must check. The
tell is two sides touching the same subsystem through different filenames.

Related: [[feedback_git_staging]], which is the same lesson at commit time — git will happily
carry work you never looked at.
