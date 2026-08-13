---
name: reference_relations_unreliable
description: ".ai/relations index is sound for retrieval but partial coverage + uneven quality — don't trust them for \"is this doc in Outline?\" gap checks"
metadata: 
  node_type: memory
  type: reference
  originSessionId: df153b19-dab1-4d52-a941-410ea1ecce26
---

**Scope correction (2026-06-10):** the relations *index itself is sound and useful for retrieval* — each `.ai/relations/<id>.json` carries structured `domains`/`topics`/`entities`/`cross_refs`/`summary`/`checksum`, and sampled entries (Narrative `47c50c3f`, GTM `10954b1c`) are accurate. The known weakness is narrow: (a) **uneven extraction quality** on a Haiku-built subset per the 2026-05-21 audit (`.ai/relations-audit-report.md` — PASS 4 / PARTIAL 9 / FAIL 2: thin topics, missed orgs in tables, 2 wrong-collection, 1 fabricated cross_ref), and (b) **partial coverage** — 253 relations vs 314 in `id_mapping` vs 112 cached `.md` (some collections skipped via `relation-config.json`). So: trust it for recall/ranking, but do NOT treat it as authoritative for "does this doc exist in Outline?" gap checks. Don't over-generalize this to "the index is broken."

`.ai/relations/*.json` is therefore **not a reliable authority for existence/gap checks** against Outline. Observed 2026-06-10: `ad8f21ec.json` carried the title "O-1 — Independent metteurs" for a document that had **always** been "O-5 — Horizontal expansion" (every Outline revision back to 05-31 was O-5), and three live docs (O-7 `0990e290`, R-6 `f3e12b45`, R-10 `575759ce`) had **no relations file at all**. A gap analysis built on relations titles therefore falsely reported O-5/O-7/R-6/R-10 as "missing from Outline," which nearly caused duplicate creation / unwanted overwrites.

**How to apply:** before concluding a local KB doc is missing from Outline (or before creating/updating one), verify against `.ai/id_mapping.json` (short-id → UUID) **and** a live `documents.info` / `documents.search` call — never relations titles alone. To check what an Outline doc currently is and its prior state, use `documents.info` + `revisions.list` (note: `revisions.list` returns metadata only, not body text — use `revisions.info` for text). Outline retains full revision history, so any bad update is reversible via `revisions.restore`. Related: [[feedback_kb_data_access]].
