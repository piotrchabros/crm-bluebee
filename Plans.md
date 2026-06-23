# BlueBee CRM — Plans.md

作成日: 2026-06-23

Feature: **File attachments on leads, contacts, accounts, opportunities.**
Backend is ~60% present (generic `Attachments` model + per-entity wiring of
varying completeness; `cases` is the reference impl). This plan finishes the
backend gaps, hardens validation/permissions, and builds the frontend UI.

Spec contract: `spec.md` → "Feature: File Attachments on CRM records".
Precedence: `spec.md` > `Plans.md`.

---

## Phase 1: Backend completion & hardening

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 1.1 | Add shared attachment validator in `common` (size ≤ 10MB, extension/MIME allowlist per spec; reject executables). One reusable function/serializer-validator used by every save path. [tdd:required] | Unit tests: oversize rejected, disallowed ext rejected, allowed types pass; validator importable from `common`. | - | cc:TODO |
| 1.2 | leads: persist uploaded `lead_attachment` on create & update (copy `cases/views.py` pattern; set `content_object`, `created_by`, `org`); run validator from 1.1. | POST multipart to lead create/update saves an `Attachments` row linked to the lead; appears in detail response; test passes. | 1.1 | cc:TODO |
| 1.3 | opportunity: add `opportunity_attachment` read field to serializer **and** persist upload on create & update; run validator. | Opportunity detail serializer returns `opportunity_attachment` list; upload saves linked row; test passes. | 1.1 | cc:TODO |
| 1.4 | Enforce delete permission (uploader `created_by` OR org ADMIN) in all `*AttachmentView` (Lead/Contact/Account/Opportunity/Case). | Non-uploader non-admin DELETE → 403; uploader → 204/200; admin → 204/200; tests cover all three. [tdd:required] | - | cc:TODO |
| 1.5 | Confirm contacts + accounts save paths already meet spec (regression guard) and that all four delete endpoints are routed. | Test matrix: upload+list+delete green for leads/contacts/accounts/opportunities. | 1.2, 1.3, 1.4 | cc:TODO |
| 1.6 | ops: extend daily backup to include `backend/media/` (attachments). [tdd:skip:ops-config] | `crm-bluebee-backup.sh` archives media dir; restore guide updated; Spec skip reason recorded (ops/no app behavior). | - | cc:TODO |

## Phase 2: Frontend API client + shared component

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 2.1 | `frontend/src/lib/api.js`: add `uploadAttachment(id, file)` (multipart/FormData to entity create/update) and `deleteAttachment(attId)`; keep existing `getAttachments`. | Both methods exist per entity factory; hit correct paths; manual call uploads & deletes a file end-to-end against backend. | Phase 1 | cc:TODO |
| 2.2 | Shared Svelte component `AttachmentPanel` (or upload+list controls): file picker, client-side size/type mirror of spec, upload progress/error, list with type icon + download, delete-with-confirm gated by `canDelete` (uploader or admin). | Component renders in isolation; rejects oversize/disallowed client-side; emits upload/delete; delete control hidden when `!canDelete`. [tdd:skip:ui-covered-by-page-qa] | 2.1 | cc:TODO |

## Phase 3: Wire UI into detail pages

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 3.1 | leads/[id]: mount upload + delete UI on the existing attachment timeline. | Can upload, see new attachment without full reload, download, and delete (perms respected) on a lead. | 2.2 | cc:TODO |
| 3.2 | accounts/[id]: same wiring. | Upload/download/delete works on an account. | 2.2 | cc:TODO |
| 3.3 | opportunities/[id]: same wiring. | Upload/download/delete works on an opportunity. | 2.2, 1.3 | cc:TODO |
| 3.4 | contacts: build **new** `contacts/[id]` detail page (server `load` + page) matching leads/accounts, including the attachment timeline + upload/delete. | Navigating to a contact shows detail page; attachments upload/download/delete works; parity with other entities. | 2.2 | cc:TODO |

## Phase 4: QA & verification

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 4.1 | Cross-entity manual QA on staging/live-branch for all four entities (upload, list, download, delete). | Documented pass for leads/contacts/accounts/opportunities; screenshots or notes attached to PR. | Phase 3 | cc:TODO |
| 4.2 | Security/permission verification: non-uploader cannot delete (403), oversize rejected, disallowed type rejected, cross-org isolation holds. | All negative cases verified (automated where possible, else documented). [tdd:required] | Phase 1, Phase 3 | cc:TODO |

---

### Notes / assumptions

- TDD: backend logic tasks are `[tdd:required]` (backend has a pytest suite,
  e.g. `common/tests/`). Frontend test framework presence not yet confirmed —
  component task marked `[tdd:skip:ui-covered-by-page-qa]`; revisit if vitest/
  playwright is found (`not_observed != absent`).
- Single file per upload action in v1 (see spec "Out of scope").
- No new privileges introduced; backend RLS/role checks remain the trust
  boundary. MCP server attachment tool deferred.
