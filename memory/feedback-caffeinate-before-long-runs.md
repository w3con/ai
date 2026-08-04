---
name: feedback-caffeinate-before-long-runs
description: Start caffeinate before spawning any executor, because the Mac falling asleep kills every running agent mid-stream
metadata:
  type: feedback
---

Before spawning an executor, or starting anything else that runs for more than a few minutes without a human at the keyboard, keep the machine awake: `nohup caffeinate -ims -t <seconds> >/dev/null 2>&1 &`, with a bounded timeout so it cannot be left running forever. Check `pgrep -lf caffeinate` first — the system starts its own short-lived ones and a five-minute timer is not protection.

**Why:** on 2026-08-04 two of three concurrently running executors died within minutes of each other, one with "Connection closed mid-response" and one with "no progress for 600s". I reported these to Alex as two unrelated infrastructure failures. Alex gave the real cause in one line: «это у меня компьютер просто заснул, потому что ты не поставил caffeinate». A sleeping Mac stops every agent at once, and the two different-looking error messages are the same event seen from two angles.

**How to apply:** start it as part of the hand-over, in the same breath as running `bin/task-handover` — not after the first agent dies. Because agents tick their checkpoints on disk before starting the next one, a sleep costs only a resume message rather than the work itself; but the resume still costs a cold read of a long card, and on the final checkpoint the verbatim gate output lives only in the stopped agent's context, so the cheap fix is to not fall asleep at all. See [[feedback-executor-card-size]] for why the last checkpoint is the expensive place to be interrupted.

**And do not narrate a wrong cause with confidence.** Two agents dying inside the same minute is a signal about the machine, not about two agents. When several independent things fail together, look for the one shared cause before explaining each separately.
