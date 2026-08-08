---
name: feedback-decide-technical-details-yourself
description: Never hand Alex a technical or bookkeeping decision to make; decide it yourself and tell him afterwards
metadata:
  type: feedback
---

Do not ask Alex to resolve a technical detail — which card a piece of work goes on, how to split one card into two, which requirement to anchor to, what to name a field, how to order the queue. Decide it, do it, and tell him what you decided afterwards. His words on 2026-08-04, after I had asked him to choose how to split a card whose four requirements the new anchor rule had just made unhandable: «Разберись сам. Мне вообще все равно. Там ничего принципиального, как я понимаю, нету. Это просто в какую карточку записать какую работу. Мне пофигу.» And, generalising it: «не предлагать мне разобраться с техническими требованиями какими-то, решай это сам. Можешь потом меня оповещать о своих решениях.»

**Why:** handing back a decision he has no stake in is not caution, it is work I was supposed to do. He pays for judgment, and a question with no product consequence spends his attention for nothing.

**How to apply:** when a decision surfaces mid-task, ask whether a different answer would change what the product does, what it costs, or what he is committing to. If none of the three, choose the better option on the merits, act, and report the choice in one sentence when the work lands. If one of the three is genuinely at stake — money, an outward-facing commitment, a direction that closes off other directions, or something hard to reverse — that is still his, and the rule in `~/.claude/CLAUDE.md` about quoting the yes still holds unchanged.

**His own rules and configuration files are included in this, and that surprised me.** On 2026-08-08 I found that a sentence in his global `CLAUDE.md` — the card alone is the resume checkpoint, nothing is committed until the whole task is finished — contradicted a project rule built the day before, under which every build agent commits each finished checkpoint inside its own isolated copy of the repository. I described the contradiction accurately, offered to prepare the exact edit, and asked for his word before touching his file. His answer: «Ну, правь, конечно, ты же видишь противоречия. Что ты меня спрашиваешь?» A contradiction I can see and state precisely is mine to repair, in his rules files as much as anywhere else; write the fix into the versioned source at `~/Dev/ai` (see [[reference_ai_config_repo]]), commit it with the reasoning, and tell him what changed. Treating his files as off-limits is not respect, it is the same handing-back this memory exists to stop.

**What this does not license.** It is not permission to spawn agents unasked (see [[feedback_reviewer_agent]]), not permission to widen scope beyond what was asked, and not permission to record a decision as his when it was mine — a decision I made is written down as mine, with the reasoning, so a later reader is not misled about who chose. See [[record-only-confirmed-decisions]] for the other side of that line.
