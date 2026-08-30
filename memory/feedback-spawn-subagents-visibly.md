---
name: feedback-spawn-subagents-visibly
description: Every subagent without exception — executor, critic, gatherer, tracer, acceptor, researcher — runs in the foreground where Alex watches its turns; never a wrapper script, never a detached or background run.
metadata:
  type: feedback
---

Every subagent runs in the foreground, raised by a visible `Agent` call in the session itself. Before it runs, say plainly which agent is being raised and what it is being asked to do; then raise it and stay with it. Never `Workflow`, never `Agent` with an `isolation` or background mode, never a shell command backgrounded with `run_in_background`, and never a wrapper script or project command that raises an agent inside itself and hands back only the answer.

**There is no read-only exception any more, corrected 2026-08-31.** An earlier version of this file, written 2026-08-18, exempted read-only readings — critics, checkers, gatherers — on the reasoning that they edit nothing and cost little. That carve-out is withdrawn on Alex's word. He gave the order a third time, in anger, when `bin/work-critic` raised its critic through its own `subprocess.run` in the very next command after a card had just landed the rule; and worse, the rule that card landed had a clause I wrote myself declaring exactly that shape acceptable. A blocking subprocess call is not foreground: by the time the command returns, the run is finished and paid for, and Alex saw none of it.

**Why:** an agent he cannot see is an agent he cannot stop, cannot pace and cannot redirect while changing course is still cheap. That is true of a reading agent as much as of an executor — a critic reading burns real tokens and produces an answer he might have wanted framed differently. Softer wordings failed three times to stop this; there is nothing left to soften.

**How to apply:** name the agent and its task in the message before the spawn, then spawn it with the visible `Agent` tool. Where a project command would raise an agent by its own hand, it must print the prompt and the file the answer becomes, and let the session raise the agent — in the Validité application repository `bin/work-critic`, `bin/work-map`, `bin/work-trace` and `bin/work-accept` each do this when `CLAUDECODE` is set, and take the answer back through a `--record <file>` flag. A command that still raises an agent itself from inside a session is a defect to fix, not a permission to use it.

**One thing this rule does not cover, settled on 2026-08-20.** When the ordinary `Agent` tool call returns saying the agent "is working in the background", that is only how the tool reports itself back to me — Alex still watches that agent's turns as they happen in his own terminal, and he confirmed it in those words. So a plain `Agent` spawn, with no `isolation` or background flag of my own, satisfies this rule in full, and there is nothing to apologise for or warn him about.

This is about *visibility*, a different question from [[feedback_reviewer_agent]], which governs *permission* to spawn at all, and from [[feedback-verify-executor-model]], which governs *which model* actually ran the work.
