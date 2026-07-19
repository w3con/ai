---
name: pilier-private-kb
description: In Pilier, internal reasoning lives in the private cloud repo (an Obsidian KB), not the public blockchain repo — know it exists and use it.
metadata:
  type: feedback
  scope: pilier
---

The Pilier **blockchain code repo is public** (`/Volumes/SSD/Dev/pilier/blockchain`, public on GitHub). The project's internal "brain" is a **separate private repo** — an Obsidian vault at `/Volumes/SSD/Dev/pilier/cloud` (`git@github.com:pilier-org/cloud.git`). Its README fixes the split: public how-to-use docs live in the landings repo (served at `pilier.dev/docs`); everything internal — ops runbooks and server inventory (`ops/`), internal knowledge about the code (`knowledge/`), development plans (`ai/plans/`) and the decision log (`ai/decisions/`) — lives in the private cloud repo, and it names agents (including Claude Code) as the main consumer of that private base.

**How to apply:** At the start of any Pilier work, know this repo exists and read it for context (`cloud/knowledge/`, `cloud/ai/decisions/`, `cloud/ai/plans/`, `cloud/ops/`). Write ALL internal reasoning — decision docs, plans, internal notes — into `cloud/`, NEVER into the public `blockchain/ai/` (that path is gitignored in the public repo as of 2026-07-19). Public "what changed & why" goes to `blockchain/CHANGELOG.md` (sanitized, keyed by `spec_version`) and/or `pilier.dev/docs`, with no internal attribution or rejected-alternative detail.

**Why:** Alex flagged (2026-07-19) that I "discovered" the KB mid-task instead of already knowing it — since its own README names agents as the main consumer, not knowing it is a real miss. This memory makes every future Pilier session start already aware.

For Pilier only, this overrides the general default that a project's decisions and plans live in that project's own `ai/` versioned with the code — because here the code repo is public, so internal reasoning must not sit in it. See [[feedback_git_staging]] for the related "stage only your files, never blanket-add" discipline that keeps internal work out of the wrong commit.
