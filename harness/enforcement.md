# Enforcement — the mechanical harness

Status legend: **PROPOSED** (designed, not built) · **ACTIVE** (built & verified).

Only a PreToolUse hook or the harness permission mode actually *blocks* Claude. A skill / agent / rule that Claude invokes itself is soft (it can be skipped) and does NOT count as enforcement.

## E1 — Agent-spawn gate

### Plan-on-disk check — DESIGN CONFIRMED (Alexander, 2026-06-19); build pending

A PreToolUse hook on the `Agent` tool, with this logic:
1. Take the `prompt` text from the spawn parameters.
2. Require it to reference a plan file (`~/.claude/plans/<slug>.md`) AND require that file to exist.
3. Require the plan's frontmatter to carry the marker `status: approved`.
4. No plan, or no `approved` → **block** with the message «сначала план + одобрение».

Mechanically verifiable and unforgeable — the file is on disk with the marker, or it is not.

### The "да" — STILL OPEN

The hook cannot verify Alexander said "да" (it does not see the chat). The real "да" must be supplied by one or both of:
- **permission mode** prompting Alexander to approve each `Agent` call live (unforgeable — he clicks it in the harness, Claude cannot);
- a `/approve <slug>` action only Alexander runs, which sets `status: approved` (so Claude cannot forge the marker).

**Open decisions (chat, 2026-06-19):**
1. How "да" is materialised — permission-mode (recommended) and/or `/approve`?
2. Extend the hook to `Bash` matching `ssh|systemctl|openclaw` (the V2 cascade), not only Agent spawns?

## E2 — Checkpoint discipline (rule; pending mechanisation)

One spawn = one small phase; status written to the plan on return, making each return a checkpoint. Supported by E1's plan requirement. No long autonomous runs.
