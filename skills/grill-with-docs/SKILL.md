---
name: grill-with-docs
description: Grilling session that challenges your plan against the existing domain model, sharpens terminology, and updates documentation (CONTEXT.md, ADRs) inline as decisions crystallise. Use when user wants to stress-test a plan against their project's language and documented decisions.
---

<what-to-do>

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing.

If a question can be answered by exploring the codebase, explore the codebase instead.

</what-to-do>

<supporting-info>

## Domain awareness

During codebase exploration, also look for existing documentation:

### File structure

Most repos have a single context:

/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/

If a CONTEXT-MAP.md exists at the root, the repo has multiple contexts...
[Create files lazily — only when you have something to write]

## During the session

### Challenge against the glossary
When the user uses a term that conflicts with the existing language in CONTEXT.md, call it out immediately.

### Sharpen fuzzy language
When the user uses vague or overloaded terms, propose a precise canonical term.

### Discuss concrete scenarios
When domain relationships are being discussed, stress-test them with specific scenarios.

### Cross-reference with code
When the user states how something works, check whether the code agrees.

### Update CONTEXT.md inline
When a term is resolved, update CONTEXT.md right there. Format defined in CONTEXT-FORMAT.md.
CONTEXT.md is a glossary only — no implementation details.

### Offer ADRs sparingly
Only offer to create an ADR when ALL THREE are true:
1. Hard to reverse
2. Surprising without context
3. The result of a real trade-off

</supporting-info>
