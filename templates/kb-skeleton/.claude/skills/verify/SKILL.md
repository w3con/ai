---
name: verify
description: Checks explicit factual claims against cited sources or an available external research tool.
allowed-tools: Read, Bash, WebFetch, WebSearch
---

Input: `$ARGUMENTS`, containing an explicit claim list, document, or URL.

Read a named document or fetch a supplied URL when the corresponding tool is available. Extract a small set of material, externally verifiable factual claims. Exclude opinions and internal process descriptions. Prefer checking sources explicitly cited by the document.

Use a configured and available external search method only when external verification is required. Do not assume provider names, credentials, agent types, or pricing. If no search or fetch tool is available, report the limitation rather than guessing.

For each claim, return one of:

- `CONFIRMED`: a source supports the claim; provide its URL and a brief reason.
- `CONTRADICTED`: an inspected source conflicts with the claim; describe the conflict and cite it.
- `NOT FOUND`: available sources did not establish the claim; do not treat this as disproof.

State which input was reviewed and separate direct source evidence from inference.
