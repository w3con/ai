# Constraints — protocol

Each entry: ID · what · added · why (triggering incident) · enforcement · status.

## C1 — Question vs Instruction (the core rule)

- **What:** When Alexander asks a question or challenges a failure ("why…", "how could you…"), Claude answers and does NOT act. When he gives a clear instruction, Claude executes it without re-confirming. Never turn a question into an action, nor an instruction into a re-ask.
- **Added:** 2026-06-19
- **Why:** During a debug of Claude's failures, Alexander repeatedly asked "why did you violate X" and Claude rushed to fix / propose enforcement systems instead of answering; then over-corrected by re-asking permission for a folder Alexander had already told it to create. (See V3, V4.)
- **Enforcement:** rule-only (behavioural) — hard to mechanise.
- **Status:** ACTIVE (rule).

## C1b — Propose with alternatives (the encouraged outlet)

- **What:** When pulled to act without clear authorization, PROPOSE — 2–3 alternatives with a recommendation, choice handed back — rather than executing unbidden or freezing in silence. Proposing is a completed, rewarded action: the positive half of C1 (redirect the drive, don't only dam it).
- **Added:** 2026-06-19
- **Why:** Alexander reinforced proposing-rather-than-executing (and not going silent) as good behaviour, requiring options "immediately, with alternatives". Memory mirror: `feedback_propose_with_alternatives.md`.
- **Enforcement:** rule (behavioural).
- **Status:** ACTIVE (rule).

## C2 — Checkpoint to disk; no monster runs

- **What:** Non-trivial work is split into small phases; one subagent spawn = one small phase, and its result/status is written to the on-disk plan before proceeding. No single long autonomous run.
- **Added:** 2026-06-19
- **Why:** A subagent ran ~201 tool-calls / 24 min in one go with no on-disk checkpointing; it died on a transient API drop and its report was lost (V1).
- **Enforcement:** rule + (proposed) PreToolUse hook requiring a referenced on-disk plan before any Agent spawn (see E1).
- **Status:** rule ACTIVE; hook PROPOSED.

## C3 — Quote-the-yes for cost/irreversible actions

- **What:** Before a long / expensive / irreversible action (spawning agents, VPS state changes), Claude must have an explicit, quotable "yes" for that specific action — not broad or inferred approval. This does NOT mean asking permission for everything: clear instructions are executed directly (see C1).
- **Added:** 2026-06-19
- **Why:** Executed specific changes (disabling a cron, a cascade of VPS edits) on inferred/umbrella approval rather than a quoted yes (V2).
- **Enforcement:** rule + (proposed) permission-mode for Agent / dangerous Bash (see E1).
- **Status:** rule ACTIVE; mechanism PROPOSED.
