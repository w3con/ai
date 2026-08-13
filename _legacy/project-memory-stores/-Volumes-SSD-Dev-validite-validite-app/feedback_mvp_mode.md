---
name: feedback-mvp-mode
description: "This project is an MVP demo, not a final product — prioritize speed and limited scope, but still make architecturally sound decisions because they affect future build-out."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 73abbe9e-e6ee-4495-bf5d-748c0104eb21
---

The current Validité work is extending an existing MVP for demonstration purposes, not shipping a final product. Some parts can be missed, stubbed, or "faked" so long as the demo flows work end-to-end.

**Why:** User explicitly flagged this when I was about to enter a 11-interview spec build-out — they wanted to make sure I optimize for demo speed, not exhaustive specification. The fact that the existing app is already a working MVP (single 1400-line main.go, JSON-LD blobs, role ACL but no role spec, certs scoped per-GTIN) confirms the pattern.

**How to apply:**
- Every spec / plan should have an explicit **MVP cut**: minimum needed for demo, what's faked/stubbed, what's deferred to post-MVP.
- Prefer fewer, shorter interviews. Combine topics where the demo only needs a thin slice.
- **Architectural decisions still matter** — data model shape, module boundaries, naming, where state lives — because they're expensive to undo later. Don't shortcut these even when shortcutting features.
- Stubs/fakes that are demo-only must be flagged as such in the spec, with a one-line note on what the real version would do.
- When proposing an approach, separate "architecture (lock in)" from "implementation (can fake for demo)" so the user sees the tradeoff.
- [[feedback-scope-discipline]] still applies — MVP mode is a reason to *narrow* scope, not to silently add adjacent features. Out-of-scope items in source docs remain out unless promoted explicitly.
