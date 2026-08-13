---
name: vue_frontend_migration
description: Vue 3 frontend migration for DPP Demo — status, architecture, and key decisions
type: project
---

Vue 3 SPA migration from vanilla HTML for the DPP Demo app was completed.

**Why:** Improve maintainability, add multi-language support (EN/FR/DE/ES/NL), set foundation for future pages.

**Frontend repo:** `/Volumes/SSD/Dev/validite/validite.app/dpp_frontend/`
- Vue 3 + Vite + TypeScript + Pinia + Vue Router 4 + vue-i18n v9
- `npm run build` → `dist/` output
- `npm run dev` with proxy `/v1 → http://localhost:8181`

**Backend changes (`dpp_demo/app/main.go`):**
- Added `//go:embed all:static` + SPA fallback handler (`e.GET("/*", ...)`)
- Static placeholder at `app/static/index.html`

**Dockerfile:** 3-stage build — Node (frontend) → Go (embed dist) → scratch runtime
- `frontend/` submodule at `dpp_demo/frontend/` for Docker build

**Deleted from dpp_demo:** `index.html`, `login.html`, `products.html`, `product.html`, `productdpp.html`, `qrcode.min.js`
- `dpp.html` kept — moves to dedicated server later

**How to apply:** When asked about frontend dev, point to dpp_frontend/. For Docker builds, frontend/ must be a submodule or copied to dpp_demo/frontend/.

**Bug fixes vs old HTML:**
- Refresh token body key: `refresh_token` (old HTML used `refreshtoken` — bug)
- Partner ID form field: `partner_id` (old HTML used `partnerid` — bug)
