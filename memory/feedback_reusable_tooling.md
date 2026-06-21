---
name: Reuse tooling — commit a documented helper, don't re-author throwaway scripts
description: Prefer writing a reusable, committed helper script over re-constructing throwaway inline scripts each turn
metadata:
  type: feedback
  scope: user-level
---

When a repetitive mechanical task recurs (e.g. rendering deck slides to images for visual verification, a repeated data transform), write the helper **once as a committed, documented script** and reuse it — do not re-author a one-off inline `python3 - <<EOF` script every turn.

**Why:** the user explicitly flagged re-constructing the same screenshot script repeatedly as inefficient ("раз за разом ты конструируешь эти скрипты"). Re-deriving throwaway tooling each turn wastes effort and is error-prone.

**How to apply:**
- Factor recurring helpers into a real script in the repo, give it a docstring/usage line, and reference it from that repo's CLAUDE.md so future sessions discover it.
- A skill is overkill for a single self-documenting CLI command; a committed script + a CLAUDE.md note is the right weight. Reserve skills for multi-step workflows that need judgment.
- Keep config/styling in its proper file (e.g. CSS in the stylesheet, not inline). Relates to [[feedback_opus_plans_only]].
