---
name: feedback-check-both-send-routes
description: Validité only — a staged letter may have gone out from either at@validite.eu or the personal Gmail; check both and open the message, never judge from a subject line
metadata:
  type: feedback
scope: Validite
---

Before saying a staged letter has not been sent, check **both** routes and open the actual message. Outgoing business letters leave by two accounts: `at@validite.eu`, read with `~/.local/bin/himalaya envelope list -a validite -f "Sent Items"`, and Alexander's personal Gmail, read with the Gmail search tool on `tikonoff@gmail.com`. A letter is often sent twice, once from each, because a first message to an unknown recipient on a `gmail.com` address gets filtered as spam.

**Why:** on 2026-08-24 I reported that the letter to Nicolas Quarta was still unsent and left the draft on the staging page. It had gone out twice, on 19 August from `at@validite.eu` and on 23 August from Gmail. Two mistakes produced that: I read the sent-folder line «Re: Mise en relation» and assumed from the subject alone that it belonged to the Camille Ernould thread instead of opening it, and I never looked at Gmail at all. Alexander had to correct it himself, and the knowledge base was carrying a live draft for a letter already four days old.

**How to apply:** open the candidate message and read its `To:` line rather than matching subjects; when the sent folder of `at@validite.eu` shows nothing, search Gmail before concluding anything; and treat a resend from the other account as the expected pattern, not an anomaly. Related: [[feedback-check-if-letter-was-agent-written]].
