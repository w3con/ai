---
name: web-search
description: Search the web for current information or documentation. Use the toolkit search command when available; fetch a supplied URL directly.
allowed-tools: Bash, WebSearch, WebFetch
---

You are performing a web lookup for the caller.

**Input:** `$ARGUMENTS`, containing a query or a URL.

For a URL, use the available URL-fetch tool first. When it returns empty or partial content (script-built pages, PDFs, bot-blocking sites), run the repository's `bin/webscrape` command, using the syntax and exit codes documented by its current implementation. For a search query, first inspect and invoke the repository's `bin/websearch` command using the syntax documented by its current implementation. Do not assume a particular home directory, search provider, credentials, or result schema.

Use the command's documented exit status and output contract. If it reports that no provider succeeded and a built-in web-search tool is available, use that tool as a fallback. Do not treat invalid arguments as a provider outage. If the script or required provider is unavailable or misconfigured, report that fact to the caller even if a fallback returns useful results.

Return the findings and source URLs to the caller. Do not answer on the caller's behalf unless asked to do so.
