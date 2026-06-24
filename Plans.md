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
