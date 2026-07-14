# Memory — Alex, one store for every project

Durable facts about how Alex wants me to work. **There is exactly one memory store**, this one, at
`~/Dev/ai/memory/`; it is under version control and reaches every project and both machines. Each
`~/.claude/projects/<slug>/memory` is a symlink to this directory, so writing "to a project's
memory" writes here — and the `memory-store-guard` hook refuses any write that lands anywhere else.

**What belongs here:** how Claude works — what Alex requires, where he corrected me, which tool to
use for what. This is by nature not owned by any project.

**What does not:** what a *project* decided — its architecture, its trade-offs. Those go to that
project's own `ai/decisions/` and `ai/arch/`, where they are versioned with the code and readable
by a human, not only by me. Plans likewise stay in the project they describe.

A memory that is about method but only true inside one project carries a `scope:` field in its
frontmatter and says so in its description. That is the whole mechanism; no second store is needed.

The core non-negotiable rules — how to write, how to decide and act, and the build and scoping
discipline — live in the body of `~/.claude/CLAUDE.md`, not here. This store holds the rest.

- [Maintainability never sacrificed](feedback-maintainability-never-sacrificed.md) — Alex's standing order: clarity beats everything, contest even his own instructions when they would trade it away
- [Check the checker](feedback-check-the-checker.md) — read a gate's criteria before writing against it, prove a safeguard actually fires before trusting it, and never route around a denial by switching tool
- [Verify the executor's model](feedback-verify-executor-model.md) — resuming a subagent silently moves it onto the session model; read the transcript's model field, never ask the agent
- [Critic and research sub-agents](feedback_reviewer_agent.md) — whether you may spawn one at all: only on Alex's explicit word, never automatically
- [Reusable tooling](feedback_reusable_tooling.md) — commit the helper once as a documented script; a script decides what happens, a skill decides when to call it
- [Stage exactly your own files](feedback_git_staging.md) — commit by naming paths; a blind `git add -A` sweeps in other sessions' work
- [Record only confirmed decisions](record-only-confirmed-decisions.md) — proposals stay in chat; nothing lands in a durable record until Alex confirms it
- [No lazy defaults](feedback_no_lazy_defaults.md) — when pressed for a decision, don't collapse to "do everything / do nothing"; do the discriminating work and give the tiered call
- [The AI config repo](reference_ai_config_repo.md) — the versioned source of truth is `~/Dev/ai`; commit configuration there, never straight into `~/.claude`
- [Reproduce the design, don't improvise](design-reproduce-not-improvise.md) — Validité website only: match the design files exactly, interview to full clarity first
- [Enter the knowledge base through its index](kb-entry-via-index.md) — Validité knowledge base only: start at `kb/_index.md`, never a blind grep
