---
name: project-mvp-auth-decision
description: "2026-05-28 MVP scope pivot: passwordless invite-only auth via Stalwart; supplier-confirmation magic link deferred; BR-9 cert inheritance kept"
metadata: 
  node_type: memory
  type: project
  originSessionId: 684aabf8-136e-4ec5-910c-b4e7d8b83847
---

# MVP scope decisions (2026-05-28 interview)

These supersede parts of `ai/reqs/brd_mvp.md` v0.3 (BR-10 in particular). See also [[project-validite-state]].

## Auth / registration — NEW, replaces auth half of BR-10
Decision: **passwordless email magic-link login, invite/approval-only signup**, email sent via the existing Stalwart server (`mail.pilier.eu:587`, user `no-reply@pilier.eu`; STARTTLS; `gopkg.in/gomail.v2`).
- Invite-only + passwordless collapse into one flow: the invite email *is* the magic link → click creates a no-password `manager` account + issues JWT.
- Reuse one `magic_tokens`-style collection keyed by `purpose` (invite | login | later: supplier-confirm).
- `SEED_USERS` stays only to bootstrap the first admin.
- **Demo safety:** also render the link on-screen so a flaky inbox can't block a live demo.

**Why:** user already runs Stalwart, so passwordless is far simpler than Google OAuth (no Cloud OAuth client, no Google-account requirement) and reuses one token mechanism.
**How to apply:** when implementing auth, build the token mechanism generically so the deferred supplier-confirmation flow plugs into the same collection.

## The two "magic links" are DIFFERENT — do not conflate
1. **Auth magic link** (passwordless login/registration) — IN SCOPE now.
2. **Supplier document-confirmation link** (original BR-10: supplier in China confirms an invoice) — **DEFERRED, not this round.**
**Why:** user corrected this conflation explicitly; the BRD wrongly bundled both into BR-10.
**How to apply:** "Purchase Order" VTM level now comes only from the manager's manual `PATCH /documents/:id {confirmed}` — treat as a flagged DEMO stub, not real peer confirmation.

## Confirmed in scope
- **P0 cert-attach fix** (GAP-1/2/3): unchanged, first.
- **BR-9 cert inheritance** from `componentDppIds` linked DPPs: yes, build it.
- **Documents section tabs** — split by document type into tabs: Bill of Materials / Production Orders / Invoices (mirror the Certificates My/Supplier tab pattern). **Frontend-only**: backend already enforces exactly these three `docType` values (`invoice`|`bom`|`production-order`) and the list endpoint already filters by `?docType=`. No backend change, no "Other" tab unless the enum is extended later.

## Resolved (interview rounds 2–3, 2026-05-28)
- **Auth cutover:** keep BOTH — password login stays for seeded/admin accounts; passwordless magic-link is the showcased path for new users.
- **Inviter:** any logged-in manager can invite (no admin-only screen; admin/manager split stays deferred).
- **BR-9 picker home:** build a NEW `/dpps/:id` DPP detail page (no detail route exists today). MVP scope = **minimal**: DPP info (GTIN/batch/serial/status) + component-link picker + link to its compliance dossier.
- **Inherited cert presentation:** flat timeline, each inherited event labelled "inherited from <component DPP>" (matches AC-5). Requires `spec_compliance.md` version bump to add the `cert.inherited` event (currently locked, not present).
- **Purchase Order VTM:** manager's manual confirm still grants "Purchase Order", but flag it self-declared/DEMO in the evidence panel.
- **Warehouse role restriction:** DEFERRED entirely this round (stays P2). Focus = auth + BR-9 + P0 cert fix.
- **Component-link picker (MVP):** restrict to DPPs whose product belongs to a registered partner. The partner linkage ALREADY EXISTS via `Product.PartnerID` (a "partner" is just a `companies` record); a DPP resolves to its partner through DPP → Product (by GTIN) → `PartnerID` → Company. No new schema. Block self-link.

## Provenance correction (don't repeat this mistake)
A "partner" = a `companies` record. `Product.PartnerID` already ties every product (and thus its DPPs) to a supplier company. So "component DPP belongs to a registered partner" is achievable NOW — it is NOT deferred. (I wrongly claimed partners don't own DPPs.)

## Post-MVP design topic — needs its own interview
The **invoice-tied** provenance constraint (link only to component DPPs tied to a *confirmed invoice* — you can only link a component you can prove you purchased) IS deferred: it needs the confirmed-invoice/supplier-confirmation flow.
**Why:** same anti-fraud principle as the VTM peer-confirmation model.
**How to apply:** revisit once document confirmation exists.
