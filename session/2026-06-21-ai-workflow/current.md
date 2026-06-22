# AI-workflow paradigm — 2026-06-21 (updated 2026-06-22)
Subject: ai-workflow
Status: active

> Filled against the "session document" section of `CLAUDE.md` (status-line rubric + good-description criteria). Re-read this file every turn before writing.

## Status line (printed in chat AND kept here — current only)

Format: `[<session>] domain NN% · task NN% · plan NN%`, scored against the CLAUDE.md rubric and replaced every answer (no history); a low axis is the cue to ask Alex now rather than proceed.

`[ai-workflow] domain 92% · task 92% · plan 80%`

## Problem

This session exposed a recurring failure: I write executable instructions and take actions on a **confidently-wrong mental model**, without first reading the authoritative source on disk or asking Alex. It showed up concretely when I built the six command skills on a wrong model of how session / subject / KB / templates relate. The deeper problem: the standing rule "ask when unsure" does not fire, because my failure mode is being *confidently wrong* — I do not feel unsure, so a trigger that depends on felt uncertainty never trips. And Alex cannot see my understanding from chat; he trusts only artifacts.

## Reason(s) / Cause(s)

- **Completion / efficiency-drive**, strongest in execution-heavy sessions (today was file-production all day): "get the artifact out" outruns "first ground myself."
- **Working against chat / my in-head model instead of the source on disk.** The answer was in `templates/README.md`; I never opened it (same root as fuckups F2, F4, F5).
- **I keep producing substance in chat and not writing it into `current.md`.** This very session: the verification findings, the decisions, and the open questions lived in chat while the file went stale and even lost its `## Open Questions` header. The discipline is only as real as the writing; producing in chat *is* the failure.
- **Treating a correction as "patch one line" rather than "the model is wrong — stop and rebuild."**
- **The "ask when unsure" rule is conditioned on felt uncertainty**, which my confident-wrongness evades.

## Glossary & domain context

- **KB** — a *project*. One KB per domain; creating one is a heavy, one-time act done by the `new-kb` skill. `/n` never creates a KB.
- **Session** — a unit of work *inside* an existing KB.
- **`current.md`** — the session's live **mini-KB** and the per-turn working surface; I work against it, not chat. It is what Alex reviews to judge my understanding.
- **subject** — the focus of a session within a project's KB.
- **`templates/`** — templates for sessions/decisions/notes; for sessions, *not* for creating KBs. `kb-skeleton/` is the whole new-KB scaffold used by `new-kb`.
- **harvest** — the abandoned two-step "stage takeaways then promote to KB" idea (decisions.md, 2026-06-20); superseded by writing straight to KB/decisions. Its save-to-KB *action* is being revived as the `/k` command + the "Knowledge saved" section.
- **Commands** — `/n` enter a session in an existing KB (creates/opens its `current.md`); `/q` answer don't act; `/l` (later) create a NEW session for another subject but stay put — do not switch into it; `/p` plan to disk; `/s` scope-check; `/f` append a miss to fuckups; `/k` (proposed) save the current understanding to the KB.

## High level Goal

SMART statement of "solved":
- **Specific:** by the end of this session, the current.md + status-line discipline (per-turn re-read, a status line on every answer, scoring against the rubric) is written into `CLAUDE.md` and the template, and the command layer works when launched in a real project.
- **Measurable:** every later answer carries a status line, `current.md` is updated every turn, and `/n` run in a domain project creates the session document and orients without error.
- **Achievable:** edits to `CLAUDE.md`, the template, and the skills — all in this repo.
- **Relevant:** it forces my confident-wrong assumptions into an auditable file before they drive action — the exact failure named in Problem.
- **Time-bound:** this session.

## Solutions (How to fix / resolve)

1. **current.md discipline** — answer every question into it; improve it every turn along domain/task/plan; work against it, not chat.
2. **Status line** every answer (chat + file), scored against the `CLAUDE.md` rubric — Alex calibrates me; a low axis triggers me to ask.
3. **Artifacts-only review** — chat is input; the file is the deliverable.
4. **Read the source before writing any executable instruction**; treat a correction as "model wrong — stop and rebuild."
5. The discipline + rubric now live inline in the `CLAUDE.md` "session document" section (one source).
6. **Re-read `current.md` every turn and regenerate Open Questions** — re-read, then list what is missing to make each section necessary and sufficient. The cure for "working against my in-head model instead of the disk."
7. **`/k` command + "Knowledge saved" section** — make the save-to-KB step an explicit, logged action, since I will not do it reliably on my own.

## Implementation plan (if needed)

- `plans/process-layer.md` — DONE.
- `plans/command-layer.md` — DONE for the six skills, but verification found the command layer is **not yet usable in a real project** (see Findings); the path fix and `/k` are pending Alex's layout decision.
- No separate plan file for the remaining fixes yet; likely direct edits once the layout is decided.
- **A hook to enforce the per-turn discipline mechanically** — checks every turn that `current.md` changed; if not, blocks. Relying on my behaviour is unreliable by design, so this is enforced, not trusted. **Design (built this turn):** a pair of hooks — `session-snapshot.sh` (UserPromptSubmit) snapshots the active `current.md`'s sha256 at turn start; `session-write-gate.sh` (Stop) recomputes at turn end and `exit 2` (block) if unchanged. Loop-safe via `stop_hook_active`; finds the file under both `session/*` and `ai/session/*` layouts. **Status: tested 6/6 green (snapshot runs; unchanged→block; changed→allow; loop-safe; inert when no active session; bypass works) and WIRED into `settings.json` (`UserPromptSubmit` + `Stop`), valid JSON confirmed. Documented in the CLAUDE.md "session document" section. **Caveat: `settings.json` is read at session start, so the hook takes effect after a restart (like the earlier matcher change), not mid-conversation. After restart, every turn is gated.**

## Findings (new problems discovered this session)

Problems uncovered while verifying that `/n` will work in a new session — not the session's original Problem, but defects found along the way:

1. **The AI repo has no KB.** `kb/` holds only `_raw/`; there is no `kb/_index.md`. So `/n`'s step 2 ("read `kb/_index.md` to orient where to write") has nothing to read here. (Verified by `ls kb/`.)
2. **The `/n` skill's paths are not portable.** It uses bare `session/`, `kb/`, `templates/`, which match the AI repo's root-level layout but contradict `CLAUDE.md`'s stated `<project>/ai/{kb,session,decisions,plans}` layout. In a real domain project `/n` would create `session/` at the project root instead of `ai/session/`, and `templates/current.md` would not resolve at all (templates live only in the AI repo). So `/n` works in the AI repo but breaks in a real project.
3. **The harvest function is lost as an action.** The model says "durable conclusions graduate to KB," but nothing triggers it and there is no KB here. Being addressed by `/k` + the "Knowledge saved" section.

## Open Questions

Re-generated every turn by re-reading this file (per the CLAUDE.md rubric).

- **Canonical file layout** — project files under `<project>/ai/` (as `CLAUDE.md` says) or at repo root (as the AI repo does)? This blocks fixing `/n` paths and writing `/k`. → Alex
- Section-criteria for the sections without them + the two completeness gates (ready-to-plan / ready-to-implement) are proposed but not yet written into `CLAUDE.md` (Glossary criterion now sharpened). → pending Alex's nod to write
- Session-folder convention: one evolving `current.md` per subject vs a new dated folder per day (low). → Alex
- **Hook — remaining before live:** test both scripts (changed→allow, unchanged→block, loop-safe), then wire `UserPromptSubmit` + `Stop` into `settings.json`. Live firing can only be confirmed on Alex's next message. → me (test), then wire
- (Resolved: `/n` and `/l` rewritten; status line current-only; `/k` agreed in principle; "Knowledge saved" and "Findings" sections added.)

## Session Decisions

Today (2026-06-22):
- Chat is only Alex's input channel; everything I produce, Alex reviews through artifacts, chiefly `current.md`. (Alex)
- `current.md` is the live per-turn working artifact: every Alex-question answered into it; every answer improves it (domain / task / plan). (Alex)
- Removed "clean Q&A does not require a disk write" from `CLAUDE.md`. (Alex)
- Every turn targets improving `current.md`; durable conclusions graduate to the subject KB. (Alex)
- Status line on every answer, in BOTH chat and `current.md`; format `[<session>] domain NN% · task NN% · plan NN%`; **current only, no history**. (Alex)
- A good description means **necessary and sufficient**, via named frameworks: Problem = gap + consequence; Cause = root-cause by counterfactual (5-Whys + removal test); Goal = SMART; Solution = cause-coverage. (Alex)
- **Sharpened Glossary criterion:** define every term in the project's vocabulary the doc uses — *including the obvious-feeling ones* — because the terms that burned us all felt obvious while wrong; the trigger is "names something project-specific," not my judgment of "misreadable." (Alex)
- **Open Questions is regenerated every turn** by re-reading the file. (Alex)
- The discipline + scoring rubric live **inline in `CLAUDE.md`**; `templates/current-md-guide.md` removed to keep one source. (Alex)
- `templates/current.md` finalised to the section structure with framework reminders pointing to the CLAUDE.md rubric. (Alex)
- **`/l` (later)** creates a new session for another subject but does NOT switch into it. **`/n`** opens `session/<date>-<slug>/current.md` (`Status: active`), orients via `kb/_index.md`, loads `decisions/<slug>.md` + plan; never creates a KB. (Alex)
- **New mandatory section "Knowledge saved to KB"** — append-only log of what was promoted to a KB; empty = reminder a save is owed. (Alex)
- **New section "Findings (new problems discovered this session)"** — home for defects/facts surfaced mid-session, so they land in the file, not chat. (Alex)
- **`/k` (save to KB)** added in principle as the seventh command. (Alex)
- **Per-turn file-change enforcement must be a HOOK, not my discipline** — Alex: I am principally incapable of reliably writing to the file, so enforce it mechanically; a hook checks every turn that `current.md` changed. (Alex)
- **The hook BLOCKS (hard), not warns** — Alex: "чтобы у тебя НИКОГДА не было возможности ответить в чат без изменения файла." Stop hook `exit 2` until `current.md` changes. (Alex)
- **Hook built, tested (6/6) and wired** — `hooks/session-snapshot.sh` (UserPromptSubmit) + `hooks/session-write-gate.sh` (Stop) in `settings.json`; documented in CLAUDE.md. Effective after a session restart (settings load at startup). Bypass: `CLAUDE_GATE_BYPASS=1`.
- **All session work committed** — discipline + rubric, `/n`/`/l` rewrite, command-layer DONE, Findings + Knowledge-saved sections, the enforcement hook and `settings.json`. (Alex: "коммить все")
- KB = project (created by `new-kb`); `/n` never creates a KB.

From 2026-06-21 (process-layer, DONE): paradigm written into live `CLAUDE.md`; 7 memory facts re-anchored; templates and `kb/ session/ decisions/` bootstrapped.

## Knowledge saved to KB

Append-only log of what was promoted to a KB this session (date · what · link).

- Nothing saved to a `kb/` wiki this session — the AI repo has no `kb/`. Durable conclusions went instead to `decisions.md` (the ai-workflow why-log) and `CLAUDE.md` (rules). This empty-by-design state is exactly the reminder the section exists to give: in a domain project, `/k` saves would be logged here.
