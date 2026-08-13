# Templates — project AI structure

## Target layout for any project

Every project that uses the KB-loop paradigm gets this structure under `<project>/ai/`:

```
<project>/ai/
  kb/                         Derivative wiki: domain notes, edited in-place, Obsidian (md + [[links]])
    _raw/                     Reserved mount point for the future raw vector store (see below)
  session/<YYYY-MM-DD-slug>/
      current.md              Working session document (template: templates/current.md)
  decisions/<subject>.md      Append-only "why" log, one file per subject (template: templates/decisions-log.md)
  plans/<slug>.md             Phased resumable plans (checked by plan-gate.sh)
```

## Templates in this directory

- `current.md` — session working document; fill in at the start of each session
- `kb-note.md` — one KB article (derivative wiki entry with conclusions)
- `decisions-log.md` — append-only decisions log header for a new subject file
- `plan-card.md` — one task card: the statement of the work, the six interview
  questions answered in the owner's own words, the sources read before those
  questions were put, the summary the owner approves, the scope boundary, the
  acceptance criteria, the checkpoints and the gate evidence. What the check
  requires is that the answers are on the record, not that an interrogation took
  place: an answer already given in conversation is written down by the
  coordinator, and only what has not been said is asked

## The interview sections are opt-in per project

`bin/plan-check` enforces the interview, the sources and the approved summary
only in directories that ask for it. A project switches the rules on by placing
an empty file named `.plan-check-interview` beside its cards; each non-comment
line in that file names a card basename exempted from the rules, which is how
cards written before the practice began keep passing unchanged. Where no such
file exists, `plan-check` checks only the older rules — approval, scope,
acceptance criteria, well-formed checkpoints, resolving paths, no leftover
placeholder — and ignores the interview entirely.

## Vector-store reservation (raw fact store)

Raw facts — regulations, research, source documents, any fact without a conclusion attached — are
NOT stored inside `kb/` mixed with the derivative wiki. They belong in a separate path.

`kb/_raw/` is reserved as the documented mount point for the future raw vector store. The rule:
**raw facts are stored separately, without conclusions.** The wiki (`kb/`) is a regenerable
derivative; the raw store is the durable foundation. Keeping them separate means a future model
can reinterpret the raw facts cleanly, without the current layer of conclusions getting in the way.

The raw vector store itself is not built yet — this reservation just keeps the door open.
