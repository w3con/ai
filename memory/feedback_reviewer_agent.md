---
name: feedback-reviewer-agent
description: Whether you may spawn a sub-agent at all — stress-test strategic output with a real adversarial critic rather than a self-checklist, but spawn only when Alex has authorised it and the plan-gate allows it, never automatically
metadata:
  type: feedback
  scope: user-level
---

Strategic output — recommendations, competitive or regulatory analysis, outreach plans, summaries, decisions, action lists — is stronger when it is stress-tested by a **real adversarial critic sub-agent** than by a self-administered checklist, because self-review shares its own blind spots. A critic catches low-value recommendations, unsupported assumptions, and missing owners or dates. This does not apply to quick factual lookups or short conversational answers.

**Spawning is gated, not automatic.** Earlier guidance here told me to decompose research into parallel sub-agents "without being asked"; that was wrong, and it contradicts both how Alex works and the plan-gate hook. Do not auto-spawn anything. Any sub-agent — critic or research — runs only when Alex has authorised it for the specific task and the gate allows the spawn. An unconstrained research agent already cost a forty-minute, 210-document runaway, so by default gather cheaply and directly yourself.

**How to apply:** when Alex asks for a critic pass, draft the output, spawn the critic once, fix inline if it returns NEEDS REVISION, and then present; never re-run the critic. Keep rigorous source flagging (sourced versus estimate) and correct your own over-claims directly.

**Not the same question as [[feedback-verify-executor-model]].** This memory answers *may I spawn
one at all* — a question of permission, and the answer is only on Alex's word. That one answers
*how do I run the ones I am allowed to spawn* — a question of money: never reuse an agent across
phases, because resuming it silently moves it onto the session model. Confusing the two costs
either an unauthorised agent or an unnoticed bill.
