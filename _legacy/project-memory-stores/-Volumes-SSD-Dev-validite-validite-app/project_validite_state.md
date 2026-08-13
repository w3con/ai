---
name: project_validite_state
description: "Current implementation state of Validité DPP platform — what's built, what's pending, key architecture facts"
metadata: 
  node_type: memory
  type: project
  originSessionId: 19892c1b-3419-43e0-b3b9-7515b384e232
---

# Validité DPP Platform — State as of 2026-05-28

## What's built (MVP complete)

### Backend (Go/Echo, single process)
Split across 4 Go files in `dpp_demo/app/`:
- **`main.go`** — server setup, auth, partners (GET/POST/PUT/DELETE `/v1/companies`), products (`/v1/products`), DPPs (`/v1/product-dpp`, `/v1/passports`), indexes, permissions, user seeding, SPA serving
- **`certificates.go`** — full cert CRUD + LLM parse pipeline; routes: `POST/GET/DELETE /v1/certificates`, `/:id/parse`, `/:id/attach`, `/:id/detach`, `/:id/file`; plus back-compat public `GET /v1/products/:gtin/certs/:id`
- **`compliance.go`** — compliance aggregator; routes: `GET /v1/compliance`, `GET /v1/compliance/:dppId`; builds event timeline from DPP lifecycle + cert events + doc events; VTM badges inline on events
- **`documents.go`** — document CRUD + startup seed; routes: `POST/GET /v1/documents`, `/:id`, `/:id/file`, `PATCH /:id` (status toggle), `DELETE /:id`

### Frontend (Vue 3 + Vite + TS, `dpp_frontend/`)
All sections implemented:
- **DocumentsView** — upload modal (file + docType + partner + linkedDpp), per-row "Mark confirmed" + delete + view file (hidden for demoSeed rows)
- **CertificatesView** — 2 tabs (My / Supplier), upload modal with ownedBy toggle + partner picker, 5s polling for parse
- **CertificateDetailView** — parse-failed banner + Retry button, expiry banner, parsed fields display (scope vs transaction), attached GTINs table with Attach/Detach
- **ComplianceView** — list of DPPs with eventCount + lastActivity
- **ComplianceDetailView** — chronological timeline, VTM badges (clickable → evidence side panel), Export PDF toast
- **AppHeader** — hamburger menu, Production group (Documents, Products, DPPs), Partners, Certificates, Compliance; language switcher (5 locales)
- **PassportsView** — DPP list with "Manage" link per row → `/dpps/:id`
- **DppDetailView** — GTIN/batch/serial info, link to compliance dossier, component DPP list with add/remove picker, save via PATCH `/v1/dpps/:id`
- **ProductView** — real cert attach/detach (replaces old stubs); "Link certificate" picker modal

### Router (`dpp_frontend/src/router/index.ts`)
All routes registered. Redirects: `/passports → /dpps`, `/companies → /partners`.

### i18n
All 5 locales have keys for: `docs.*`, `certList.*`, `certDetail.*`, `compliance.*`, `complianceDetail.*`, `nav.*`.

### Public viewer (`dpp-vldt/`)
Minimal GS1 path parser → fetches product data from API. Shows DPP info + certificates + materials.

## Key architecture facts

- **LLM pipeline**: `ANTHROPIC_API_KEY` env → `claude-sonnet-4-6` model → PDF → structured JSON → `parsedFields`. Max 4 concurrent parses (semaphore). 90s server timeout. On missing API key: cert is **deleted** (not kept with error). Status: `parsing` → `ai-validated` or cert deleted on failure.
- **GridFS**: used for both cert PDFs and document files. Bucket shared.
- **Permissions**: `admin` + `manager` = full access (`*`). `warehouse` = read-only + DPP create. `partner` = read certs/docs/compliance, manage products. Seeded fresh on every startup.
- **Demo stubs tracked**: `DEMO-DOC-1` (7 startup seed docs), `DEMO-CERT-1` (no supplier login), `DEMO-VTM-1` through `DEMO-VTM-5` (Mass Balance, Storage, Purchase Confirmation, Supplier Identity, Certs Audited all capped).
- **SPA routing**: single binary serves both SPAs by Host header (`vldt.eu` → dpp-vldt, everything else → dpp_frontend). Build dirs must be present before `go build`.
- **Auth**: JWT HS256, access 15min + refresh 7d. Admin role bypasses permission check. Non-admin roles: user fetched from DB on every request.

## Gaps plan progress (ai/plans/plan_mvp_gaps.md)

| Phase | What | State |
|-------|------|-------|
| A | GAP-1/2/3: cert attach/detach UX | ✅ done |
| B | GAP-4/5/6: DPP linking + cert.inherited + DppDetailView | ✅ done |
| C | GAP-7: passwordless auth (magic-link, invite, Stalwart SMTP) | ✅ done |
| D | GAP-8: Documents type tabs (frontend-only) | ✅ done |

## Key additions from Phase D (2026-05-28)

- `DocumentsView.vue`: 3 tabs (Invoices / BoM / Production Orders); `?docType=` filter on load; upload modal defaults to active tab; no backend change; no new i18n keys (reuses `docs.docType_*`)
- `plan_mvp_gaps.md` fully complete — all GAP-1..8 implemented

## Key additions from Phase C (2026-05-28)

- `auth_magic.go`: `MagicToken` struct + `magic_tokens` collection (TTL index); `initMagicTokens()`
- 4 new endpoints: `POST /v1/auth/magic/request`, `GET /v1/auth/magic`, `POST /v1/auth/magic/confirm`, `POST /v1/auth/invite`
- gomail.v2 dependency added; SMTP reads `EMAIL_TRANSPORT_DEFAULT_{HOST,PORT,USERNAME,PASSWORD}`; link always returned in response (demo fallback)
- `docker-compose.yml` wires all 4 SMTP vars from `.env`
- `LoginView.vue`: password/magic-link tabs; demo link shown if SMTP not configured
- `MagicConfirmView.vue` at `/auth/magic/:token` (public route)
- `AppHeader.vue`: "Invite User" button + modal (manager-only)
- `stores/auth.ts`: `requestMagicLink`, `confirmMagic`, `invite` methods

## Key additions from Phase B (2026-05-28)

- `ProductDPP` struct: `ID primitive.ObjectID` + `ComponentDppIds []primitive.ObjectID`
- `GET /v1/dpps/:id` + `PATCH /v1/dpps/:id` (new namespace, avoids GS1 wildcard)
- `listPassports` now returns `id` per row
- `compliance.go`: `cert.inherited` event type; VTM Certificates uses highest-rank wins; `EventRefs.ComponentDppId`
- `DppDetailView.vue` at `/dpps/:id`; all 5 locales have `dppDetail.*` keys

## Collections in MongoDB
`users`, `companies`, `products`, `product-dpp`, `certificates`, `documents`, `permissions`, `fs.files`, `fs.chunks` (GridFS)
