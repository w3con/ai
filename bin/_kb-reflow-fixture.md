---
title: kb-reflow self-test fixture
type: test
tags: []
ai:
  domains: ["test"]
  topics: ["fixture", "reflow"]
  entities: { people: [], orgs: [], regulations: [] }
  summary: "Fixture file for kb-reflow self-test. Contains every boundary kind."
  generated: 2026-06-26
---

# Heading — boundary, never merged

Plain prose paragraph that has been
hard-wrapped at a narrow column width
to test the reflow transform.

Another prose paragraph with
several lines joined
across three lines total.

| Column A | Column B |
|----------|----------|
| Row 1    | Data     |
| Row 2    | More     |

- [ ] Task item that wraps
  to a second continuation line
- [ ] Another task item — standalone
- Simple [[wikilink]] bullet item
- Another plain bullet

> Blockquote line one
> Blockquote line two

```python
code = "stays untouched"
wrapped_line = (
    "inside fence"
)
```

<!-- relation-build:related-start -->
## Related

[[some-doc]]  [[other-doc]]
<!-- relation-build:related-end -->

Final prose paragraph after the Related block
that should also be reflowed
across its three lines.
