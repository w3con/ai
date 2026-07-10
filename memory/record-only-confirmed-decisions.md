---
name: record-only-confirmed-decisions
description: "Don't write decisions into durable records before Alex explicitly confirms; recommendations stay in chat until approved."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af8c3d91-68de-4b31-b809-cef13a9c2088
---

When capturing into on-disk records/plans, write only what Alex has **explicitly confirmed**. Proposals and recommendations stay in the chat until he says yes — do not pre-populate a record with a recommendation, even one labelled "pending confirm."

**Why:** On 2026-06-26 Alex flagged that I recorded a stack recommendation (Astro+Vue) into the plan file before he confirmed it; the same session he also pushed back on hardening soft "depends on the design" preferences into "RESOLVED" rules. Recording ahead of the "yes" pre-empts his decision and erodes trust, even when marked provisional.

**How to apply:** propose in chat → wait for explicit confirmation → then record as decided. If something genuinely must be noted before confirmation, keep it in a clearly-labelled "open/proposed" section, never in an "answer"/"decided" slot. Distinguish firm decisions from soft preferences in the wording. The two rules this used to point at — act only on what was decided, and propose with alternatives rather than a single answer — were promoted into `CLAUDE.md` (sections "How you decide and act" and "How you write") and no longer exist as separate memories.
