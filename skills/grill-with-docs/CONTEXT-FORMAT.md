# Project context format

Use a root `CONTEXT.md` for a project with one shared vocabulary. For distinct domains, use a `CONTEXT-MAP.md` that points to context files for each domain.

## Definitions

- Choose one preferred term and list genuinely confusing alternatives as terms to avoid.
- Define what a project-specific term means in one or two sentences.
- Include domain-specific language, not general programming terms.
- Group definitions under headings when useful.
- Add a definition only when the project has resolved the meaning; preserve unresolved questions elsewhere.

## Example

```markdown
# Language

## Orders

**Order**
A confirmed request to purchase one or more products.
_Avoid_: Cart, transaction.
```
