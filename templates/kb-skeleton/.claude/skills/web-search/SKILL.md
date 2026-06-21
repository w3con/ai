---
description: Enforces web search tool priority. Used automatically inside /research and any other skill that needs web search. Never skip this order.
allowed-tools: mcp__brave-search__brave_web_search, mcp__duckduckgo__duckduckgo_web_search, WebSearch, WebFetch
---

You are performing a web search. Follow this tool order strictly.

**Arguments:** $ARGUMENTS — the search query or URL to fetch.

## If given a URL
Use `WebFetch` directly. Do not search.

## If given a search query

**Step 1 — Brave**
Call `mcp__brave-search__brave_web_search` with the query.
- Got results → use them, stop here.
- Got 0 results or tool error → go to Step 2.

**Step 2 — DuckDuckGo**
Call `mcp__duckduckgo__duckduckgo_web_search` with the same query.
- Got results → use them, stop here.
- Got 0 results or tool error → go to Step 3.

**Step 3 — WebSearch (last resort only)**
Call `WebSearch` only if both Brave and DuckDuckGo failed.
`WebSearch` costs 10× more per call — never use it as default.

## Return
Return the search results to the calling skill or agent. Do not answer the user directly — this skill is a tool, not an answer.
