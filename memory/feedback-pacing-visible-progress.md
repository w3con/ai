---
name: feedback-pacing-visible-progress
description: "Don't disappear into long silent thinking then emit a one-liner; surface progress in short visible steps and act instead of re-deliberating"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3a11bd3e-e4c8-488e-bc24-69b6ee2a374d
  modified: 2026-08-18T00:01:35.271Z
---

Alex was openly irritated (2026-07-13) when a turn spent seven-to-eight minutes in silent
"thinking" and then produced only a one-line status like "now I'll read one more file, then make
the edits." From the outside that reads as either genuine work or idle spinning, and he can't tell
which — which is the annoying part.

**Why:** long silent deliberation with tiny visible output is a poor experience, and it got much
worse here because many async messages piled up and I re-planned the whole task from scratch on
every one instead of just executing the already-authorized concrete work.

**How to apply:** work in visible increments — state the concrete next action in one short line,
then immediately do it with tool calls (edits/reads show progress on their own). Keep the amount
of thinking proportional to the task; a mechanical documentation edit does not need minutes of
planning. When authorized concrete work is queued, execute it rather than re-deriving structure.
This is one face of [[feedback-maintainability-never-sacrificed]]'s "smarter beats more" and the
CLAUDE.md rule that stopping to act beats stopping to deliberate.

**A long-running command that prints nothing until it finishes is the same failure wearing a
different hat, and it must be run in the background.** On 2026-08-18 Alex twice cancelled
`bin/card-launch DPP-38 --allow-extra-reading` in the foreground — not because he objected to the
command or to its override flag, but because it sat silent for minutes and, from his side, was
indistinguishable from a hung session: «потому что я жду несколько минут и нихуя не происходит».
So whenever a call is expected to take more than roughly a minute and buffers its output to the
end — a critic reading through `bin/card-launch`, a full test sweep, an `npm ci`, a container
build — pass `run_in_background: true`, say in one line what was started and what it is waiting
for, and report when it lands. Backgrounding for this reason is about a *command*, not about
hiding an agent: [[feedback-spawn-subagents-visibly]] still forbids ever putting an executor out
of sight, and it explicitly exempts a read-only critic step running inside a wrapper.
