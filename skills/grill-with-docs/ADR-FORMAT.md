# ADR Format

ADRs live in `docs/adr/` with sequential numbering (`0001-slug.md`, etc.). The template is minimal: a short title + 1-3 sentences of context/decision/why. Optional sections (Status, Considered Options, Consequences) only when they add genuine value.

## Template

```markdown
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

An ADR can be a single paragraph. Optional sections (Status, Considered Options, Consequences) are only included when they add genuine value.

## When to offer an ADR — all three must be true:

1. Hard to reverse
2. Surprising without context
3. The result of a real trade-off

Qualifies for an ADR: architectural shape, integration patterns between contexts, technology choices with lock-in, boundary/scope decisions, deliberate deviations from the obvious path, constraints not visible in code, rejected alternatives when the rejection is non-obvious.
