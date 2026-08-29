---
name: feedback-description-explains-how-it-works
description: A card's description must let Alex understand how the thing works and why it works that way — if he cannot follow it, the description is the thing that is wrong
metadata:
  type: feedback
scope: validite-app
---

A task card's `description.md` has to leave Alex understanding how the built thing actually works — what it does, in what order, and the reason behind each of its parts. What he does not want in there is the story of how a plan got repaired: which finding the critic raised, what I rewrote in response, which step I merged into which. The line is between *reasons* (wanted) and *process narrative* (not wanted), never between short and long.

**Why:** on 2026-08-29 he read HRN-5's description and could not tell what the card was about; I first answered that the repair details do not belong in a description, and he corrected the framing — «мне неинтересно читать про то, как ты чинил план, но мне интересно читать, какие причины того или иного, чтобы понимать, как работает карточка. Потому что если я даже не понимаю, как она работает, значит, описание плохое». A description he cannot follow is a defect in the description, not a gap in his attention.

**How to apply:** give a card a section that walks through how the thing works in plain words — the command that starts it, each check it makes and the concrete reason that check exists, and what it does once nothing has stopped it. Define every term the moment it appears (what a "map" is, what a "phase boundary" is), because a term he has to decode is the same failure as an unexplained card. Keep the critic's findings and my answers to them in `plan.md`, where the executor and the acceptor read them. Related: [[feedback-cut-slop-keep-depth]], [[feedback-unanswered-question-means-unclear]], [[feedback-no-ciphers-in-chat]].
