# CONTEXT Format

**Structure:** A `CONTEXT.md` file at the repo root (single context) or a `CONTEXT-MAP.md` + per-context files (multi-context).

## Rules

- **Be opinionated** — pick the best word, list others under `_Avoid_`
- **Keep definitions tight** (1-2 sentences max): define what it IS, not what it does
- **Only include project-specific terms** (not general programming concepts)
- **Group terms under subheadings** when natural clusters emerge

## Single vs multi-context detection

- If `CONTEXT-MAP.md` exists → read it to find contexts
- If only root `CONTEXT.md` exists → single context
- If neither exists → create root `CONTEXT.md` lazily when the first term is resolved

## Example Template

```markdown
# Language

## Orders

**Order**
A request from a customer to purchase products. Every order has a status (pending, paid, shipped, delivered) and belongs to exactly one customer.
_Avoid_: Transaction, Request, Cart.

**Order Status**
The current lifecycle state of an order: pending → paid → shipped → delivered. Transitions are one-way; an order cannot move backward.
_Avoid_: State, Stage.
```
