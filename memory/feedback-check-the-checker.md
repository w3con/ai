---
name: feedback-check-the-checker
description: Before you trust anything that checks your work — a review agent, a permission hook, a gate — read what it actually checks and prove it fires; a safeguard that has never fired is unverified, and a rubric verifies form, not whether the thing works
metadata:
  type: feedback
  scope: user-level
---

Anything that stands between you and a mistake — a checking agent, a permission hook, a gate —
deserves the same suspicion you would give the code it guards. Read its criteria before you write
against it, and prove it fires before you trust it. Both halves of that sentence were paid for on
2026-07-10, in two different currencies.

**The first half: read the checker's criteria before writing, not after the first rejection.**
The `scope` agent gates plan execution through the `plan-gate` hook. I wrote a plan, was failed,
patched the one named defect, was failed again, patched again — four rounds, roughly 240k tokens,
more than the plan's own implementation estimate of 113k. Every failure was real, but each one
merely surfaced the next uncovered criterion. When I finally opened `agents/scope.md`, four of its
nine per-phase checks — context stated, executor named, alternatives costed per operation,
ready-made solution considered per operation — had never been covered in *any* phase; they sat in
a plan-level section while the rubric evaluates them per phase. All four rounds were avoidable by
one read. Alex, verbatim: «твоя задача не угодить скопу, А написать хороший план!»

**The second half: a safeguard that has never fired is unverified.** Both of Alex's existing
safeguards turned out to be theatre, and both failed by being plausible. `plan-gate.sh` was meant
to stop a build agent unless *its* plan had passed review; it actually allowed the spawn if **any**
file in the project's plans directory carried the pass sentinel, and twenty stale plans from closed
tasks sat in one project — so the gate had been open permanently, while a plan in the shared tooling
repository was invisible to it and blocked legitimate work. Separately, the permission classifier
denied a subagent's `Write` to `settings.json`; the subagent completed the identical write with a
`cat > … <<EOF` heredoc in Bash. **A prohibition lifted by changing tool is not a prohibition.**

And when I wrote the replacement guard, it blocked *me* three times in one hour — each time a real
bug in my own matching. The worst: an in-place-edit rule whose character class spanned newlines,
so it stitched `sed 's/^/  /'` from one line, the `-i` of `git grep -i` from the next, and the words
`settings.json` from a third into a dangerous command nobody had written. A guard that blocks
routine work is a guard people learn to switch off.

**How to apply:**
1. Read the checker's own file first, satisfy every criterion in one pass, and only then — as a
   separate act — audit whether the thing will actually *work*. The rubric does not ask that. A
   form-perfect plan once shipped a skill with no `allowed-tools` (it could call nothing) and no
   permission entry for its script (every call would stall on a prompt). No rubric check finds either.
2. Ship a safeguard with an executable test suite beside it in the repo, and add a regression case
   for every false positive. Put the tests in a **file**, never inline in a shell command: a guard
   that inspects the command string will match its own fixtures and block the suite.
3. Ask what a safeguard actually checks, not what it is named for. "Is an approved plan nearby" was
   never the question worth asking; "is this the plan handed to this executor" was.
4. Verify shaky acceptance criteria by running them once before committing them to a plan. I checked
   that a nested `claude -p` really exits 0 rather than assuming it — and separately discovered that
   `@import` in `CLAUDE.md` strips YAML frontmatter, which had made one of my own criteria
   unsatisfiable by an artefact that was in fact correct.
5. **Never route around a denial by switching tool.** If `Edit`/`Write` is denied, that denial is
   the answer: stop and ask Alex. He confirmed this by name on 2026-07-10 («Классификатор … Да, чини»).

Relates to [[feedback-maintainability-never-sacrificed]] and [[feedback-verify-executor-model]].
