---
name: n
description: Enter the working loop on a subject — open its session document and load its existing KB.
argument-hint: "<subject slug>"
disable-model-invocation: true
---

Enter the full working loop on the subject named in $ARGUMENTS, inside the existing KB of the current project.

1. **Open the session document.** Create or open `session/<date>-<slug>/current.md` from `templates/current.md`, with `Status: active`. This is the per-turn working surface for the whole session.
2. **Orient in the existing KB — work out where this session's output will go.** Read `kb/_index.md` (the generated map of the base: one line per document, grouped by collection) to see the existing collections and documents, and decide which document(s) this session will improve or add. Open the subject's `decisions/<slug>.md` and its active plan in `plans/` if they exist.
3. **Fill `current.md` and run the loop.** Interview Alex about the subject; on every turn re-read `current.md`, answer into it, improve the three axes (domain / task / plan), and print the status line.

This command never creates a KB — that is the `new-kb` skill. If the project has no `kb/` yet, say so plainly and point to `new-kb`.
