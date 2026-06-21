# AI-workflow paradigm — 2026-06-21
Subject: ai-workflow
Status: active

## Task / understanding

We are migrating the AI operating paradigm from draft and chat history into live, versioned, on-disk form. The core work this session is `process-layer`: write the KB-loop paradigm into the live `CLAUDE.md`, create the `kb/session/decisions/` structure, re-anchor the 7 memory facts to the paradigm, and seed this session document. The repo at `/Volumes/SSD/Dev/ai` is already the symlinked source of truth for `~/.claude/` (migration done at commit e83d799).

The paradigm: LOOP (understand → gather → plan) is the default state; the only exit is "Execute the plan." KB is the north star — every drive gets redirected into a KB update or a plan update, never into premature action.

## Domain knowledge (gathered this session)

- **Repo structure:** `/Volumes/SSD/Dev/ai` symlinked into `~/.claude/`; `CLAUDE.md`, `memory/`, `agents/`, `hooks/`, `skills/` all live here.
- **Four-plan queue:** `repo-migration` (DONE, commit e83d799), `process-layer` (THIS PLAN, APPROVED), `scope-reviewer-redesign` (next — changes the role of `scope` from plan-author to plan-checker), `command-layer` (after that — the `/_n`, `/_l`, `/_q` command vocabulary).
- **KB-loop paradigm:** confirmed in `CLAUDE.draft.md` and `decisions.md` (entries 2026-06-20 and 2026-06-21). Two modes in practice: LOOP (default) and Execution (gated by "Execute the plan"). Ambient vs `/_n` are emphases within the loop, not separate modes.
- **Two KB tiers:** derivative wiki (`kb/`) with conclusions; raw fact-store (`kb/_raw/`) reserved for a future vector store that holds facts without conclusions. The wiki is a regenerable derivative; the raw store is the durable foundation.
- **Language decision:** harness layer (`CLAUDE.md`, `memory/`, `agents/`) in English; project knowledge (`kb/`, `decisions.md`) in the project's language (currently Russian). English was confirmed neutral for model comprehension — the criterion is portability and maintainability.
- **Memory facts:** 7 files re-anchored to the paradigm in this session; each now carries an explicit "Paradigm connection" paragraph. The role of `scope` (plan-author) is intentionally preserved; `scope-reviewer-redesign` will change it in the next plan.

## Open questions

- When will `scope-reviewer-redesign` be picked up? (next in the four-plan queue — awaiting session)
- SessionStart hook for ambient sessions: flagged as a possible later addition, not yet designed.
- `/_n` and other command-layer vocabulary: deferred to `command-layer` plan.

## Plan

→ plans/process-layer.md (APPROVED, executing phases 1–5 this session)

## Session decisions

→ decisions.md (flat log; subject-split into decisions/<subject>.md is deferred)

Key decisions this session:
- KB-loop paradigm written into live CLAUDE.md (English translation of CLAUDE.draft.md)
- 7 memory facts re-anchored with paradigm connections; MEMORY.md index updated
- Templates created: current.md, kb-note.md, decisions-log.md, README.md (layout + vector reservation)
- `kb/`, `session/`, `decisions/` bootstrapped in repo
