# AI-workflow paradigm — 2026-06-21 (updated 2026-06-22)
Subject: ai-workflow
Status: active

> Filled against the "session document" section of `CLAUDE.md` (status-line rubric + good-description criteria).

## Status line (per-turn — printed in chat AND logged here)

Format: `[<session>] domain NN% · task NN% · plan NN%` — the session name plus how complete my understanding is along the three axes, scored against `current-md-guide.md`. Logged on every answer so the trajectory is visible: rising numbers mean understanding is deepening and I am being useful; a low axis is the cue to ask Alex now rather than proceed.

- 2026-06-22 — [ai-workflow] domain 90% · task 90% · plan 60%
- 2026-06-22 — [ai-workflow] domain 92% · task 92% · plan 62% (sections restructured; scoring guide drafted)
- 2026-06-22 — [ai-workflow] domain 92% · task 94% · plan 62% (good-description criteria sharpened to necessary-and-sufficient + named frameworks)
- 2026-06-22 — [ai-workflow] domain 93% · task 95% · plan 64% (re-read protocol added; Goal made SMART; Solutions now cause-complete)
- 2026-06-22 — [ai-workflow] domain 93% · task 96% · plan 78% (discipline + rubric written inline into CLAUDE.md; guide file folded in)
- 2026-06-22 — [ai-workflow] domain 93% · task 97% · plan 82% (session template finalised; /l semantics clarified; about to commit)

## Problem

This session exposed a recurring failure: I write executable instructions and take actions on a **confidently-wrong mental model**, without first reading the authoritative source on disk or asking Alex. It showed up concretely when I built the six command skills on a wrong model of how session / subject / KB / templates relate. The deeper problem: the standing rule "ask when unsure" does not fire, because my failure mode is being *confidently wrong* — I do not feel unsure, so a trigger that depends on felt uncertainty never trips. And Alex cannot see my understanding from chat; he trusts only artifacts.

## Reason(s) / Cause(s)

- **Completion / efficiency-drive**, strongest in execution-heavy sessions (today was file-production all day): "get the artifact out" outruns "first ground myself."
- **Working against chat / my in-head model instead of the source on disk.** The answer was in `templates/README.md`; I never opened it (same root as fuckups F2, F4, F5).
- **Treating a correction as "patch one line" rather than "the model is wrong — stop and rebuild."**
- **The "ask when unsure" rule is conditioned on felt uncertainty**, which my confident-wrongness evades.

## Glossary & domain context

- **KB** — a *project*. One KB per domain; creating one is a heavy, one-time act done by the `new-kb` skill. `/n` never creates a KB.
- **Session** — a unit of work *inside* an existing KB.
- **`current.md`** — the session's live **mini-KB** and the per-turn working surface; I work against it, not chat. It is what Alex reviews to judge my understanding.
- **subject** — the focus of a session within a project's KB.
- **`templates/`** — templates for sessions/decisions/notes; for sessions, *not* for creating KBs. `kb-skeleton/` is the whole new-KB scaffold used by `new-kb`.
- **`current-md-guide.md`** — the yardstick for scoring the status line and judging a good Problem/Cause/Goal/Solution.
- **Commands** — `/n` enter a session in an existing KB (creates/opens its `current.md`); `/q` answer don't act; `/l` (later) create a NEW session for another subject but stay put — do not switch into it; `/p` plan to disk; `/s` scope-check; `/f` append a miss to fuckups.

## High level Goal

SMART statement of "solved":
- **Specific:** by the end of this session, the current.md + status-line discipline (per-turn re-read, a status line on every answer, scoring against the guide) is written into `CLAUDE.md` and the template.
- **Measurable:** every later answer carries a status line, and `current.md` is updated every turn.
- **Achievable:** edits to `CLAUDE.md`, the template, and the guide — all in this repo.
- **Relevant:** it forces my confident-wrong assumptions into an auditable file before they drive action — the exact failure named in Problem.
- **Time-bound:** this session.

## Solutions (How to fix / resolve)

1. **current.md discipline** — answer every question into it; improve it every turn along domain/task/plan; work against it, not chat.
2. **Status line** every answer (chat + file), scored against `current-md-guide.md` — Alex calibrates me; a low axis triggers me to ask.
3. **Artifacts-only review** — chat is input; the file is the deliverable.
4. **Read the source before writing any executable instruction**; treat a correction as "model wrong — stop and rebuild."
5. Fold the above into a single `CLAUDE.md` section (pending), and place the scoring guide where it is always in context.
6. **Re-read `current.md` every turn and regenerate Open Questions** — each turn, re-read the file and ask what is still missing to make every other section necessary-and-sufficient; that gap is the open questions. This is the concrete cure for the cause "working against my in-head model instead of the disk."

## Implementation plan (if needed)

- `plans/process-layer.md` — DONE.
- `plans/command-layer.md` — FAILED; `/n` and `/l` need rewriting on the corrected model.
- Pending: a consolidated `CLAUDE.md` section for the current.md + status-line discipline, and a decision on where `current-md-guide.md` lives (see Open Questions). Likely direct edits, no separate plan file.

Re-generated every turn by re-reading this file and asking what is still missing to make the other sections necessary-and-sufficient (per the CLAUDE.md rubric).

- `/n` rewrite: what does "orient where in the existing KB to write" mean mechanically? Next step is to read `templates/kb-skeleton/KB-CONVENTIONS.md` and the KB index before rewriting `/n`. → me first, then Alex if unresolved
- Session-folder convention: one evolving `current.md` per subject vs a new dated folder per day (low priority; I chose one evolving). → Alex
- (Resolved this turn: guide/discipline placement = inline in `CLAUDE.md`; `/l` semantics = creates a new session but does not switch into it.)

## Session Decisions

Today (2026-06-22):
- Chat is only Alex's input channel; everything I produce, Alex reviews through artifacts, chiefly `current.md`. (Alex)
- `current.md` is the live per-turn working artifact: every Alex-question answered into it; every answer improves it (domain / task / plan). (Alex)
- Removed "clean Q&A does not require a disk write" from `CLAUDE.md` (line 53) and its twin at line 46. (Alex)
- Clarified in `CLAUDE.md` that every turn targets improving `current.md`; durable conclusions graduate to the subject KB. (Alex)
- Status line on every answer, in BOTH chat and `current.md` — calibration for Alex, usefulness signal for me; also a self-trigger to ask when an axis is low. (Alex)
- Status-line format: `[<session>] domain NN% · task NN% · plan NN%`. (Alex)
- `current.md` section structure: Status line · Problem · Reason(s)/Cause(s) · Glossary & domain context · High level Goal · Solutions (How to fix/resolve) · Implementation plan (if needed) · Open Questions · Session Decisions. (Alex + my reorder)
- A scoring & quality guide (`templates/current-md-guide.md`) defines the axis rubric, good-description criteria, and ideal exemplars; the % is derived by comparing my text to it. (Alex)
- A good description means **necessary and sufficient**, via named frameworks: Problem = gap + consequence; Cause = root-cause by counterfactual (5-Whys + removal test); Goal = SMART; Solution = cause-coverage. A missing necessary criterion caps the matching axis. (Alex)
- **Open Questions is regenerated every turn:** re-read `current.md` each turn and derive the open questions from what is still missing to make the other sections necessary-and-sufficient. Re-reading the file each turn — not trusting my in-head copy — is itself the cure for working against a drifted model. (Alex)
- **The whole discipline + scoring rubric/criteria live inline in `CLAUDE.md`** (not a separate `@import`-ed file); `templates/current-md-guide.md` removed to keep one source and avoid F4-style duplication. (Alex)
- **Session template `templates/current.md` finalised** to the nine-section structure with short framework reminders pointing to the CLAUDE.md rubric. (Alex)
- **`/l` (later)** creates a new session for another subject but does NOT switch into it — the current session stays active; the new one waits to be entered with `/n`. (Alex)
- **`/n` and `/l` skills must work with `current.md`** (create/open the session document); they will be rewritten on this model next. (Alex)
- KB = project (created by `new-kb`); `/n` never creates a KB.

From 2026-06-21 (process-layer, DONE): paradigm written into live `CLAUDE.md`; 7 memory facts re-anchored; templates and `kb/ session/ decisions/` bootstrapped.
