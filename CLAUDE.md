# User-level profile & working style

Durable preferences about the user (Alex) and how he wants me to work, applied across **every** project. The granular store is `~/.claude/memory/` (one fact per file, maintained by the `user-profiler` agent); the files below are imported so they load in every session. Project-specific facts stay in each project's own memory directory, not here.

To keep these from drifting: edit the fact files in `~/.claude/memory/`, update that directory's `MEMORY.md` index, and add an `@import` line below for any new user-level fact.

@/Users/tknff/.claude/memory/feedback_directness.md
@/Users/tknff/.claude/memory/feedback_communication_expansive.md
@/Users/tknff/.claude/memory/feedback_opus_plans_only.md
@/Users/tknff/.claude/memory/feedback_reusable_tooling.md
@/Users/tknff/.claude/memory/feedback_decide_before_building.md
@/Users/tknff/.claude/memory/feedback_reviewer_agent.md
@/Users/tknff/.claude/memory/feedback_scope_agent.md
# Scoping — plan non-trivial tasks before executing
Before executing any non-trivial task — anything touching more than 2–3 files, involving several distinct steps, or carrying real risk of session exhaustion — delegate to the **`scope`** agent (`~/.claude/agents/scope.md`) FIRST. It writes a phased, resumable plan to `~/.claude/plans/<slug>.md` (one file per task — no shared `current.md`, so parallel tasks never overwrite each other); I then show that plan to the user and get approval **before any implementation begins**. Trivial tasks (a one-line fix, a single known small edit) I execute directly — no plan ceremony. The on-disk plan, not a commit, is the resume checkpoint; commits happen only when the whole task is done, and the plan file is deleted once the task is closed. To resume after a session dies, glob `~/.claude/plans/*.md` and read any plan whose status is not `DONE`. This rule exists because a monolithic agent spawn once hit its session limit having produced nothing — see [[feedback_scope_agent]].
