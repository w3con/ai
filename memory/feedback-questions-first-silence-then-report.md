---
name: feedback-questions-first-silence-then-report
description: "Ask every question before the first edit, build in total silence, and hand over one report at the end carrying the findings, the decisions taken alone and the mistakes with their fixes"
metadata:
  node_type: memory
  type: feedback
---

A task runs in three phases that never mix. Before the first edit you read what bears on the task yourself — knowledge-base documents, change history, the live state of the system — and then put **all** of your questions at once; in a project whose cards carry an interview section, the answers required are the six in `templates/plan-card.md`, recorded in Alex's own words. What must be on the record is the answers, not an interrogation — whatever already came out in conversation you write down yourself, and you ask only about what was never said. You then write a summary in your own words of what is being built, and his approval of that summary is what starts the work. From there until the work is finished there is silence: no progress reports, no warnings about what you found on the way, no confessions of a wrong turn already corrected, no requests for permission. At the end he reads one report: what was built, which technical decisions you took alone, what went wrong, and how each was fixed.

**Why:** Alex asked for exactly this on 2026-08-13 — «мне очень хочется сделать так, чтобы ты мне задавал много-много много вопросов, и ни разу меня ничего не предупреждал… только в конце, после того, как все имплементировано, я смотрю на отчет со всеми твоими находками, со всеми твоими проебами, с тем, как ты эти проебы решил». He also measured the surplus: «95% всего, что ты пишешь, для меня это просто шум». Work here repeatedly began before the task was understood, and the cure is depth of interview, not a right to interrupt him later.

**How to apply:** a question that arises while building is always a question of technical implementation and never of business — he settled that explicitly — so decide it yourself and carry the decision into the final report. A genuinely business-level question surfacing mid-build is evidence the interview was too shallow; that lesson goes into the report and still does not license an interruption. The only thing that stops everything is a destructive or irreversible action the approved summary did not cover. See [[record-only-confirmed-decisions]].
