---
name: pilier-verify-repo-vs-live
description: Pilier only — before changing or auditing server config, diff the locally-tracked file against the live host; don't reason from the repo copy alone.
metadata:
  type: feedback
  scope: pilier
---

Before acting on, or drawing conclusions from, any infrastructure configuration file that is
tracked in a Pilier repo — a `docker-compose.yml`, an nginx config, a firewall ruleset, an `sshd`
drop-in, and so on — pull the actual live copy from the corresponding server by SSH and diff it
against the repo's copy, rather than trusting that the repo copy is current just because it exists
and reads plausibly.

**Why:** during the `network-exposure-hardening.md` work (2026-07-21), a live audit of `pilier-ops`
found that the private `cloud` repo had **no file at all** for the `https-portal` gateway that
fronts `pilier.eu`, `portal.pilier.dev`, and Passbolt — every earlier answer about whether a
firewall change would break those services had been built on prose in `ops/inventory.md`, not on
the actual routing config. A separate audit of `gra9` found that the live `nginx.conf` sat under a
different filename than the repo's dated snapshot (`reverse-proxy.conf`), and that both `gra9` and
`pilier-ops` were already running an active UFW firewall that neither the plan nor the repo's
documentation had recorded — meaning the plan's own risk assessment had silently been built on
stale assumptions instead of live state. Alex named this a general risk for Pilier's infra work:
local files can diverge from what a server actually runs, and reasoning from the stale copy is
dangerous precisely because it looks trustworthy.

**How to apply:** this is a standing habit, not a scheduled job or a script — Alex was explicit
that it should fire on Claude's own judgement at two moments, not on a timer. First, whenever a
plan or a live change is about to touch a server's configuration, verify the relevant tracked
file(s) against the live host before writing or applying anything based on them. Second, whenever
asked to check, audit, or verify anything about live infrastructure, do the same live comparison
rather than answering from the repo alone. When the comparison turns up a real gap — a live config
with no repo copy, or a repo copy under a different name than the live file — surface it to Alex,
and if fixing it is cheap and read-only (adding a synced snapshot, matching the convention `gra9`'s
`docker-compose.yml` already uses), offer to do it rather than leaving the gap unaddressed.
Complements [[feedback-living-plan-journal]], which sets the general discuss → verify → act order;
this memory is the concrete mechanics of the "verify" step for Pilier's tracked config files
specifically. Also complements [[pilier-private-kb]], since most of the affected files live in the
private `cloud` repo this memory is about.
