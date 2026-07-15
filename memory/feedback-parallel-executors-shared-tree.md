---
name: feedback-parallel-executors-shared-tree
description: Running build executors in parallel — safe to overlap only across disjoint toolchains unless each gets its own worktree
metadata:
  type: feedback
---

When executing a phased plan with multiple build sub-agents running at the same time in
ONE shared working tree, two executors that both compile the same module will see each
other's half-written files during their gate (`go build ./...`, `vue-tsc`), producing
spurious failures and confusing attribution.

**Why:** on 2026-07-12, building a 12-phase feature overnight, I parallelised phases to use
the night well. Frontend + backend phases overlapped safely (disjoint toolchains — a Vue
`npm run build` never reads Go files and vice-versa). But two backend-Go phases editing and
compiling the same module concurrently would have collided. The clean rule fell out of that.

**How to apply:**
- Overlap freely across **disjoint toolchains** (one frontend + one backend at a time is
  safe, and roughly halves wall-clock).
- Do **not** run two same-language executors that compile the same module concurrently in
  the shared tree. Either serialise them, or give each `isolation: "worktree"` (the Agent
  tool creates an isolated git worktree per agent) so their edits and gates don't intersect.
- Verify each phase before releasing the next dependent one: read the real diff, run the
  gate yourself, and confirm the executor's transcript `model` field
  (`grep -o '"model":"[^"]*"'`) — never trust the launch parameter alone
  ([[feedback-verify-executor-model]]).
- Commit a reusable gate **script** once (e.g. a Dockerised `go-gate.sh`) rather than
  reconstructing the verification each phase ([[feedback_reusable_tooling]]).
