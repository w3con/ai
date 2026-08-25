---
name: feedback-approve-letter-before-writing-it-down
description: "A letter is proposed in chat and only written to the drafts page, the contact card or the tracker after Alex has approved the text; drafting straight to disk churns the knowledge base over wording nobody has agreed to."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 75faf2cf-3bfb-4cb6-83cf-d35fa1950123
  modified: 2026-08-25T11:20:22.545Z
---

A letter to a real person is shown to Alex **in the chat message itself** and nowhere else until he approves the text. Only after he says the letter is right does it get staged on the outgoing-drafts page, and only then do the contact card and the tracker get their rows about it. The same holds for every artefact whose wording is still being argued: propose it in the conversation, write it to disk once it is settled.

**Why:** on 2026-08-25 a reply to Nicolas Quarta went through four versions in one sitting, and each version was written into `kb/BizDev/_drafts.md`, twice more into `kb/BizDev/letter-style.md` and the tracker, and committed, before Alex had approved any of them. He rejected the first for talking when it promised to listen, then cut the next sentence as well. The result was three commits of churn over text that never existed as a letter, plus the read-modify-rewrite cost of the knowledge base on every turn. In his words: «ты просто занимаешься переписыванием в базе знаний… до того, как мы письмо даже утвердили».

**How to apply:** draft in the reply, give the body in full so it can be read and copied without opening a file, say what was cut and under which rule, and stop. When he approves, stage it and log it in one pass. If the letter is rejected, the next version is also a chat message. The `/draft-letter` skill was corrected the same day so that its own Step 3 says this rather than "stage it on the drafts page" — [[feedback-check-the-checker]] applies, so read the skill before trusting that it still says so.

Related: [[record-only-confirmed-decisions]], which is the same instinct applied to decisions rather than to wording.
