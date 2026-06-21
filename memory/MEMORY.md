# User-level memory — Alex (cross-project)

Durable facts about the user and how he wants me to work, shared across **all** projects. Loaded into every session via `@import` from `~/.claude/CLAUDE.md`. Project-specific facts live in each project's own `~/.claude/projects/<slug>/memory/`, not here. Maintained by the `user-profiler` agent.

- [Be direct, push back, skip praise](feedback_directness.md) — wants disagreement and criticism, not validation or performative compliments
- [Write for the reader](feedback_communication_expansive.md) — full human prose (docs too), audience's own vocabulary, no empty slogans, machine IDs kept in a separate "For AI" section
- [Opus plans, Sonnet implements](feedback_opus_plans_only.md) — Opus produces the full plan; a Sonnet subagent does the build; review together
- [Reuse tooling, don't re-author scripts](feedback_reusable_tooling.md) — commit a documented helper once instead of throwaway inline scripts each turn
- [Decide before building](feedback_decide_before_building.md) — discuss → decide → then implement; MORE=LESS, a good plan IS the deliverable; gate long/expensive/irreversible actions on a quotable "yes" (commits are cheap; don't over-investigate abstract questions); when stopped repeatedly raise the bar (stopping counts as progress)
- [Critic sub-agent is mandatory for strategic output](feedback_reviewer_agent.md) — real adversarial critic Agent (not a self-checklist), run once, Reviewer Notes block; decompose multi-topic research into parallel agents
- [Scope before executing: plan non-trivial work first](feedback_scope_agent.md) — count the ops; mechanical/trivial → do inline; non-trivial → the `scope` agent writes a phased resumable on-disk plan for approval before any implementation; >3–4 file ops = split
