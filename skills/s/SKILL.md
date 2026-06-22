---
name: s
description: Send the current plan to the scope agent to check its phasing.
argument-hint: "<path to the plan file; may be empty — I'll take the current active one>"
disable-model-invocation: true
---

Run the `scope` agent on a plan file — the one named in $ARGUMENTS, or, if empty, the current active plan in `ai/plans/`. The `scope` agent checks that the plan is properly phased and writes its verdict directly into the plan file: on PASS, together with the sentinel line the plan-gate hook looks for before it lets a build through; on FAIL, with a list of what to fix.

This agent spawn is allowed by the plan-gate hook because `scope` is on its allowlist, so the command will not be blocked by the gate. Note: `scope` does not author the plan, it only checks the one you already wrote — fixing it against the verdict is your job, not the agent's.
