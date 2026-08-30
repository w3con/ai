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

Everything about **how to write** — to Alex, in a document, or in a letter to somebody outside the team — lives in `../STYLE.md` and in no other file, this index included. A style rule must never be recorded here; `bin/style-check` fails the deploy when one is.

The core non-negotiable rules on how to decide and act, and the build and scoping discipline, live
in the body of `~/.claude/CLAUDE.md`, not here. This store holds the rest.

- [Do nothing unasked](feedback-do-nothing-unasked.md) — Alex's standing order: do only what was explicitly requested, name anything else and ask before doing it, and touch nothing outside the request
- [Maintainability never sacrificed](feedback-maintainability-never-sacrificed.md) — Alex's standing order: clarity beats everything, contest even his own instructions when they would trade it away
- [Check the checker](feedback-check-the-checker.md) — read a gate's criteria before writing against it, prove a safeguard actually fires before trusting it, and never route around a denial by switching tool
- [Never pipe a checking tool through tail](never-pipe-a-checking-tool-through-tail.md) — `| tail` cuts the verdict and replaces the exit code with the pager's; redirect to a file and read `$?`
- [Verify the executor's model](feedback-verify-executor-model.md) — reuse across phases is permitted again since the vendor fixed the model-drift defect on 2026-08-01, but an agent's self-report about its own model still proves nothing; read the transcript's model field when it matters, never ask the agent
- [One task per session](feedback-one-task-per-session.md) — one task per session so the conversation stays disposable and `/rewind` is safe; parallel work in a separate session cut by `bin/session-start` (`/new`); and cut the number of tool calls, since each one re-sends the whole context
- [Pace with visible progress](feedback-pacing-visible-progress.md) — don't burn 8 minutes in silent thinking then emit a one-liner; act in short visible steps, don't re-plan from scratch each async message
- [Caffeinate before long runs](feedback-caffeinate-before-long-runs.md) — start caffeinate when you hand work over, not after the first agent dies; a sleeping Mac kills every executor at once
- [Critic and research sub-agents](feedback_reviewer_agent.md) — whether you may spawn one at all: only on Alex's explicit word, never automatically
- [Spawn subagents visibly](feedback-spawn-subagents-visibly.md) — executor subagents ALWAYS foreground, never background/wrapper; read-only agents (critic, checker) are not covered
- [See a problem, found a card](feedback-see-a-problem-found-a-card.md) — found it the moment you notice it and never merely propose it; but a small reversible machinery repair inside work you are already doing is fixed now and recorded in one line, not carded
- [Never report your own problems](feedback-never-report-your-own-problems.md) — a problem you caused or a leftover you could finish is yours to solve, record and card up; never hand it back as a question
- [Resolve before reporting](feedback-resolve-before-reporting.md) — a blocked commit, a dirty tree, a missing tool is yours to fix; never hand Alex an obstacle you have not tried to clear
- [Report broken tooling at once](feedback-report-broken-tooling.md) — a script, hook, skill, command or server that is missing or misconfigured gets one line in the same answer, even when a fallback quietly produced the result
- [Install what you need](feedback-install-what-you-need.md) — a missing tool gets installed, not reported and waited on; destructive or outward-facing actions still need his word
- [Test runs must not reach the user](feedback-test-runs-must-not-reach-the-user.md) — make sending opt-in behind a flag before an executor iterates on anything that delivers to a real person; kill a loose agent, don't message it
- [Reusable tooling](feedback_reusable_tooling.md) — commit the helper once as a documented script; a script decides what happens, a skill decides when to call it
- [Stage exactly your own files](feedback_git_staging.md) — commit by naming paths; a blind `git add -A` sweeps in other sessions' work
- [Commit by naming paths](feedback-commit-by-naming-paths.md) — never `git add` then `git commit`; a parallel session's blind stage takes whatever sits staged in a shared checkout
- [Commit periodically](feedback-commit-periodically.md) — land work at each milestone and remind Alex, don't let uncommitted changes pile up for hours
- [Approve the letter before writing it down](feedback-approve-letter-before-writing-it-down.md) — a letter lives in the chat message until Alex approves the text; only then does it reach the drafts page, the card and the tracker
- [Record only confirmed decisions](record-only-confirmed-decisions.md) — proposals stay in chat; nothing lands in a durable record until Alex confirms it
- [Four edge questions before the critic](feedback-plan-edges-before-critic.md) — landing moment, unreachable branches, measurable gates, which bytes exactly; run them on your own plan before spending a critic on it
- [Questions first, silence, one report](feedback-questions-first-silence-then-report.md) — ask everything before the first edit, build without a word, hand over one report with the findings, the decisions taken alone and the mistakes with their fixes
- [No lazy defaults](feedback_no_lazy_defaults.md) — when pressed for a decision, don't collapse to "do everything / do nothing"; do the discriminating work and give the tiered call
- [Decide technical details yourself](feedback-decide-technical-details-yourself.md) — never hand Alex a choice with no product consequence; choose on the merits, act, and tell him afterwards
- [Never size work in human hours](feedback-no-human-hour-estimates.md) — agents build everything here; argue about context, file collisions and what's on the path, never "it's sixty hours" or "it's too big"
- [The AI config repo](reference_ai_config_repo.md) — the versioned source of truth is `~/Dev/ai`; commit configuration there, never straight into `~/.claude`
- [Reproduce the design, don't improvise](design-reproduce-not-improvise.md) — Validité website only: match the design files exactly, interview to full clarity first
- [Enter the knowledge base through its index](kb-entry-via-index.md) — Validité knowledge base only: start at `kb/_index.md`, never a blind grep
- [Size a card to one executor](feedback-executor-card-size.md) — one card ≈ one phase and one toolchain; swap agents at a phase boundary, never mid-phase, and never on the last checkpoint where the check output still lives only in the agent's context
- [Parallel executors in a shared tree](feedback-parallel-executors-shared-tree.md) — overlap only across disjoint toolchains (frontend+backend), never two same-language gates; else give each a worktree
- [Browser-verify: rAF sleeps in a background tab](browser-verify-raf-background-tab.md) — canvas/preview renders (and blob-download checks) need the tab foregrounded via a screenshot
- [Living plan-journal, verify-first](feedback-living-plan-journal.md) — discuss and re-check against live systems before acting; keep a KB roadmap+journal per effort and update it as understanding grows
- [Pilier's internal KB is a private repo](feedback_pilier_private_kb.md) — Pilier only: the blockchain repo is public, so internal reasoning/plans/decisions live in the private `cloud` repo (`pilier-org/cloud`) — read it for context and write internal docs there, never into `blockchain/ai/`
- [Check both send routes](feedback-check-both-send-routes.md) — Validité only: a staged letter may already be sent from at@validite.eu or from the personal Gmail; open the message, never judge from a subject line
- [Check who wrote the letter](feedback-check-if-letter-was-agent-written.md) — before filing a quote as evidence, ask whether a person or an assistant wrote it and whether it only echoes our own framing back; grade the quote in the same line
- [Warmth isn't a commitment signal](feedback-warmth-not-a-commitment-signal.md) — a pleasant, enthusiastic-sounding call means nothing on its own; log names/dates/documents, not tone, and don't pin it on one contact's character
- [App: no real data yet, and DB access exists](project_app_no_real_data_yet.md) — the Validité DPP application repository only: only test/demo records exist so far, and the coordinator CAN reach Mongo directly via docker exec — never repeat an old plan's "no access" claim untested
- [A reported failure is a work order](feedback-reported-failure-is-a-work-order.md) — when Alex pastes a broken deploy or build, start the fix and report it; do not ask whether to begin
- [Clone config verbatim](feedback-clone-config-verbatim.md) — deriving a new node/service config from an already-proven twin: copy the proven flags/values byte-for-byte, don't re-derive by reasoning about names
- [Verify repo vs live](feedback_pilier_verify_repo_vs_live.md) — Pilier only: before changing/auditing server config, diff the tracked file against the live host, don't trust the repo copy alone
- [A clean merge is not agreement](feedback-clean-merge-is-not-agreement.md) — no conflict only means the two sides edited different files; compare what each side's work produces
- [Python on the SSD machine](machine-ssd-python-path.md) — prepending Homebrew to PATH swaps in an interpreter without PyYAML and fakes a regression.
- [No tests for the cockpit](feedback-no-tests-for-the-cockpit.md) — Validité app only: the owner works that screen himself; fix what is broken, never add browser checks around it unasked
- [A description explains how it works](feedback-description-explains-how-it-works.md) — Validité app cards: the description must leave Alex understanding how the thing works and why; the plan-repair story stays out, the reasons stay in
