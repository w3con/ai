---
name: feedback-scope-agent
description: Scope and phase non-trivial work before executing — count the ops, do mechanical/trivial work inline, and for anything non-trivial let the scope agent write a phased on-disk plan for approval before any implementation
metadata:
  type: feedback
  scope: user-level
---

Two facets of one rule: **estimate the size of the work before you spawn anything, and never start a non-trivial build without a phased plan on disk.**

**Triage — count the operations first.** Before spawning any subagent, count explicitly: how many files will it read, how many will it write and how large, does any single file exceed ~1000 lines of reading + rewriting? Mechanical writes whose content is already decided (config files, templates, small scripts) → do them directly with Edit/Write, not via an agent. One agent = one focused task (a CSS audit, or a translation — not both). If it takes more than one sentence to describe what the agent will write, it is too much: split it.

**Non-trivial work → the `scope` agent.** Before executing any non-trivial task — more than 2–3 files, several distinct steps, or real risk of session exhaustion — delegate to the **`scope`** agent (`~/.claude/agents/scope.md`). It analyzes the task for completeness gaps and action-creep, atomizes it into small resumable phases (each = one on-disk artifact + concrete acceptance criteria + required context + token estimate + executor), and writes the plan to `~/.claude/plans/<slug>.md` — one file per task, kebab-slug name, so parallel tasks never overwrite each other (there is no shared `current.md`). I then show that plan to the user and get explicit approval **before writing a single line of implementation**.

Trivial tasks (a one-line fix, a single known small edit) I execute directly — no plan ceremony. The triage decision (trivial vs not) stays with me, the orchestrator; calling the agent for a trivial task is itself wasted tokens.

**Why:** a single agent was once spawned to do 10+ file operations (rewrite a 5521-line CSS file + two full French translations + 6 new files). It hit its session limit having produced nothing — the user's tokens fully wasted. Root cause: monolithic execution with no on-disk plan to resume from and no per-phase verification.

**How to apply:**
- The on-disk plan, not a git commit, is the resume checkpoint. One file per task at `~/.claude/plans/<slug>.md`; to resume after a session dies, glob `~/.claude/plans/*.md` and read any plan whose status is not `DONE`. The plan file is deleted once the task is closed (committed) — no archive.
- Commit only when the WHOLE task is done — never per phase or per atomic write.
- Each phase must be small enough to survive a mid-task session death. >3–4 substantial file ops in one phase = split it.
- A phase is not a spawn: one Sonnet spawn can carry several consecutive phases so the ~10–20k cold-start overhead is paid once, not per phase. Choose the executor by comparing work against spawn overhead — delegate only when the batch amortizes it, needs context isolation, or benefits from parallelism; otherwise the orchestrator does it inline (running a known script, a trivial edit). Real build work (pages, translations, code) still goes to Sonnet. Token estimates for delegated phases must include the spawn overhead.
- A hard-gate PreToolUse hook (block Agent calls without an approved plan) was considered and deferred — the behavioral rule comes first; add the hook only if I keep forgetting. Relates to [[feedback_opus_plans_only]] and [[feedback_decide_before_building]].

**Paradigm connection:** a phased, resumable on-disk plan is the required artifact that the plan-arm of the loop produces. Without it, "Execute the plan" has nothing to gate against and the loop has no durable checkpoint. The triage logic (count ops; trivial → inline; non-trivial → phased plan) is how the loop stays proportionate: not every question needs a plan, but every non-trivial build does, and that plan must exist on disk before implementation starts.
