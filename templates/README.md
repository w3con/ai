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

## Vector-store reservation (raw fact store)

Raw facts — regulations, research, source documents, any fact without a conclusion attached — are
NOT stored inside `kb/` mixed with the derivative wiki. They belong in a separate path.

`kb/_raw/` is reserved as the documented mount point for the future raw vector store. The rule:
**raw facts are stored separately, without conclusions.** The wiki (`kb/`) is a regenerable
derivative; the raw store is the durable foundation. Keeping them separate means a future model
can reinterpret the raw facts cleanly, without the current layer of conclusions getting in the way.

The raw vector store itself is not built yet — this reservation just keeps the door open.
