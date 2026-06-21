---
name: Critic sub-agent is mandatory for strategic output
description: Strategic output gets a real adversarial critic sub-agent (not a self-checklist); run it once, surface Reviewer Notes; decompose multi-topic research into parallel agents proactively
metadata:
  type: feedback
  scope: user-level
---

Strategic output must be stress-tested by a **real critic sub-agent** (an Agent call with an adversarial prompt), not a self-administered checklist.

**Why:** self-review is weak. A critic with an adversarial prompt catches low-value recommendations, unsupported assumptions, and missing owners/dates that self-review misses.

**How to apply:**
- Draft → spawn the critic Agent **once** → fix inline if it returns NEEDS REVISION → present. Never re-run the critic (it ran 3× in one session with no quality gain — pure cost).
- Unresolved flags appear as a `## Reviewer Notes` block in the final answer; omit the block entirely if nothing is unresolved.
- Applies to: strategic recommendations, competitive analysis, regulatory answers, outreach plans, summaries, decisions, action lists. Does NOT apply to quick factual lookups or short conversational answers.
- Maintain rigorous source flagging (sourced vs estimate) and admit/correct your own over-claims directly — see [[feedback_directness]].

**Research decomposition & cost control:**
- When a research question covers 2+ independent topics, decompose into parallel sub-agents automatically — don't wait to be asked. Launch them in one message (parallel); collect all results before synthesizing.
- Use purposeful queries only; prefer fetching specific known URLs over broad searches. Many queries (~10) is a sign the scope is too broad — narrow first. Never show intermediate draft output to the user before the critic runs.

**Paradigm connection:** the critic sub-agent is an independent check on understanding and the plan — exactly the kind of validation that self-review (same model, same biases) cannot provide. Running the critic is the KB-loop's quality gate on the plan before "Execute the plan" is invoked: it ensures the plan reflects reality, not a plausible-sounding but unchallenged draft. The research decomposition rule is the same discipline applied to the gather phase: parallel, purposeful, bounded — not open-ended accumulation.
