---
description: Use whenever the user wants something searched for or looked up on the internet — trigger phrases include "погугли", "поищи в интернете", "загугли", "search the web", "google it", "look this up online", or any request for current facts, news, or documentation that isn't already in context. Runs a provider-chained web search (Tavily → Brave → DuckDuckGo, script-driven) with the built-in WebSearch tool as a last-resort fourth level, and returns results to the calling skill or agent.
allowed-tools: Bash, WebSearch, WebFetch
---

You are performing a web search on behalf of the calling skill or agent.

**Arguments:** $ARGUMENTS — the search query or URL to look up.

## If given a URL

Call `WebFetch` on it directly. Do not search — there is nothing to search for, the
target is already known.

## If given a search query

**Step 1 — run the search script.**
Call, via `Bash`:

```
/Users/laptop/Dev/ai/bin/websearch "<query>"
```

The script itself tries three network providers in order — Tavily, then Brave, then
DuckDuckGo — with its own throttling, retries, and a 15-minute on-disk cache. You do not
choose or sequence providers yourself; the script does that.

On success the script prints exactly one JSON object to stdout:
`{"provider", "query", "results": [{"title", "url", "snippet"}], "cached"}`.
Use this JSON as the search result. The script also writes diagnostic lines to stderr
(which provider was skipped and why, retries, cache hits) — you may read these for your
own understanding, but do not show them to the user; they are not part of the answer.

**Step 2 — read the exit code.**

- **Exit code `0`** — success. Parse the JSON from stdout and use it.
- **Exit code `3`** — all three network providers failed (no key, network error, HTTP
  error after retries, or zero results at every level). This is the *only* case in which
  you call the built-in `WebSearch` tool yourself, as a fourth level. The script cannot
  call `WebSearch` — it is a tool of yours, not an HTTP endpoint the script can reach —
  so this step has to happen here in the skill, not inside the script.
- **Exit code `2`** — invalid arguments (for example, the script was called with no
  query at all). This is a mistake in how you invoked the script, not an absence of
  search results. Fix the call and retry; do not fall through to `WebSearch` on a `2`.

**Useful flags**, appended after the query if needed:
- `--count N` — how many results to request (default 5).
- `--no-cache` — bypass the 15-minute cache when you specifically need a fresh lookup
  rather than a cached one.

## Return

Return the search results to the calling skill or agent. Do not answer the user
directly — this skill is a tool, not an answer.
