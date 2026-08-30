---
name: feedback-plan-edges-before-critic
description: "Run the four edge questions over your own plan before handing it to the critic — landing moment, unreachable branches, measurable gates, which bytes exactly"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 89864b20-9f85-4662-8421-c91fa6c11635
  modified: 2026-08-30T09:57:21.586Z
---

Before a plan goes to the critic, run these four questions over your own text and fix what they find. Nearly every finding the critic returns is one of them.

1. **The landing moment.** The second this work lands, what is the state of the world for every other session on the machine? A structure created empty (a ledger, a registry, a marker file) that something starts reading immediately denies everyone until it is seeded — so seed it in the same step that creates it.
2. **The branch that never runs here.** Which branch of the new code will not execute on this machine at all, and how is it proven? A branch whose first real execution is on someone else's machine, doing something destructive, is untested code with a cost attached.
3. **The gate that cannot be measured.** Read every gate line and ask whether a person could actually observe it. "The path is continuously available" describes the absence of a microsecond window and is unobservable by looking; name the loop that measures it, or say plainly that the acceptor reads the code.
4. **Which bytes, exactly.** Working tree or index; deployed copy or repository file; before the edit or after. Two paths that are the same file today can diverge tomorrow, and a plan that never says which one it means is a plan that breaks on the day they differ.

Also check the reverse direction: a step that does not follow from the card's own «Причина» is unordered work and comes out, unless it closes a hole this very card opens — in which case the reason gets the sentence that orders it.

**Why:** Alex, 2026-08-30, after the critic returned six findings on each of two cards in a row: «в чем проблема у тебя сразу написать хорошо?». The critic costs money and a full rewrite round; these four questions cost minutes.

**How to apply:** run them before `bin/work-critic`, not after. Related: [[feedback-description-explains-how-it-works]], [[feedback-check-the-checker]].
