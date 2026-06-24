# BlueBee CRM — Product Spec (SSOT)

> Root product contract. Precedence: `spec.md` > sub-spec > `Plans.md`.
> This document fixes *what is correct*; `Plans.md` tracks *what to do*.
> Created 2026-06-23. First contract section: File Attachments.

---

## Feature: File Attachments on CRM records

### Summary

Users can attach files to **leads, contacts, accounts, and opportunities** (and
cases, which already works). Attachments are listed on each record's detail
view, can be uploaded and deleted from the UI, and are isolated per org.

### Data model (existing — do not redesign)

- Storage is the generic `common.models.Attachments` model
  (`ContentType` + `object_id` generic FK), org-scoped, indexed on
  `(content_type, object_id)` and `(org, -created_at)`.
- Files are stored on `FileField(upload_to="attachments/%Y/%m/")` →
  `MEDIA_ROOT=/media` inside the backend container, backed by the persistent
  Docker named volume `media_data` (mounted on backend + celery). Deleting an
  attachment also removes its file via a `post_delete` signal.
- `cases/views.py` is the reference implementation for the upload/list/delete
  pattern; new work copies it rather than inventing a new shape.

### Behavior contract

1. **Upload.** On a record's detail page, a user can upload one file at a time
   via multipart POST to the entity's create/update endpoint using the field
   `<entity>_attachment` (e.g. `lead_attachment`, `opportunity_attachment`).
   The attachment is linked to the record via the generic FK and stamped with
   `created_by` and the caller's `org`.
2. **List.** Each detail page shows existing attachments in the activity
   timeline, newest first, with file name, type icon, uploader, and timestamp,
   and a download link to the file URL.
3. **Delete.** Each attachment has a delete control. Delete goes to
   `/<entity>/attachment/<pk>/` (DELETE).
4. **Validation (server-authoritative).** Uploads are rejected when:
   - file size > **10 MB**, or
   - the extension/MIME is **not** in the allowed business set:
     `pdf, doc, docx, xls, xlsx, ppt, pptx, csv, txt, png, jpg, jpeg, gif,
     webp, zip`.
   Executables/scripts (e.g. `exe, sh, bat, js, msi, dll`) are rejected.
   The UI mirrors these limits for fast feedback, but the server is the trust
   boundary and re-validates every request.
5. **Permissions.**
   - Any active user in the org who can view a record can **upload** to it and
     **view/download** its attachments (existing RLS/role checks apply; the
     feature adds no privileges).
   - **Delete** is allowed only to the attachment's uploader (`created_by`) or
     an org **ADMIN**. Others receive `403`.
   - Org isolation is absolute: a record's attachments are only ever visible or
     mutable within the owning org (enforced by the existing RLS layer; the
     `org` FK on every attachment is mandatory).

### Surfaces

- **leads/[id]**, **accounts/[id]**, **opportunities/[id]**: existing detail
  pages — add upload + delete UI to the already-rendered attachment timeline.
- **contacts/[id]**: **new** detail page (does not exist today) — built to match
  the other three, including the attachment timeline + upload/delete.
- API client (`frontend/src/lib/api.js`): gains `uploadAttachment` (multipart)
  and `deleteAttachment`; `getAttachments` already exists.

### Out of scope (this iteration)

- Multiple-file / drag-and-drop batch upload (single file per action for v1).
- Inline file preview / thumbnails beyond a type icon.
- Virus scanning (size + type allowlist only).
- Exposing attachments through the `bcrm-mcp` MCP server (possible later phase).
- S3/object-storage backend (local media volume is sufficient for now).

### Non-functional / ops

- Media is persisted on the `media_data` Docker volume (not the ephemeral
  container layer) so attachments survive container recreation.
- The daily backup (`ops/crm-bluebee-backup.sh`) archives the container's
  `/media` as `media_<ts>.tar.gz` alongside the DB dump.
- Tests use a temp `MEDIA_ROOT` (`crm/test_settings.py`) so the suite never
  writes into production media.

---

## Feature: Record detail pages as the primary record view

> Added 2026-06-24. Covers leads, contacts, accounts, opportunities (deals).
> Supersedes the read/quick-view role of the NotionDrawer for these entities.

### Summary

Clicking a row in the **leads, contacts, accounts, or opportunities** list
navigates directly to that record's **detail page** (`/<entity>/<id>`) instead
of opening the side drawer. The detail page is the single, full-fidelity view of
a record: it shows **every field the drawer showed**, every field is **editable
in place**, the **Notes** field renders simple rich text from Markdown, and each
field that is a **relation to another record** offers a control to open the
related record in a **new browser tab**.

### Behavior contract

1. **Row click → detail page (no drawer).**
   - In all four list views, clicking a row routes to `/<entity>/<id>` via
     client-side navigation. The view drawer is no longer opened by a row click.
   - The **create** flow still uses the drawer (or its existing create surface);
     only *viewing/opening an existing record* changes.
   - **In-place inline cell editing in the list table is preserved** — only the
     row-open gesture changes, not the table's per-cell quick edit.
   - Deep links that previously opened a record in the drawer
     (e.g. `?<entity>=<id>`, `?action=view`) **redirect** to the detail page
     rather than 404-ing or opening the drawer.

2. **Detail page is a superset of the drawer.**
   - Every field present in the entity's drawer column set appears on the detail
     page. No field that was visible/editable in the drawer is dropped.

3. **Every field editable in place (inline per-field autosave).**
   - Each editable field can be edited directly on the detail page; the change is
     persisted on commit (blur or Enter) via a partial update (`PATCH`) of that
     single field. A success toast confirms; a failure reverts the field to its
     prior value and surfaces an error.
   - **Read-only / system fields are excluded** and rendered non-editable:
     `id`, timestamps (`created_at`, `updated_at`), audit fields (`created_by`),
     and server-derived/computed values (e.g. opportunity `probability` when it
     is derived from stage). These are displayed but never editable.
   - Editing introduces **no new privileges**: the same RLS/role checks that
     gate the existing update endpoints apply unchanged. A user who cannot edit a
     record cannot edit its fields here.

4. **Notes render simple rich text from Markdown.**
   - The Notes field is authored as **Markdown** and rendered to HTML for display.
   - Supported, at minimum: preserved **spaces and line breaks**, **h1**, **h2**,
     and **bold**. Lists and links may also render.
   - Rendering is **sanitized** (server-authoritative trust boundary mirrored on
     the client): output HTML is restricted to an allowlist
     (`h1, h2, p, br, strong/b, em, ul, ol, li, a`); `<script>`, event handlers,
     and any other tags/attributes are stripped. Untrusted Markdown can never
     execute script.
   - Notes are **stored as raw Markdown text** (no data-model change); rendering
     and sanitization happen at display time.

5. **Relation fields can open the related record in a new tab.**
   - Any field that references another entity (e.g. opportunity → account,
     contact → account, lead → converted account/contact/opportunity) shows, next
     to its value, a control that opens the related record's detail page
     (`/<related-entity>/<id>`) in a **new browser tab**, leaving the current
     record open.

### UI quality

- The detail pages are restructured to reduce clutter: fields grouped into clear
  labeled sections, consistent spacing/typography per `DESIGN_SYSTEM.md`, no
  duplicated drawer-only chrome, and a stable two-pane / sectioned layout that
  reads cleanly on desktop and collapses sanely on mobile. "Cluttered" is
  replaced by a defined section grouping per entity.

### Out of scope (this iteration)

- Full Markdown/WYSIWYG (tables, images, code blocks) — only the simple subset
  above is supported for Notes.
- Bulk/multi-field transactional edit with a single Save — editing is per-field.
- Changing the create flow or removing the drawer component itself (still used
  for create and elsewhere).
- New permissions or field-level visibility rules beyond existing RLS/role.

---

## Feature: Comments on records (deals, leads, accounts, contacts)

> Added 2026-06-24.

On the deal, lead, account, and contact detail pages, users can read and post comments. (Endpoints are per-entity: POST /<entity>/<id>/ to create, PATCH/DELETE /<entity>/comment/<commentId>/ to edit/remove.)

- **List**: each comment shows author, relative date, and text rendered as
  sanitized Markdown (same allowlist as Notes), newest first.
- **Add**: a form posts a new comment (POST /opportunities/<id>/ with {comment}).
- **Edit / Delete**: a comment the current user authored (or any comment, if
  ADMIN) has inline edit and delete-with-confirm; others see no edit/delete
  controls. The backend re-enforces author/ADMIN permission
  (PATCH/DELETE /opportunities/comment/<commentId>/), returning 403 otherwise.
- Writes go through SvelteKit server actions (cookie JWT + org context), never
  the client token. The feature adds no new privileges.
