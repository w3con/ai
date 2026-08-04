---
name: feedback-name-roles-not-people
description: "Process and procedure documents name roles with a glossary, never a person's name; define the human as \"the owner\" rather than writing \"Alex\""
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8e5704a6-3164-44e4-9ae8-cd13489690c9
  modified: 2026-08-02T19:41:21.202Z
---

A document that describes how work gets done names **roles**, and defines them once in a short glossary near the top. It never says "Alex". Alex asked for this directly on 2026-08-02, after reading a process page that referred to him by name a dozen times: «ты ссылаешься на Алекса. Давай заведем в этом документе, а также в самом скилле небольшой словарь. e.g. кто такой координатор? Кто за что отвечает, чтобы не был просто Алекс».

The four roles settled on, and the words to use: **the owner** (в русском тексте «владелец») — the human the work is done for, who decides what gets built, approves a plan before implementation starts, and accepts the result; **the coordinator** — the agent session that talks to the owner, plans, founds and fills the planning documents, and hands implementation over ("orchestrator" and "planning agent" are the same role under other names); **the executor** — the sub-agent that implements one document's worth of work and never decides scope; **the reviewer** — the adversarial reading agent, spawned only on demand.

**Why:** a role is a description of responsibility that stays true when the person or the model behind it changes, and a document written around one person's name silently becomes wrong the moment anyone else touches the process. It also reads as gossip about an individual rather than as a procedure. The same argument is why the glossary is mandatory rather than optional: a role name with no definition is just a different kind of unexplained shorthand, which Alex objects to for the same reason he objects to bare identifiers — see [[feedback-no-ciphers-in-chat]].

**How to apply:** when writing or editing any procedure, skill file, agent brief or knowledge-base page about process, put a short roles glossary near the top and use those words throughout. Where a decision genuinely needs attribution — a quoted line that settled something — attribute it to the role and the date («владелец, 2026-07-14»), not to the name. This is about documents; ordinary chat with Alex is unaffected.
