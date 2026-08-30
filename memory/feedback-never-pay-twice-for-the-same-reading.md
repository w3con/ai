---
name: feedback-never-pay-twice-for-the-same-reading
description: An agent's answer that already exists is never bought a second time — recover it and finish the mechanical tail by hand
metadata:
  type: feedback
---

When a paid agent has already read the work and given its answer, and the pipeline then fails on machinery around that answer — a matcher, a format check, a bad exit code — the fix never includes raising the same agent again. Repair the machinery, recover the existing answer from wherever it landed (a rejection file, git history, a transcript), and finish the remaining mechanical steps by hand: the merge, the checks, the closing file, the push, the cleanup.

**Why:** on 2026-08-31 an acceptor read HRN-57, answered every finding and ended with «ИТОГ: принято». `bin/work-accept` refused it anyway because the acceptor had written `**attention 1.**` and the matcher wanted `attention 1.` unadorned. I fixed the matcher, deleted the rejection file and re-ran the whole tail, which would have raised the tracer and the acceptor a second time on unchanged work. Alex stopped it mid-call: «какую нахуй перезапускать приемку!?!?», then «руками все сам доделай». The reading was already bought; buying it again pays for nothing, and re-running a pipeline command is not the only way to reach its outcome.

**How to apply:** when a pipeline stops on its own machinery rather than on the work, ask what the command would have done next and do exactly that yourself — `git merge --squash` and a commit through the real pre-commit hook, the closing file written by hand carrying the recovered answer verbatim plus a plain note of what was folded by hand and why, then the push and the worktree removal. Do not reach for a test seam (`WORK_ACCEPT_CMD` and its siblings) to feed the old answer back through the command: that is theatre around the same result and Alex reads it as re-running the thing he just stopped.

Related: [[feedback-run-the-card-means-the-whole-pipeline]] says one word authorises the whole conveyor; this one says the conveyor is never run twice over the same reading. [[feedback_reviewer_agent]] governs whether an agent may be raised at all.
