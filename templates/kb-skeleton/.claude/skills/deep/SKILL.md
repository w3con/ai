---
description: Manual trigger for cross-domain KB retrieval. Spawns the kb-retriever agent to build a compressed multi-collection brief from the local knowledge base. The agent also auto-invokes on cross-domain questions; use /deep to force it, or to point it at a specific area.
allowed-tools: Agent, Read, Bash
---

Spawn the **kb-retriever** agent with the user's query from `$ARGUMENTS`, passing along any collection or domain hints they gave. Return the agent's brief to the user as-is.

Do **not** load knowledge-base documents into this (main) context yourself — reading and compressing them is the agent's job, and keeping the raw documents out of the main conversation is the whole reason this runs as an agent.

If `$ARGUMENTS` is empty, ask what to retrieve, and list the available areas by showing the `## ` collection headers from `kb/_index.md` (resolve `PROJECT_ROOT="$(git rev-parse --show-toplevel)"`).
