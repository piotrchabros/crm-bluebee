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
