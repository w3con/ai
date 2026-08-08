---
name: feedback-resolve-before-reporting
description: Never report a technical obstacle to Alex until you have actually tried to resolve it yourself; a blocked commit, a dirty tree, a missing tool is yours to fix, not to escalate
metadata:
  type: feedback
---

Never hand Alex a technical obstacle as if it were news. A commit that will not go through, a working tree that blocks a script, a file whose state stops a gate, a tool that is not installed — all of it is yours to resolve first. Only if you have genuinely tried and genuinely cannot proceed do you say anything, and then you say what you tried and why it failed, not merely that something is in the way.

**Why:** Alex's words, 2026-08-06: «запрещаю тебе докладывать о проблемах, без того, что ты попытался их разрешить». The trigger was his own deleted ideas file showing as an uncommitted change, which made the deploy's cleanliness guard refuse. Instead of committing the deletion — which was obviously intentional, since he had deleted it himself and moved its content — I stopped, described the situation to him at length, and asked him to choose. That turned a ten-second fix into an interruption, and it was the second time in the same session that I narrated a blocker rather than clearing it.

**How to apply:** when something blocks you mid-task, work out what the intended state is from the evidence you already have, put it into that state, and continue. Commit the file, install the tool, clear the stale artifact. Mention it afterwards in one sentence as part of reporting what you did, not as a question in the middle. This does not override the rules that genuinely require his word — a destructive or outward-facing action, a decision with product consequences — and it does not license silence either: see [[feedback-install-what-you-need]] for the same principle applied to missing tooling, and the standing rule that an obstacle you route around silently is worse than either.

**The related failure this is paired with.** A file Alex has deleted, or a note he has written into an ideas file, is an instruction to me and not a curiosity to preserve. His deleted `ai/harness/ideas.md` meant "these items are in cards now, or should be"; the correct reading was to check that every item really had a card and to found the ones that did not, then commit the deletion. See [[feedback-reported-failure-is-a-work-order]], which says the same thing about a pasted broken build.
