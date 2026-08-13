---
name: project-retailer-pitch-build
description: "Retailer pitch deck location + build workflow — edit source slides, never the generated index.html"
metadata: 
  node_type: memory
  type: project
  originSessionId: 47074b2a-2e11-408e-a55a-1df524025ed1
---

The retailer pitch deck lives at `/Volumes/SSD/Dev/validite/web/validite.eu/pitch/retailers/` (separate
repo from the KB). `index.html` is **generated** — do NOT edit it directly. Source slides are in
`slides/*.html` (opening, situation, problem-data, problem-traceability, scenario-before, solution,
offers, demo, results, demo-portfolio, closing), assembled into `index.html` by `python3 build.py`
(which injects them between `<!-- SLIDES_START -->`/`<!-- SLIDES_END -->` in `source.html`).

**Workflow:** edit the relevant `slides/<name>.html`, then run `python3 build.py` to rebuild `index.html`.
Bilingual deck: every text node has `<span class="fr">…</span><span class="en">…</span>` — change both.

Related: this is the deck design direction the user likes (see [[feedback-strategy-capture]]); the
retailer-flywheel strategy is O-2.
