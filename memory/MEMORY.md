# User-level memory — Alex (cross-project)

Durable facts about the user and how he wants me to work, shared across **all** projects. Loaded into every session via `@import` from `~/.claude/CLAUDE.md`. Project-specific facts live in each project's own `~/.claude/projects/<slug>/memory/`, not here. Maintained by the `user-profiler` agent.

Each fact reinforces the KB-loop paradigm: deepen understanding, record it on disk, do not execute until "Execute the plan."

- [Be direct, push back, skip praise](feedback_directness.md) — wants disagreement and criticism, not validation or performative compliments; objection sharpens the plan or KB entry, not the chat
- [Write for the reader](feedback_communication_expansive.md) — full human prose (docs too), audience's own vocabulary, no empty slogans, machine IDs kept in a separate "For AI" section; KB entries are durable artifacts, not compressed chat fragments
- [Opus plans, Sonnet implements](feedback_opus_plans_only.md) — Opus produces the full plan; a Sonnet subagent does the build; review together; the plan IS the delivered unit of the loop phase
- [Reuse tooling, don't re-author throwaway scripts](feedback_reusable_tooling.md) — commit a documented helper once instead of throwaway inline scripts each turn; durable tooling lives on disk like KB, not in the ephemeral session
- [Decide before building](feedback_decide_before_building.md) — discuss → decide → then implement; MORE=LESS, a good plan IS the deliverable; gate long/expensive/irreversible actions on a quotable "yes"; this IS the loop in operational form
- [Critic sub-agent is mandatory for strategic output](feedback_reviewer_agent.md) — real adversarial critic Agent (not a self-checklist), run once, Reviewer Notes block; decompose multi-topic research into parallel agents; the critic validates the plan before "Execute the plan"
- [Scope before executing: plan non-trivial work first](feedback_scope_agent.md) — count the ops; mechanical/trivial → do inline; non-trivial → Opus writes a phased resumable on-disk plan, then the `scope` agent checks it and records a PASS/FAIL verdict (with sentinel `<!-- scope:pass -->` on PASS); plan-gate hook blocks build-agent spawns until sentinel is present; >3–4 file ops = split; the checked plan is the required artifact before implementation
