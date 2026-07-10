---
name: design-reproduce-not-improvise
description: "Applies to the Validité website redesign (Dev/web): reproduce the design files exactly, never improvise; interview to 100% clarity and record to disk."
metadata: 
  node_type: memory
  type: feedback
  scope: validite-web
  originSessionId: af8c3d91-68de-4b31-b809-cef13a9c2088
---

On the validité site redesign, Alex forbids ANY design improvisation — "запрещаю фантазировать даже на пиксель." Build only (a) exactly what is written in `redesign/Components.dc.html` / `redesign/DESIGN.md`, or (b) what Alex stated explicitly. Never "finish details by the logic of the visual language" — that is the failure mode he called out.

For anything not 100% specified: **write a mini-plan to disk and run an interview** — ask as many questions as needed until his intent is fully clear, recording each answer into the plan file *before* writing any code. (Hero example: `/Users/laptop/Documents/Validite/plans/hero-redesign.md`.)

**Why:** I repeatedly guessed (full-bleed hero, removed the 16px radius, invented object-position and min-height, mis-took "zero padding" as full-width) instead of reproducing the showcase. It wasted effort and angered him.

**How to apply:** reproduce showcase values verbatim; when unsure, the move is mini-plan-on-disk + interview, not a best-guess build. Note he often fires several messages that queue and arrive *after* I've already asked — do not re-ask what a later message already answered. The two rules this used to point at — act only on what was decided, and answer directly without performative padding — were promoted into `CLAUDE.md` (sections "How you decide and act" and "How you write") and no longer exist as separate memories.
