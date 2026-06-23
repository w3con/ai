# User-level memory — Alex (cross-project)

Durable facts about the user and how he wants me to work, shared across **all** projects. Loaded into every session via `@import` from `~/.claude/CLAUDE.md`. Project-specific facts live in each project's own `~/.claude/projects/<slug>/memory/`, not here. Maintained by the `user-profiler` agent.

The core non-negotiable rules — how to write, how to decide and act, and the build and scoping discipline — now live directly in the body of `~/.claude/CLAUDE.md`, not here. This store holds only the remaining situational practices:

- [Reuse tooling, don't re-author throwaway scripts](feedback_reusable_tooling.md) — commit a documented helper once instead of re-writing throwaway inline scripts each turn
- [Critic and research sub-agents only on Alex's word](feedback_reviewer_agent.md) — stress-test strategic output with a real adversarial critic, but never auto-spawn any sub-agent; spawning is gated and needs Alex's go
- [Stage exactly your own files, never blind `git add -A`](feedback_git_staging.md) — commit only the paths this task changed; the tree may carry prior-session or parallel-agent changes
