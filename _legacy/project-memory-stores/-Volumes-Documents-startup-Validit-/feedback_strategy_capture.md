---
name: feedback_strategy_capture
description: "How the user wants strategy work captured — restartable decision log + options map, reasons/goals attached, research flagged not auto-run"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d707ed36-d57f-4c52-a5fa-94a6ebeca4f4
---

For strategy work, the user wants decisions and open threads persisted to disk **and** Outline so a
broken session can restart without losing context. Use an ADR-lite **decision log** (decision + why +
alternatives + status; keep superseded decisions visible, not deleted) and a **strategic options map**
that enumerates each opportunity with a consistent template (thesis, segment, differentiation, market
size, pricing, competitors, risks, effort, status, research-needed).

**Why:** the user explicitly fears forgetting opportunities/reasoning before making the best decision.

**How to apply:**
- Storage split: `/Intelligence/` = raw data/sources; `/Strategy/` = decisions built on it. Decision log
  lives in `/Strategy/GTM/Positioning/`; options map in `/Strategy/GTM/`; market data in
  `/Intelligence/Markets/Textile & Apparel/Market metrics`.
- Attach a **"why it matters / goal"** to every research/backlog item — not just the question.
- **Do NOT auto-run all research.** Flag what should be researched (with goals) for later; run only what
  the user picks. The user prefers to review the structure first.
- Keep the 5–10yr North Star visible in the options map as the lens for judging each option.
- **Propagate findings into the canonical docs** (O-pages, options map, Decision Log, Intelligence) — don't
  leave them stranded in side-files; side-files aren't the strategy. Stale "Research needed: R-X" TODOs must
  be replaced with the actual findings.
- **Don't do unit economics / financial model prematurely.** That's a **per-branch** step, after branch
  selection, against the *current* model file (confirm which file is current — don't assume). The research
  phase = save raw → Intelligence + structure findings. Branch prioritisation + pricing/economics + tier
  ideas (e.g. Verified Lite) are decided later, inside each specific branch — see [[feedback_kb_data_access]].
- Maintain rigorous source flagging (sourced vs estimate) — see [[feedback_reviewer_agent]]; admit and
  correct your own over-claims directly — see [[feedback_directness]].
- **Persist decisions/findings PROACTIVELY — don't ask permission to log.** Capture as you go or at the
  end of a discussion, without a "shall I log this?" round-trip. Do NOT ask the user to "confirm" things
  that are their own answers or data you produced. Reserve questions for genuine decision **forks** (real
  choices the user must make), not for capture. (User flagged the repeated confirm-prompts as friction,
  2026-06-01.)
- **"Save plan to disk" = handoff to another agent, NOT ExitPlanMode and NOT `/capture`.** When the user
  says save the plan, they mean: persist the plan/context to a durable file so a fresh agent (Sonnet
  implementer) can pick it up — and STOP there, do not exit plan mode or start building. This is the
  `/handoff` use case (context transfer), distinct from `/capture` (turning a decision into a durable KB
  `.md`). The auto plan file lives outside the repo (`~/.claude/plans/…`); also write a durable copy into
  the repo (infra/meta plans → `.ai/` alongside `redesign-plan.md`/`fix-v2.md`). Fix for `/handoff`: write
  to a durable repo path, not ephemeral `$TMPDIR`; keep it user-level so it's available across projects.
  They rejected ExitPlanMode and asked to "save plan to disk" on 2026-06-10, then corrected that this is
  the handoff sense. (Reinforces Opus-plans/Sonnet-implements — see [[feedback_opus_plans_only]] — and
  [[feedback_decide_before_building]].)
