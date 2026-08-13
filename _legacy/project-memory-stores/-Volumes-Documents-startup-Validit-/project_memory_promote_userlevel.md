---
name: project_memory_promote_userlevel
description: Memory is now two-tier — user-level facts at ~/.claude/memory loaded via ~/.claude/CLAUDE.md; project facts stay here; user-profiler routes by scope
metadata: 
  node_type: memory
  type: project
  originSessionId: fd818334-9b1b-42bc-b6b2-4cf8514483a9
---

Memory is now split into two tiers (promoted 2026-06-11 at the user's request, ahead of any second project).

**User-level (cross-project):** `~/.claude/memory/` holds person/working-style facts shared across every project — directness, write-for-the-reader, Opus-plans/Sonnet-implements, reusable-tooling, decide-before-building, critic-agent discipline. They load in every project because `~/.claude/CLAUDE.md` `@import`s each file (the global CLAUDE.md is read in every session; the harness is not documented to auto-load a user-level memory dir, so the import is what guarantees loading). Single source of truth = the files; `~/.claude/memory/MEMORY.md` is the index, and CLAUDE.md carries one `@import` line per file.

**Project-level (Validité only):** this directory keeps facts that don't generalize — `feedback_kb_data_access` (Outline/MCP/.env), `feedback_web_repo_boundary` (the web-repo path), `feedback_strategy_capture` (Validité folder layout), and all `project_*` / `reference_*`.

**Why:** preferences about the person shouldn't be re-learned per project; project plumbing shouldn't leak into unrelated KBs (health, travel).

**How to apply:** when recording a new fact, route by scope — a durable preference about *the user* or *how to work* → `~/.claude/memory/` (add file + MEMORY.md line + a CLAUDE.md `@import`); a fact about *this project* → here. The `user-profiler` agent encodes this routing. Adding a fact at the user level means also adding its `@import` to `~/.claude/CLAUDE.md`, or it won't load.
