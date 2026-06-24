# BlueBee CRM — Plans.md

作成日: 2026-06-23

Feature: **File attachments on leads, contacts, accounts, opportunities.**
Backend is ~60% present (generic `Attachments` model + per-entity wiring of
varying completeness; `cases` is the reference impl). This plan finishes the
backend gaps, hardens validation/permissions, and builds the frontend UI.

Spec contract: `spec.md` → "Feature: File Attachments on CRM records".
Precedence: `spec.md` > `Plans.md`.

---

> **2026-06-23 findings correction (after code re-verification):** the backend
> is ~90% pre-built. ALL FOUR entities + cases already persist uploads on
> create & update, list attachments, and have delete views. So 1.2/1.3 were
> already implemented. The genuine gaps were: file validation (1.1), a delete
> permission bug (1.4), and media backup (1.6). The real remaining work is the
> **frontend** (Phases 2–3).

## Phase 1: Backend completion & hardening

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 1.1 | Add shared attachment validator in `common` (size ≤ 10MB, extension allowlist; reject executables). Enforced via `Attachments.clean()` (called by `full_clean()` in `save()`) so every save path is covered. [tdd:required] | Unit tests: oversize rejected, disallowed ext rejected, allowed types pass. ✅ 8 tests pass. | - | cc:完了 [68c26cd] |
| 1.2 | leads: persist uploaded `lead_attachment` on create & update. | **Already implemented** (`lead_views.py:292`, `:568`). Verified by existing tests + live behavior; now also covered by validation. | 1.1 | cc:完了 [pre-existing] |
| 1.3 | opportunity: persist upload on create & update; return attachments in detail. | **Already implemented** (`opportunity_views.py:299`, `:472`; attachments returned in view response dict, frontend already reads them). | 1.1 | cc:完了 [pre-existing] |
| 1.4 | Fix delete permission so uploader can delete (was `profile == created_by`, Profile vs User → always False; only ADMIN could delete). Now `profile.user == created_by` in Contact/Account/Case/Opportunity views (Lead already correct). | Non-uploader non-admin DELETE → 403; uploader → 200; admin → 200. ✅ delete-perm tests pass. | - | cc:完了 [68c26cd] |
| 1.5 | Regression guard across all entities + custom 400 handler for Django ValidationError. | ✅ 49 attachment tests pass; live E2E: disallowed→400, oversize→400, upload→saved, delete→200. | 1.2, 1.3, 1.4 | cc:完了 [036046b] |
| 1.6 | ops: back up media; fix durability + test isolation. [tdd:skip:ops-config] | ✅ backup archives container `/media`; `media_data` volume added (was ephemeral); post_delete removes file; test_settings isolates MEDIA_ROOT. | - | cc:完了 [036046b] |

## Phase 2: Frontend API client + shared component

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 2.1 | `frontend/src/lib/api.js`: add `uploadAttachment(id, file)` (multipart/FormData) and `deleteAttachment(attId)`; FormData-aware `apiRequest`. | ✅ Both methods per entity factory; verified via live E2E upload+delete. | Phase 1 | cc:完了 [03f5ad0] |
| 2.2 | Shared `AttachmentPanel.svelte`: file picker, client-side size/type mirror, upload/delete with toasts + invalidateAll, delete gated by uploader/admin. | ✅ Component built; client validation mirrors backend; delete hidden when `!canDelete`. | 2.1 | cc:完了 [03f5ad0] |

## Phase 3: Wire UI into detail pages

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 3.1 | leads/[id]: mount AttachmentPanel in Files tab. | ✅ Wired; vite compiles clean; backend E2E confirms upload/delete on leads. | 2.2 | cc:完了 [03f5ad0] |
| 3.2 | accounts/[id]: same wiring. | ✅ Wired (Files tab → AttachmentPanel). | 2.2 | cc:完了 [03f5ad0] |
| 3.3 | opportunities/[id]: same wiring. | ✅ Wired (Files tab → AttachmentPanel). | 2.2, 1.3 | cc:完了 [03f5ad0] |
| 3.4 | contacts: build **new** `contacts/[id]` detail page + AttachmentPanel; "Open full page" link from drawer. | ✅ New route (page + server load); reachable from contacts list drawer. | 2.2 | cc:完了 [03f5ad0] |

## Phase 4: QA & verification

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 4.1 | Cross-entity QA (upload, list, download, delete). | ✅ Backend E2E green on live API (leads path exercised end-to-end). ⚠️ Browser click-through of the UI still needs the owner (cannot log in as user). | Phase 3 | cc:WIP |
| 4.2 | Security/permission verification: non-uploader cannot delete (403), oversize rejected, disallowed type rejected, cross-org isolation. | ✅ delete-perm tests (403/200), oversize→400, disallowed→400, double-extension blocked; org-mismatch enforced by model clean. | Phase 1, Phase 3 | cc:完了 [036046b] |

---

### Notes / assumptions

- TDD: backend logic tasks are `[tdd:required]` (backend has a pytest suite,
  e.g. `common/tests/`). Frontend test framework presence not yet confirmed —
  component task marked `[tdd:skip:ui-covered-by-page-qa]`; revisit if vitest/
  playwright is found (`not_observed != absent`).
- Single file per upload action in v1 (see spec "Out of scope").
- No new privileges introduced; backend RLS/role checks remain the trust
  boundary. MCP server attachment tool deferred.

---

# Feature 2: Record detail pages as primary view

追加日: 2026-06-24

Goal: clicking a row in **leads / contacts / accounts / opportunities (deals)**
opens the **detail page** (`/<entity>/<id>`) instead of the drawer; the detail
page shows everything the drawer showed, makes every field inline-editable
(per-field PATCH autosave), renders **Notes** as sanitized Markdown
(spaces, h1, h2, bold), and adds an **open-in-new-tab** control beside every
relation field. UI is restructured to reduce clutter.

Spec contract: `spec.md` → "Feature: Record detail pages as the primary record view".
Precedence: `spec.md` > `Plans.md`.

Decisions (locked 2026-06-24): Notes = **Markdown syntax**; editing =
**inline per-field autosave**; relation control = **new browser tab**.

Codebase facts (verified): detail routes already exist for all 4 entities
(`/<entity>/[id]/+page.svelte`); all 4 lists do `onRowClick → drawerOpen = true`;
`api.js` already exposes `patch(id, data)` (PATCH) and `update` (PUT); Notes
today render as `whitespace-pre-wrap` plain text; **no** markdown/sanitizer/
editor lib exists in the repo yet; relation fields exist as `type:'relation'`
in each entity's drawer column set.

## Phase 5: Navigation — list rows open detail pages

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 5.1 | Change `onRowClick` in all 4 lists (leads/contacts/accounts/opportunities) to `goto('/<entity>/<id>')`; stop opening the view drawer on row click. Keep table per-cell inline edit (`onRowChange`) and the **create** drawer intact. [tdd:skip:ui-nav-covered-by-qa] | Clicking a row in each of the 4 lists lands on `/<entity>/<id>`; drawer no longer opens for view; create button still opens create drawer; vite builds clean. | - | cc:TODO |
| 5.2 | Redirect legacy view deep-links to the detail page: `?<entity>=<id>` / `?action=view` now `redirect()` (or client `goto`) to `/<entity>/<id>` instead of opening the drawer. Preserve `?action=create`. [tdd:skip:ui-nav-covered-by-qa] | Visiting a former view deep-link URL lands on the detail page (no 404, no drawer); create deep-link still opens create. | 5.1 | cc:TODO |

## Phase 6: Shared inline-edit + relation + markdown components

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 6.1 | Build `EditableField.svelte`: display↔edit toggle, type-aware inputs (text, number, date, select, relation, long-text/markdown); commit on blur/Enter → `api.<entity>.patch(id,{field:value})`; optimistic update with toast on success and **revert + error** on failure; respects a `readOnly` flag. [tdd:required] | Component unit/interaction test (vitest if present, else story/manual harness): edit→blur issues PATCH with only the changed field; failed PATCH reverts value and shows error; `readOnly` renders non-editable. | Phase 5 | cc:TODO |
| 6.2 | Add Markdown support: introduce `marked` (or `markdown-it`) + `DOMPurify`; build `MarkdownView.svelte` that renders Markdown to **sanitized** HTML restricted to allowlist `h1,h2,p,br,strong,b,em,ul,ol,li,a`; Notes edit uses a raw-Markdown textarea (stored as text, no backend change). [tdd:required] | Tests: `# H1`,`## H2`,`**bold**`, blank lines/spaces render correctly; `<script>`/`onerror`/`<iframe>` are stripped; round-trip edit saves raw markdown via PATCH. | Phase 5 | cc:TODO |
| 6.3 | Build `RelationLink.svelte`: renders the related record's display value plus an external-link icon button linking to `/<related-entity>/<id>` with `target="_blank" rel="noopener"`. [tdd:skip:ui-covered-by-qa] | Renders value + button; button opens correct related detail URL in a new tab; safe when relation is empty (no button, no broken link). | Phase 5 | cc:TODO |

## Phase 7: Wire detail pages (parity + edit + notes + relations + declutter)

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 7.1 | leads/[id]: render **every** drawer field via `EditableField`; Notes via Markdown view/edit; relation fields (converted account/contact/opportunity) via `RelationLink`; mark system/computed fields read-only; regroup into clean labeled sections per DESIGN_SYSTEM.md. | Field set ⊇ drawer columns; each editable field PATCH-saves; Notes renders h1/h2/bold/spaces; relations open in new tab; read-only fields non-editable; layout grouped, no overflow. | 6.1, 6.2, 6.3 | cc:TODO |
| 7.2 | accounts/[id]: same treatment (parity, inline edit, notes, relation buttons e.g. parent/owner, declutter). | Same DoD as 7.1 for accounts. | 6.1, 6.2, 6.3 | cc:TODO |
| 7.3 | opportunities/[id] (deals): same treatment; relation buttons for account/contact; ensure derived `probability` is read-only. | Same DoD as 7.1 for opportunities; probability non-editable. | 6.1, 6.2, 6.3 | cc:TODO |
| 7.4 | contacts/[id]: same treatment; relation button for account; parity with contact drawer fields. | Same DoD as 7.1 for contacts. | 6.1, 6.2, 6.3 | cc:TODO |

## Phase 8: QA & verification

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 8.1 | Cross-entity QA: row-click navigation, field parity vs drawer, inline edit save/revert, notes rendering, relation new-tab, deep-link redirects — across all 4 entities. | All four entities pass the click-through; no field regressions vs drawer; vite/build clean. | Phase 7 | cc:TODO |
| 8.2 | Security/permission verification: Notes Markdown sanitization blocks `<script>`/event-handler injection; inline edit obeys existing RLS/role (no new privilege); a user without update rights cannot PATCH a field. | Injection payloads stripped in rendered notes; unauthorized PATCH → 403; no privilege escalation. | 6.2, Phase 7 | cc:TODO |

---

### Notes / assumptions (Feature 2)

- Backend needs **no** data-model change: PATCH endpoints already exist
  (`api.js#patch`), Notes already stored as text. If any entity's update endpoint
  rejects single-field partials, extend that view to accept partial payloads
  (track as a sub-task when found; `not_observed != absent`).
- `marked` + `DOMPurify` are new frontend deps; sanitization allowlist is the
  trust boundary for Notes rendering.
- Frontend test framework presence not yet confirmed; `[tdd:required]` tasks fall
  back to a manual/interaction harness if vitest/playwright is absent — revisit.
- The drawer component is **not** removed; it still serves create and other uses.
