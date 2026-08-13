---
name: feedback_kb_data_access
description: "How to access the Outline KB cheaply and safely — never MCP, avoid ad-hoc curl, strip local paths in Outline, keep .env secret out of context"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d707ed36-d57f-4c52-a5fa-94a6ebeca4f4
---

The user is **cost-sensitive about how I touch the Outline KB**. Two rules:

1. **Never use MCP** — too expensive (token cost). This is a hard rule, not just the old CLAUDE.md note.
2. **Stop regenerating ad-hoc curl/python every time** — that per-call generation is the cost the user
   wants gone. The intended fix is a thin local wrapper (e.g. `bin/outline` with verbs read/create/
   update/tree) or a skill that holds credentials and is called with **non-secret arguments**. (To be
   built when the user prioritises optimization — they said: finish the workflow first, optimize after.)

**Secrets:** keep `.env` / `OUTLINE_API_KEY` **out of my context** — never echo the key value (using
`source .env` + `$VAR` inside a command is acceptable since the value isn't printed, but a wrapper that
reads .env internally is preferred so I never handle it). `.env` is gitignored. Anthropic does not train
on Claude Code/API content by default, but secrets still land in the local session transcript — so the
real protection is never putting them in context.

**When writing TO Outline:** strip local filesystem paths (`strategy/research/*`, `strategy/options/*`,
`SYNTHESIS-*.md`). They are **meaningless to humans in Outline** — they're only my working breadcrumbs.
Use Outline `/doc/...` links instead. Local files keep both (local paths are useful for me); the Outline
copy gets Outline links only. See [[feedback_strategy_capture]].
