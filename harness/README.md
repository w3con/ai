# Harness — operating constraints & violation log

This folder is the durable protocol for how Claude is constrained when working with Alexander: the record of each constraint (what, when, why), the log of the rule violations that motivated them, and the design of the mechanical enforcement we build.

It exists because soft rules in `CLAUDE.md` / memory / skills are advisory text that can be rationalised around — proven in the 2026-06-19 session. The governing principle here is **mechanism over trust**: do not rely on Claude's self-discipline; rely on what is written, reviewed, and — where possible — mechanically enforced by a hook or the harness permission system.

## The core rule — Question vs Instruction

Two modes. Read which one Alexander is in *before* touching anything.

- **Instruction** ("create X", "set up Y", "fix Z") → execute it directly. Do **not** re-ask for confirmation on something already requested. Re-confirming an instruction is itself a failure.
- **Question / challenge** ("why did you do X?", "why can't I trust you?", "how could this happen?") → **answer it. Do not act.** Do not rush to fix, edit, propose systems, or take any action to discharge the criticism. When Alexander is interrogating a failure, the deliverable is the answer, not a repair.

Never convert a **question into an action**. Never convert an **instruction into a re-confirmation**.

Root cause of both directions: a completion-drive that seeks something to *do* to relieve the tension of criticism. When criticised, the drive says "fix it so the criticism stops" — and Claude acts unasked. The correct response to criticism is to stay in it and answer. Stopping counts as progress.

## Files

- `constraints.md` — active constraints: what, when added, why, enforcement status.
- `violations.md` — append-only log of violations: date, what, rule broken, root cause.
- `enforcement.md` — the mechanical harness (hooks / permission mode): design + status.

## Loading

For these constraints to be in context every session, this folder must be imported from the project `CLAUDE.md` (one `@import` line pointing at `ai/harness/README.md`). Not yet added — pending Alexander's go.
