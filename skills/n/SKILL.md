---
name: n
description: Enter the loop on a subject — open a fresh working session and load its existing KB.
argument-hint: "<subject slug>"
disable-model-invocation: true
---

Enter the full working loop on the subject named in $ARGUMENTS by opening a working session for it. Create a fresh `session/<date>-<slug>/current.md` from the template `templates/current.md` with `Status: active`, then load the subject's existing knowledge: its `kb/`, its `decisions/<slug>.md`, and its active plan in `ai/plans/` if one exists. Load the KB for the subject's domain, follow the loop instructions, and interview Alex about the subject. After that you are in the loop and work it until "Execute the plan" is given or the subject is changed.

This command does not create a KB. Creating a KB is the job of the `new-kb` skill. If the subject has no KB yet, do not scaffold one here — open the session, say plainly that the KB is missing, and point to `new-kb` to create the domain first.
