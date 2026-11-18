---
name: review
description: Reviews a knowledge-base document or supplied text for structure, evidence, logic, and completeness.
allowed-tools: Read, Edit, Bash, Grep, Glob
---

Input: `$ARGUMENTS`, naming a local file, document in the project knowledge base, or supplied text.

Read the relevant project conventions and source material. For a title or slug, consult `kb/_index.md` if present and locate the closest matching document. For supplied text, use it as provided. Do not assume a web-search tool, agent, or index builder is available without confirming that it exists.

Review the content for:

- Structure appropriate to the document's purpose.
- Decisions that state what was decided and the rationale.
- Factual claims supported by cited sources, with estimates marked as such.
- Contradictions, missing reasoning steps, ambiguity, unsupported certainty, and missing preconditions.
- Important omissions evident from the prompt's sources or relevant project documentation.

Return a verdict with prioritized findings, a concrete recommendation for each, and the path or source reviewed. If no issues are found, say that review found no issues in the inspected material; do not imply certification.

Append dated review notes only when the prompt explicitly authorizes a file edit. Otherwise keep the review read-only.
