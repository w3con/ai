# Decision log — plan-gate hook

## 2026-07-10 — The gate checks the plan handed to the executor, not the neighbourhood

**Decided by:** Alexander, in conversation with Opus («давай починим… да, давай так»).
**What:** `hooks/plan-gate.sh` no longer scans `<project>/plans/*.md` for a scope-PASS
sentinel. It now reads the plan file named in the spawned agent's own prompt (any path
ending in `.md`; absolute preferred, relative resolved against the project root, the working
directory, and the `plans/` and `ai/plans/` conventions under each) and allows the spawn only
if **that** file contains the line `<!-- scope:pass -->`. A build agent whose prompt names no
plan is denied. The read-only agents `scope`, `Explore` and `Plan` stay exempt, so the verdict
can still be obtained in the first place.

**Why:** the old question — «does some approved plan exist nearby?» — is not the question
worth asking, and in practice it answered «yes» permanently. In `Dev/app` there were 26 plans
under `ai/plans`, of which 20 still carried a PASS from tasks closed long ago; any build agent
therefore passed the gate, for any task, whether or not a plan had been written for it. The
gate had stopped protecting anything and merely looked as though it did. The same design also
failed in the opposite direction: a plan living in a different repository — the shared tooling
repo `~/Dev/ai/plans/` — was invisible to the gate, so legitimate, scope-approved work there
was blocked while unapproved work in `Dev/app` sailed through. Binding the check to the plan
actually handed to the executor removes both faults at once, and removes the directory scan
entirely rather than adding more directories to it.

**Alternatives considered:** (1) add `$HOME/Dev/ai/plans` to the scanned directories — the
cheapest change and the one that would have unblocked the session immediately; rejected
because it fixes only the cross-repository symptom and leaves the gate permanently open in
`Dev/app`, which is the more dangerous of the two faults. (2) Expire the sentinel by plan
status, e.g. ignore plans marked `DONE` — rejected as a second mechanism guarding against a
consequence rather than the cause; under the new contract a stale plan can only be used by
naming it deliberately, which is no longer an accident. (3) Delete the 20 stale sentinels —
useful hygiene, but it restores the hole the moment the next plan passes scope.

**Consequences:** spawning a build agent now requires naming its plan in the prompt. This is
a real cost, paid on purpose: it is the change, not a side effect of it. Sessions that spawned
implementation agents with a bare instruction will now be denied until the plan path is
included. `CLAUDE_GATE_BYPASS=1` still skips the gate; the hook still fails closed on any
parse error. Behaviour is covered by twelve cases exercised on 2026-07-10, including the
regression that gave rise to this decision: a build agent spawned from `Dev/app` with no plan
named is denied where it was previously allowed.
