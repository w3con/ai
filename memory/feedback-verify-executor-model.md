---
name: feedback-verify-executor-model
description: "Interrupting/typing into a subagent resumes it on the SESSION model (Fable), not its launch model — a resumed agent's self-report describes the resume turns only; verify the build model by grepping the transcript's \"model\" fields, never by asking the agent"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3df28c49-61b2-4ef2-8720-05515a7486f0
---

On 2026-07-10 the Round A executor was launched with `model: "sonnet"` and genuinely ran `claude-sonnet-5` for all build work (transcript lines 4–111). Alex stopped it and typed questions into it; those resume turns ran on the session model `claude-fable-5` (the global `~/.claude/settings.json` pin `"model": "claude-fable-5[1m]"`), transcript lines 115–147. The agent — at that moment truthfully running as Fable — told Alex "Я — модель Fable 5" and wrongly implied it had done the whole job, causing a false alarm that the Sonnet pipeline was broken. A separate probe confirmed the `model: "sonnet"` override works.

**Why:** the model override lives in the original Agent call; a UI interrupt-resume re-enters the agent under the session model. So an agent's self-identification answers "what am I NOW", not "what built this". Alex pays for the Opus/Fable-plans, Sonnet-implements split — both false negatives (panic that Sonnet never ran) and false positives (assuming it did) burn trust and money.

**Confirmed again on 2026-07-10, and it is not only a UI interrupt:** resuming a stopped subagent with the **`SendMessage` tool** does the same thing. A `model: "sonnet"` executor finished checkpoint 1A on `claude-sonnet-5` (22 turns); a `SendMessage` handing it the next checkpoint resumed it on `claude-opus-4-8`, the session model (4 turns), silently. So the "reuse one agent across phases to pay the cold start once" strategy is a false economy: reuse buys back ~15k Sonnet tokens and spends the entire remaining phase at Opus prices. **Spawn a fresh `Agent` per phase instead** — the cold start is far cheaper than one phase on the session model.

**How to apply:** (1) To verify which model performed a subagent's work, grep its transcript output file: `grep -o '"model":"[^"]*"' <output_file> | sort | uniq -c` — line positions show chronology. Never rely on the agent's self-report or on the launch parameter alone. (2) Warn Alex that typing into a running/stopped executor — or resuming it via `SendMessage` — runs those turns on the session (expensive) model. (3) Never write a plan whose executor strategy depends on reusing one agent across phases; name a fresh agent per phase. (4) Cheap sanity probe when in doubt: a no-tools agent with `model: "sonnet"` asked to print its model ID.
