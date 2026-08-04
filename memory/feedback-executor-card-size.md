---
name: feedback-executor-card-size
description: One card handed to one executor must fit roughly one phase and one toolchain; swap agents at a phase boundary, never mid-phase
metadata:
  type: feedback
---

**One card does one thing.** That is the whole rule, and it is Alex's, stated on 2026-08-04 after
he had watched me miss it twice in one hour: «одна функциональность - вот что главное». Cards
group upward into a feature — one feature may own several cards — so a card never needs to carry
two pieces of functionality to keep them together.

The checkpoint count is not a second rule and is not a budget; Alex explicitly does not care about
it («мне похрену сколько чекпоинтов»). It is a symptom worth reading: a card whose checkpoint list
keeps growing is usually a card that has quietly acquired a second piece of functionality, and the
answer is to split off that second thing, never to trim steps off the first.

Apply this to the card as it will actually be handed over, not as it was first drafted. A second
defect discovered after founding does not join the card; it becomes its own card. When one defect
blocks the other from even being committed, that is an argument for ordering the two cards, never
for merging them.

**Why:** Alex, 2026-08-04, watching an executor run forty minutes on `SHL-2`: «Это слишком большая
задача для одного агента - Будь стоит слишком дорого.» A long-running agent is expensive in the
obvious way, and expensive in a way that is easy to miss: on its hundredth turn it starts
forgetting the card's own out-of-scope list.

**And why the count, specifically.** Within the hour, on the very next card, I did it again: founded
`HRN-45` at two points and one phase, appended a second defect as a five-checkpoint Phase E, and in
the same message called the result «намеренно маленькая». Twelve checkpoints. It ran past half an
hour and its executor's stream died before the last one. Alex: «Нет, блять, ты ему дал задачу,
которая 30 с лишним минут. Это короткое называется?» The work survived only because every finished
checkpoint was ticked on disk. The soft measure did not stop me; a count would have.

**How to apply:** size the card at planning time, and where the work is honestly wider, hand it
over phase by phase rather than whole.

**Swapping an agent is cheap only at a phase boundary, and stopping is never a refund.** The card
carries the ticked checkpoints, so a fresh agent picking up at a boundary needs nothing else, and
that is precisely why the boundary is the cheap moment. Mid-phase it is the opposite: the tokens
already spent are not returned by stopping, the old agent's remaining turns are mostly cache reads
at about a tenth of normal input cost, and the fresh one pays a full cold start re-reading a card
that has grown long. Worst of all is stopping on the final checkpoint, where the verbatim check
output — the whole basis of acceptance under [[record-only-confirmed-decisions]] — still lives only
in the stopped agent's context and has to be re-earned by re-running the checks at the coordinator's
own more expensive model.
