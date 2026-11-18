# Knowledge-base conventions

This file defines the Markdown document contract shared by human editors and any index builder configured for this project. Confirm that a builder supports these fields before using generated metadata.

## Document locations

Store knowledge-base documents as Markdown under `kb/`, grouped in project-defined collections. Use filesystem-safe names that are easy to reference. Files outside `kb/` are not governed by this document.

## Frontmatter

Each knowledge-base document may use this YAML frontmatter:

```yaml
---
title: "Document title"
type: reference
status: working
tags: [example]
relates-to: [related-document-slug]
ai-note: "Optional usage note."
ai:
  domains: [example-domain]
  topics: [example-topic]
  entities: { people: [], orgs: [], regulations: [] }
  summary: "Generated summary."
  generated: "<YYYY-MM-DD>"
  source: local:kb/collection/document.md
---
```

Fields above `ai:` are human-owned. A configured builder may own and replace the `ai:` block; do not edit that block manually when such a builder is enabled. If no builder is configured, omit generated metadata rather than inventing its values.

`title` names the document. The established `type` values are `strategy`, `intelligence`, `bizdev`, `custdev`, `operations`, `finance`, `reference`, and `decision`. The established `status` values are `draft`, `working`, `authoritative`, and `archived`. `tags`, `relates-to`, and `ai-note` are optional project metadata. The `ai:` keys and their exact meanings must match the builder contract in use.

## Links and sources

Use the project's supported internal link format consistently. Ordinary Markdown links are appropriate for external sources. Clearly distinguish direct source claims from estimates and hypotheses, and include enough provenance for readers to locate cited material.

## Generated index

Treat an index as generated only if a project command documents that behavior. Do not manually modify a generated index; use its builder and check mode where available.
