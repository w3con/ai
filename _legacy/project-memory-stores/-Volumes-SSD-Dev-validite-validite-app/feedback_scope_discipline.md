---
name: feedback-scope-discipline
description: "When source/requirements docs declare scope (in/out), stick to it — don't silently expand the work list with adjacent items the user didn't ask for."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 73abbe9e-e6ee-4495-bf5d-748c0104eb21
---

When the user hands over requirements documents (e.g. Navigation Guide, Certificates spec), those docs are the **authoritative source of scope**. Items they explicitly mark out-of-scope stay out. Don't add adjacent or "obviously needed" items to the work list without surfacing them as a question first.

**Why:** During the spec build-out plan I added Magic Link, Hashing & Anchoring, and (effectively) a Roles spec to the interview series — all three were explicitly out-of-scope in Navigation.md v1.1. User caught it: "'Build new' - why those, and not as specified in the Navigation.md?" Silent scope creep wastes interview rounds and erodes trust in the plan.

**How to apply:** When planning from a source doc, open the response with the scope as-declared in the source (in/out lists verbatim). Anything you want to add beyond that gets called out as an explicit question with justification ("X is implied by Y because Z — do you want it in scope?"). Cross-cutting needs implied by in-scope items (e.g. AI Parsing implied by Certificates v1.0's "AI-validated" status) are fine to include, but must be labeled as *required by* an in-scope item, not as fresh scope.
