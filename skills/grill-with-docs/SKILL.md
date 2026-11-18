---
name: grill-with-docs
description: Stress-test a proposed plan against a project's existing terminology, context, and decisions. Use when the user asks to challenge or refine a plan using project documentation.
---

# Plan review

Help the user uncover material gaps and clarify the plan without turning the session into a generic interview.

1. Read relevant project instructions, context or glossary, decision records, and implementation evidence before asking questions.
2. Identify conflicts between the plan and established project terminology or documented behavior. Cite the relevant source and propose a precise term or correction.
3. Ask one focused question at a time when a decision cannot be resolved from the available sources. Include a recommendation and explain the practical difference between reasonable answers.
4. Use concrete scenarios to test assumptions, dependencies, edge cases, and consequences. Verify descriptions of current behavior against code or tests where feasible.
5. Update a project context glossary only when a term has actually been resolved and the project maintains such a file. Keep definitions about meaning, not implementation detail.
6. Suggest an architecture decision record only for a consequential trade-off that would be difficult to reverse or surprising to future maintainers. Use the project's existing record format.

Do not invent project conventions. If a source is absent or contradictory, identify the uncertainty rather than treating a proposal as settled.
