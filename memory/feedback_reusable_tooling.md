---
name: feedback-reusable-tooling
description: When a mechanical task recurs, write the helper once as a committed, documented script and reuse it, instead of re-authoring a throwaway inline script each turn; a skill decides *when* to call, a script decides *what happens*
metadata:
  type: feedback
  scope: user-level
---

When a mechanical task recurs (rendering deck slides to images for a visual check, a repeated data transform), write the helper **once as a committed, documented script** and reuse it. Do not re-author a one-off inline `python3 - <<EOF` script every turn.

**Why:** Alex flagged re-constructing the same screenshot script over and over as wasteful ("раз за разом ты конструируешь эти скрипты"). A throwaway script evaporates when the session ends; a committed one is durable tooling.

**How to apply:** factor a recurring helper into a real script in the repo, give it a usage line, and reference it from that repo's CLAUDE.md so later sessions find it. Keep config and styling in their proper files (CSS in the stylesheet, not inline).

**Script or skill — the line between them, so this rule is not misread as "never write a skill".**
The two answer different questions and often both are needed. A **script** owns what happens once
you have decided to act: deterministic logic the model must not improvise — an ordered chain of
providers, a pause between requests, a cache, an exit code. A **skill** owns the decision to act
at all: recognising that "погугли" means the user wants a web search. Neither substitutes for the
other. When a job needs only the first — a single self-documenting command — a committed script
plus a note in CLAUDE.md is the right weight, and a skill would be ceremony around a shell call.

Worked example, 2026-07-10: web search needed both. `bin/websearch` holds the provider chain, the
per-provider throttle, the fifteen-minute cache and the exit codes, because a model cannot reliably
wait between requests or tell whether a provider is up. `skills/web-search/` holds one judgment —
is this a request to search — and one fallback the script physically cannot perform, calling the
model's own `WebSearch` tool when the script reports every provider down. See
`decisions/web-search-tool.md` in this repository.
