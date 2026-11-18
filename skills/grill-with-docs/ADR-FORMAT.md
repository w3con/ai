# Architecture decision record format

Store records in the project's established decision-record directory and use its numbering convention. If no convention exists, agree on a location before creating a new system.

## Minimal template

```markdown
# Short decision title

Context: <the constraint or problem that matters>

Decision: <what was selected>

Rationale: <why this option fits better than relevant alternatives>

Consequences: <important follow-up, cost, or limitation>
```

Keep only sections that add useful information. A concise paragraph is sufficient for a small decision. Record status and alternatives only when they clarify the decision's lifecycle or trade-off.
