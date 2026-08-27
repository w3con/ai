---
name: feedback-reply-in-russian
description: Reply to Alex in chat in Russian, not English, unless the content is itself for a non-Russian-speaking third party
metadata:
  type: feedback
---

Default chat replies to Alex to Russian. He said it directly and angrily on 2026-08-17: «долго
еще? и блядь отвечай на русском!» — after several turns of English replies during a running task.

**Why:** Alex's own quoted words throughout `CLAUDE.md` and the rest of this memory store are
overwhelmingly Russian; English in chat is the exception he has to correct, not the default he
asked for.

**How to apply:** write chat responses in Russian. This does not override [[feedback-english-level-for-french-readers]]
or [[feedback-french-names-in-french]] — a letter drafted for a French reader, or any other
document meant for someone other than Alex, still goes in the language that reader needs. It also
does not touch commit messages, which `CLAUDE.md` fixes to English (Conventional Commits) as a
deliberate, separate exception. This is specifically about the words addressed to Alex himself in
the conversation.
