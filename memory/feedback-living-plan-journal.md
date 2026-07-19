---
name: feedback-living-plan-journal
description: Alex's working order — discuss and re-verify against live systems before acting, then keep a living plan-journal in the project KB and update it as understanding grows
metadata:
  type: feedback
---

Begin every non-trivial piece of work by discussing the unclear points and re-verifying against reality — read the actual servers, configs and code rather than trusting prior notes or your own first reading, which Alex has repeatedly caught as wrong until re-checked. As understanding solidifies, update the knowledge base incrementally: when something becomes clear, record it; when it becomes clearer, expand or rewrite it. Maintain one living plan-journal document per effort in the project KB (`ai/plans/…`) that tracks what is done and what remains, holds an explicit open-vs-decided split, and keeps a dated session history — Alex thinks of it as "what is happening and what is planned."

**Why:** Alex stated it as a standing rule ("мы всегда начинаем с обсуждения любых недопонятностей и всё перепроверяем") and wants a document that lets work survive across sessions and keeps him oriented. On the Pilier infra work he explicitly asked for exactly this living plan + journal.

**How to apply:** keep the order discuss → verify against live systems → then act; write confirmed facts to the KB as you go, but only confirmed ones (see [[record-only-confirmed-decisions]]); keep one roadmap/journal file per effort, tick it and append history rather than relitigating. Pairs with [[feedback-pacing-visible-progress]] and [[feedback-maintainability-never-sacrificed]].
