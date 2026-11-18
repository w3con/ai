---
name: deep
description: Retrieves and synthesizes material across a project's local knowledge-base collections.
allowed-tools: Agent, Read, Grep, Glob
---

Input: `$ARGUMENTS`, a question with optional collection hints.

If an appropriate read-only knowledge-base retrieval agent is available, delegate the source selection and synthesis to it, then return its sourced brief. Otherwise read `kb/_index.md`, select relevant documents, inspect them directly, and produce the same brief. Do not assume an agent or index-refresh command exists unless it is available in this project.

If the input is empty, ask what the user wants to retrieve and list collection headings from `kb/_index.md` if present.
