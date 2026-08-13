---
name: project-app-no-real-data-yet
description: The Validité DPP platform (the application repository) currently holds no real production data, only test/demo records, and the coordinator DOES have direct Mongo access via docker exec — verify environment claims from old plan text before repeating them.
metadata:
  type: project
  scope: app
---

The database behind the Validité DPP platform (the application repository — Go backend
`dpp_demo/app`, Mongo) currently contains no data from real use — no real companies, no real users, no real certificates
or invoices. Everything in it right now is test or demo data that can be wiped or recreated at
will, with no consequence to any actual customer or operator.

**Why this matters.** Plan documents in `ai/plans/` sometimes describe a step's motivation in terms
that read as if real, accumulated production data is at risk — for example the plan text for
`PLT-5.8.0` in `ai/plans/plan_audit-fixes.md` says building a unique index over "already dirty
data" would crash the app at startup, and frames the step as a safeguard against corrupting live
records. That sentence was written as general engineering reasoning (it is technically true *if*
duplicate data existed), not as a claim that such data exists today. Repeating it as though it
describes an actual present risk is wrong and misleads Alex about what is actually at stake. Alex
has corrected this more than once; forgetting it again is the failure this memory exists to stop.

**How to apply.** When a plan phase's rationale leans on "protect existing/live/production data,"
check first whether the claim is about data that actually exists yet, not just repeat the plan
document's original wording. State it plainly: there is no real data at stake, only test/demo
records. Re-verify this fact against current reality before trusting it in a later session — once
the platform goes live, this memory becomes stale and should be updated or removed.

**Correction, same day.** An earlier draft of this memory also claimed "the coordinator has no
direct database access, only Alex does via `! <command>`" — copied uncritically from
`ai/plans/plan_audit-fixes.md`'s PLT-5.8.0 text without testing it. That claim was false and Alex
called it out directly. The coordinator has full shell access on this machine via the `Bash` tool,
the Mongo container is reachable with a plain `docker exec mongo mongosh "mongodb://admin:<password
from the repo's own .env, MONGO_PASSWORD>@localhost:27017/dpp?authSource=admin" --eval '...'`, and
this was proven by actually connecting and running read queries directly — no `!` and no Alex
involvement needed. The lesson generalizes past this one plan line: never repeat an "I can't do
X"/"only Alex can do X" claim found in a document without first trying X. The two demo organizations
and their SIREN/SIRET come from a startup backfill in `internal/tenancy`; seeded users come from the
`SEED_USERS` environment variable; `scripts/gen-demo-invoices/` generates a handful of clearly-fake
invoice PDFs for the specific manual demo of uploading/parsing/deleting an invoice in front of a
client — it writes files, not database rows, and needs a manual upload through the app.
