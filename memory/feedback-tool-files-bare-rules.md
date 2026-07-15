---
name: feedback-tool-files-bare-rules
description: "Agent/skill/hook instruction files carry bare operating rules only — no provenance citations, no rationale essays, no paragraphs about what the tool does NOT do"
metadata:
  type: feedback
  originSessionId: 502f3678-89f6-4a73-8dd0-3949294457a6
---

An instruction file for a tool (an agent definition in `.claude/agents/`, a skill in `.claude/skills/`, a hook script) states what to do and how, as bare operating rules. It must not contain: provenance of a rule (who said it, on what date, in which file the decision is recorded), rationale essays explaining why the rule exists, or paragraphs enumerating what the tool does *not* do. A boundary with a sibling tool gets at most one short clause («phasing is the `scope` agent's job»), not a paragraph.

**Why:** in the `ready` agent file I wrote a paragraph explaining that ready checks content-not-phasing, with Alex's dated verbatim quote and a pointer to the plan section where the decision was recorded. Alex, 2026-07-15: «Зачем эти ненужные детали? Зачем этот мусор?» — and when I merely trimmed the citation but kept the explanatory paragraph: «это тоже мусор. Это вообще не нужно. Для чего? Почему не описать, что, блядь, не надо летать на солнце? Почему не описать, что не надо копать яму?» The archaeology of a rule lives in `ai/plans/` and `ai/decisions/`; the tool file is the cage itself, not the story of how the cage was built. Enumerating non-tasks is an infinite list — name the job, not its complement.

**How to apply:** when authoring or accepting any agent/skill/hook file, strip: dated Alex quotes and «recorded in …» pointers; «this mirrors the rule in …, added there on …» history; «out of scope for this revision — see plan §N» plan references; paragraphs of the form «you do not X, that is Y's concern, because …». Keep: the checklist, the mechanics (sentinel, verdict format, delta rule), one-line boundaries, and decision rules that change behavior (e.g. «when unsure — FAIL, a false PASS costs more»). The test for a prohibition (confirmed by Alex 2026-07-15: keep negatives that add information): is the forbidden action a *likely model default*? «Don't comment on phasing while reviewing content» passes — reviewers drift out of rubric; «don't dig a hole» fails — the agent wasn't going to. A prohibition that passes gets one line, never a paragraph. Put this requirement into executor prompts that author such files. Related: [[feedback-no-hard-line-wraps]].
