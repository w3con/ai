---
name: feedback-no-hard-line-wraps
description: "Never hard-wrap prose in markdown documents — one paragraph = one physical line; Alex's viewers render the wrap points as visible line breaks"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 502f3678-89f6-4a73-8dd0-3949294457a6
---

When writing any markdown document for Alex (kb/ notes, ai/ records, plans, decision logs), never insert hard line breaks inside a paragraph to keep source lines under ~100 columns. Write each paragraph as one physical line, however long. The same applies to executor subagents — put this rule into their prompts when they will author documents.

**Why:** Alex's document viewers render a single newline as a visible line break, so a hard-wrapped paragraph displays as ragged, broken lines («убери искусственные переносы в этом документе и всех других. Сделай себе пометку — не ставить переносы», 2026-07-13, after the whole kb/harness/ document set had to be unwrapped post-hoc).

**How to apply:** paragraph = one line; blank line between paragraphs. Tables, headings, list items, YAML frontmatter, and code blocks are unaffected (a long list item is also one line). If an existing document shows this problem, unwrap it with a script that joins continuation lines while skipping fences/tables/frontmatter rather than hand-editing. Related: [[feedback_reusable_tooling]].
