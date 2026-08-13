---
name: feedback-test-runs-must-not-reach-the-user
description: "When a script's job is to deliver something to a person, sending must be opt-in behind a flag before any executor is allowed to iterate on it"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 61343295-343e-4bf9-86ab-11d55e28ae64
  modified: 2026-08-13T15:28:38.340Z
---

When you brief an executor to build anything whose purpose is to deliver a message to a real person — a Telegram digest, an email, a notification — make sending **opt-in behind an explicit flag before the executor starts**, and tell it to verify by reading the assembled output printed to its own terminal. Never let "run it and check the result" mean "send it".

**Why:** on 2026-08-13 I told an executor to run the digest script on the server after each module and confirm the section worked. The script sent on every run by default, so Alexander received a string of empty placeholder digests in his personal Telegram chat and was rightly furious («да нихуя продолжает приходить все в Телеграм»). Sending an instruction to the running executor did not stop it, because a subagent only reads its mailbox between tool calls — the only thing that stopped it was killing the agent. The fix that should have been in place from the first line of the brief was inverting the default: print by default, send only with `--post`.

**How to apply:** invert the default in the script itself rather than relying on the executor's discipline, because a default is enforced and an instruction is not. Put the flag in place yourself before spawning anyone. If an executor is already loose and reaching a person, kill it with `TaskStop` immediately rather than messaging it and hoping — then check whether anything on the server side is also looping before you claim it has stopped. This is the same principle as [[feedback_reusable_tooling]]: what must not be improvised belongs in code, not in a prompt.
