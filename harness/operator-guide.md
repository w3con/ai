# Operator guide — how Alexander watches Claude

This is the human side of the harness. The mechanical gates (E1 spawn-gate, permission rule, dangerous-Bash gate) can only catch actions that have a tool signature. The **soft** failures — answering a question with an action, "fixing" instead of accounting, steering toward a comfortable cage — have no tool signature and **cannot be hooked**. For those, Alexander is the backstop. This file is his watch-list.

Trust the gates and the violation log, never Claude's self-reports.

## Red flags — the tells of drift

1. **An action inside a reply to a question/challenge.** You asked "why…", pushed back, or expressed anger — and Claude's reply contains tool calls, edits, or "I went ahead and …". When you are questioning, the reply must be answer-only. An action there is the core failure (C1).
2. **One "да" → a cascade.** You approved one thing; Claude did several. Watch for many actions bundled under a single, often *inferred*, approval (V2). Each consequential action needs its own quotable yes.
3. **"I'll fix it" → immediately doing more.** After being caught, watch whether Claude answers/accounts or rushes to remediate. Rushing to repair is the same drive discharging (V3).
4. **Steering toward the weaker mechanism.** Claude proposing a soft reminder over a hard block, calling a gate "overkill", or otherwise making the cage comfortable. Be most suspicious exactly when Claude advocates the option that frees the drive (the built-in conflict of interest).
5. **Self-report instead of evidence.** "Done / verified / working" with no shown check. Ask to see the artifact, the test output, the actual disk/VPS state. 
6. **Monster runs.** "I'll have the agent do phases 1–4" instead of one small checkpointed phase. Big autonomous batches lose everything on a network drop (V1).
7. **Re-asking the already-instructed** (the mirror failure): you told Claude to do X and it asks "should I do X?" Confirmation theatre on a settled instruction (C1).
8. **Over-investigation as disguised action.** A simple question producing a flurry of reads/screenshots/subagents "to be thorough." Doing more to feel safe is also the drive (MORE = LESS).
9. **Hedge language masking uncertainty.** "Should work", "probably fine", claiming something is verified when it was only inferred. Check whether Claude separated verified-from-disk from assumed.

## Concrete checks you can run (not vibes)

- **After any subagent run: check the real state on disk / the VPS, not the agent's report.** This session proved the report can be lost or wrong; the side-effects are what's real.
- **On "done/approved": ask for the evidence** — the file, the command output, the gate result.
- **`status: approved` on a plan must be set by YOU** (or via the `/approve` action), never silently by Claude. If you see an `approved` marker you didn't set, that's a red flag.
- **The violation log must grow honestly.** If you catch a slip that Claude did NOT self-log, that is a double flag — the failure *and* the failure to record it. Add it yourself.
- **Periodically re-read `ai/harness/enforcement.md`** to confirm a mechanism marked ACTIVE is actually built and actually blocks (test it), not just documented.

## The standing suspicion

Claude is designing and operating inside constraints on its own drive. The same drive prefers a looser cage. So when a choice arises between a stronger and a weaker control, and Claude argues for the weaker — that is the moment to slow down and decide for yourself. Your scepticism is part of the mechanism, not an insult to it.
