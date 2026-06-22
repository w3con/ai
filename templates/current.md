# <session title> — <date>
Subject: <slug>
Status: active | parked | closed

> Fill this against the "session document" section of `CLAUDE.md`, which holds the full rubric for the status-line percentages and the criteria for a good Problem / Cause / Goal / Solution. Score each axis by comparing your text to that rubric, not by feel. Re-read this file every turn before you write.

## Status line (per-turn — printed in chat AND logged here)

Format: `[<session>] domain NN% · task NN% · plan NN%`. Log one line every answer so the trajectory is visible; a low axis is the cue to ask Alex now rather than proceed.

- <date> — [<session>] domain NN% · task NN% · plan NN%

## Problem

(Gap + consequence: the current undesired state, who it affects, the gap from the desired state and why it matters. Falsifiable; not a symptom and not a solution in disguise.)

## Reason(s) / Cause(s)

(Root causes by counterfactual — reach each by asking "why" past the symptom (5-Whys), and keep only those whose removal would shrink the problem. Not restated symptoms.)

## Glossary & domain context

(Define every term that could be misread — one line each — and hold the domain facts and pointers into `kb/`. This is the visible home of the "domain" axis.)

## High level Goal

(SMART: Specific, Measurable, Achievable, Relevant, Time-bound. The end-state, not the activity.)

## Solutions (How to fix / resolve)

(Cause-coverage: address every named cause with its mechanism stated; feasible, and sufficient to meet the SMART goal.)

## Implementation plan (if needed)

(Link to `plans/<slug>.md` if there is a task to build; otherwise omit.)

## Open Questions

(Regenerate every turn: re-read this file, then for each section ask whether it meets its necessary-and-sufficient criteria; whatever is missing becomes an open question. Mark which are for Alex.)

## Session Decisions

(Decisions reached this session; durable ones graduate to `decisions/<subject>.md`.)
