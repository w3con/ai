---
name: Reuse tooling — commit a documented helper, don't re-author throwaway scripts
description: When a mechanical task recurs, write the helper once as a committed, documented script and reuse it, instead of re-authoring a throwaway inline script each turn
metadata:
  type: feedback
  scope: user-level
---

When a mechanical task recurs (rendering deck slides to images for a visual check, a repeated data transform), write the helper **once as a committed, documented script** and reuse it. Do not re-author a one-off inline `python3 - <<EOF` script every turn.

**Why:** Alex flagged re-constructing the same screenshot script over and over as wasteful ("раз за разом ты конструируешь эти скрипты"). A throwaway script evaporates when the session ends; a committed one is durable tooling.

**How to apply:** factor a recurring helper into a real script in the repo, give it a usage line, and reference it from that repo's CLAUDE.md so later sessions find it. A skill is overkill for a single self-documenting command; a committed script plus a CLAUDE.md note is the right weight, and skills are reserved for multi-step workflows that need judgment. Keep config and styling in their proper files (CSS in the stylesheet, not inline).
