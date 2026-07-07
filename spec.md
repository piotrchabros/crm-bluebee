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

---

## Update (2026-06-24): Attachment serving — authenticated, org-scoped

Supersedes the original "files served from /media" note. Attachment files are no
longer exposed on a public URL. They are streamed through an authenticated proxy
that enforces org isolation:

- Backend `GET /api/attachments/<id>/download/` (`IsAuthenticated` + org context)
  streams the file from the local media volume only when
  `attachment.org == request org`; unknown/cross-org ids return 404.
- Frontend `/files/<id>` SvelteKit route reads the httpOnly `jwt_access` cookie
  and proxies the backend download endpoint to the browser; `AttachmentPanel`
  links to `/files/<id>`.
- The public `/media/` route and its org-context exemption were removed; direct
  `/media/...` access now 404s.
- Storage is unchanged (local `FileSystemStorage` on the media volume); the prod
  `MEDIA_URL`/S3 settings in `server_settings.py` are legacy/unused on Django 6.

Possible future refinement: per-record view-permission check (currently
org-level isolation), and signed time-limited URLs.

---

## Feature: Self-hosted AI offer generator (native port from bluebee-website)

> Spec delta added 2026-06-28. Plans.md contract: "Feature 4: Self-hosted AI
> offer generator (native port)". Precedence: `spec.md` > `Plans.md`.

### Summary

The AI sales-offer generator currently lives in the external `bluebee-website`
app (Next.js 15 + Payload CMS + Google Gemini) and is reached by crm-bluebee
over the public `https://bluebee.marketing` API. This feature **ports the
generator natively into crm-bluebee's own stack** (Django backend + SvelteKit
frontend + the existing Postgres) so offers are generated, stored, rendered, and
served entirely first-party, with **no runtime dependency on bluebee.marketing**.

A salesperson on an Opportunity clicks "Generuj ofertę" (UI already exists),
picks a brand (BlueBee / BespokeSoft), and the CRM — not an external service —
turns the deal's description into a structured offer, persists it, and returns a
public link `…/oferta/{slug}-{accessToken}` that renders a branded offer page.
The "Edytuj ofertę" natural-language edit updates the same link.

> Decision note: a full native port was chosen over containerizing the existing
> Next.js app. Reviewers flagged this as the higher-effort, higher-parity-risk
> path (≈2000 LOC of React renderers + the Gemini prompt re-implemented in the
> CRM stack → a permanent fork of bluebee-website's generator). The parity and
> model-stability risks below are therefore first-class, test-gated requirements,
> not afterthoughts.

### Data model (new — `offers` domain in Django)

- New `Offer` model, **org-scoped** under the same multi-tenant boundary as the
  rest of the CRM (RLS / `org` FK). Fields mirror the source Payload collection,
  restricted to the `data` offer type (the only type the CRM flow uses):
  `org`, `client_name`, `title`, `brand` (`bluebee`/`bespoke`), `offer_data`
  (JSON, the validated structured offer), `status`
  (`draft`/`sent`/`viewed`/`accepted`/`rejected`), `slug`, `access_token`,
  `sent_at`, `viewed_at`, `responded_at`, `valid_until`, `value`, `notes`,
  `created_by`, optional FK to the originating `Opportunity`.
- `slug` auto-derived from `client_name` + `YYYY-MM` with collision suffixing;
  `access_token` random, generated once at create, immutable thereafter. Token
  entropy must be **≥** the source (8 url-safe chars from 6 random bytes) — it is
  the only guard on the public link, so it is a security boundary, not cosmetic.
- The Opportunity keeps its existing `offer_brand` / `offer_id` / `offer_url` /
  `offer_status` fields; `offer_id` now references the local `Offer`.

### Offer-data contract (ported 1:1 from `offer-schema.ts`)

- `offer_data = { brand, hero, sections[] }`. `hero` = `{ eyebrow?, titleLead,
  titleEm, subtitle, meta[≤4] }`. `sections` = 1–14 blocks of a **discriminated
  union of 10 types**: `prose`, `checklist`, `stats`, `techGrid`, `valueGrid`,
  `highlight`, `warmNote`, `table`, `pricing`, `cta` — each with the exact field
  shape, min/max bounds, and defaults of the source zod schema.
- Text fields are **rich strings**: the renderer interprets **only** `**bold**`
  and `[label](url)` links (http/https/mailto). **Zero raw HTML.** Dashes: only
  short `-`.
- `pricing` blocks carry `preset: "standard-ab"` + `valueA`/`subscription`/
  `minutes`/`estimated`; the renderer deterministically **expands** the preset
  into the comparison + table + two pricing cards (this expansion is a
  golden-test target — it puts money on screen).
- Server-side validation is the source of truth and must be **behaviorally
  identical** to the zod schema (same accepts/rejects); on a model
  schema-mismatch the generator **retries once** with the error appended to the
  prompt, then fails with a 422-class error.

### AI generation contract

- Generation calls Google Gemini (source pins `gemini-3-flash-preview`,
  `responseMimeType: application/json`, `temperature` 0.3 for create / 0.2 for
  edit). The system prompt (brand info, hard rules, block-type doc, worked
  example) is ported **1:1**; `brand` from the request is authoritative (never
  taken from the model output).
- `gemini-3-flash-preview` is a **preview** model: the implementation must pin a
  version and define a stable fallback so a model rename/removal does not break
  production. The `GEMINI_API_KEY` lives only in the backend env.
- Two operations: brief → offer_data (create) and current offer_data + NL
  instruction → full updated offer_data (edit; brand preserved, untouched parts
  kept 1:1).

### Behavior contract

1. **Generate.** Opportunity "Generuj ofertę" → backend builds the brief from the
   deal (description ≥ 20 chars, client = account name → fallback opportunity
   name, value = amount, validUntil = close date), calls the **local** generator,
   persists an `Offer`, writes `offer_id`/`offer_url`/`offer_status=generated` on
   the Opportunity, returns the link. No call leaves the server except to Gemini.
2. **Edit.** "Edytuj ofertę" + NL instruction → local edit → same `slug`/
   `access_token`/link; only `offer_data` changes.
3. **Public view.** `GET /oferta/{slug}-{accessToken}` renders the offer page
   **unauthenticated** (it is shared with clients) in the brand theme (BlueBee
   dark / BespokeSoft light). First genuine view sets `status=viewed` once — not
   on owner preview, not on bot prefetch. A wrong/absent token returns 404.
4. **Isolation.** The public offer route exposes **only** that one offer's
   rendered content via its unguessable token; it must not become a path to any
   other tenant's CRM data.

### Surfaces

- Backend: new `offers` Django app/module (model + migration + schema validation
  + Gemini client + internal create/edit/get + public get-by-token); Opportunity
  generate/edit views re-pointed from bluebee.marketing to the local generator.
- Frontend: public SvelteKit route `/oferta/[slugToken]` (outside the
  authenticated app group) re-implementing the rich-string renderer, the 10 block
  components, the hero, both themes, and the `standard-ab` expansion; the existing
  Opportunity "Generator Oferty" card is unchanged in shape.
- Config: `GEMINI_API_KEY` added; `BLUEBEE_OFFERS_*` external-proxy settings
  retired (or feature-flagged off) once cutover is verified.

### Cutover

- The current external-proxy integration (Opportunity → bluebee.marketing) stays
  working until the native path passes parity + E2E, then the CRM is switched to
  the local generator in one change and the external dependency removed.
- Pre-existing public offer links already issued on `bluebee.marketing` continue
  to live on that domain; importing historical offers into the CRM so old links
  resolve first-party is **out of scope** (optional follow-up).

### Out of scope (this iteration)

- PDF export (source uses Puppeteer/Chromium) — optional follow-up.
- The source's `custom` (TSX-in-repo) and `auto` (legacy Gemini-HTML) offer
  types; only the `data` type is ported.
- Payload CMS admin UI for offers (CRM uses its own surfaces).

### Non-functional / ops

- Generation latency ~15–30 s: backend/proxy timeouts must exceed it (existing
  proxy uses 90 s); Gemini 5xx / malformed-output paths return friendly errors.
- Polish correctness end-to-end: diacritics (ł, ż, ś…) and the short-dash rule
  must survive generation, storage, and rendering with no mojibake.

---

## Update (2026-06-29): Per-org white-label offer branding

> Spec delta. Plans.md contract: "Feature 5: Per-org white-label offer
> branding". **Supersedes** the fixed two-brand model in the Feature 4 section:
> the salesperson no longer picks `bluebee`/`bespoke` from a dropdown, and brand
> identity is no longer the hard-coded `BRAND_INFO` map + the two `data-brand`
> CSS themes. Branding now belongs to the **active organization**.

### Summary

Each CRM organization carries its own offer branding. When a salesperson
generates an offer, the branding is read from `request.profile.org` — there is
**no brand selector**. Two different orgs produce visually and contactually
distinct offers from the same generator.

### Org branding model (new fields on `common.Org`)

Reuses existing Org fields — `name`/`company_name`, `email`, `website`, `logo`
(ImageField) — and adds:
- `offer_theme` — `dark` | `light` (default `dark`). Selects the base palette.
- `offer_accent` — hex color (default `#E3FF04`). The single accent driving
  links, headings, chips, pricing highlights, etc.
- `offer_prepared_by` — optional signature text (e.g. "BespokeSoft (Dawid
  Kawalec)"); defaults to `company_name`/`name` when blank.

A data migration sets sensible values on existing orgs (no visual regression for
the current org).

### Generation contract (changed)

- `create_offer(org, *, client_name, brief, …)` derives a **branding dict** from
  the org via `offers.branding.org_branding(org)`:
  `{label, email, site, prepared_by, theme, accent, company_name, has_logo}`.
- The Gemini system prompt is built from this branding (replaces `BRAND_INFO`):
  eyebrow `Oferta współpracy · {label} × {client}`, CTA email/site, "Ofertę
  przygotował {prepared_by}". The contact details are baked into `offer_data`
  text at generation time (a snapshot of the org's contacts).
- `offer_data.brand` (the old `bluebee`/`bespoke` enum) is **relaxed to optional**
  in the schema and is no longer the theme driver; it may be dropped from output.
- The Opportunity generate/edit endpoints and the "Generator Oferty" card **lose
  the brand field**; branding is implicit from the org.

### Public render contract (changed)

- The public payload (`/api/public/offers/<slug>/<token>/`) includes a
  `branding` object derived from `offer.org`: `{theme, accent, company_name,
  email, website, prepared_by, logo_url}`.
- The renderer applies the theme via `data-theme="dark|light"` on `.offer-root`
  and sets `--offer-accent` (+ derived soft/border alphas) **inline** from
  `accent` — so any accent color works, not just the two presets. `offer.css`'s
  light override moves from `[data-brand="bespoke"]` to `[data-theme="light"]`.
- The topbar shows the org **logo** when present, else the **company name** text.
- **Logo on a public page:** org logos live on the auth-gated media volume, so a
  **token-scoped public logo endpoint** streams `offer.org.logo` for a valid
  `slug`+`token` (no login, no other-org exposure). `logo_url` points at it.

### Management (org settings UI)

- The org branding fields are editable on `settings/organization` (backend org
  serializer + frontend page): theme select, accent color, prepared-by, and the
  existing logo upload. Admin-scoped like other org settings.

### Out of scope (this iteration)

- Per-brand multiple offer templates beyond theme+accent+logo+contacts.
- Per-user (vs per-org) branding; brand A/B within one org.


## Feature: Company (Account) CSV import

### Summary

Bulk-create companies (`accounts.Account`) from a CSV file, using the same
two-phase preview→commit importer already shipped for contacts. **Core company
fields only** — no assignees/teams/tags/contact links in this iteration.

### Behavior contract

- **Surface:** an "Import" action on the Accounts list opens a drawer (mirrors
  `ContactImportDrawer`). Phase 1 `POST /api/accounts/import/preview/` validates
  and returns row-level results **without writing**. Phase 2
  `POST /api/accounts/import/commit/` re-validates and writes in one transaction.
- **Permissions:** ADMIN or explicit sales-access only (same `_can_import` gate
  as contacts). Others get 403.
- **Caps:** ≤ 5 MB, ≤ 5000 data rows, `.csv` extension, UTF-8 (with/without BOM)
  only; size enforced against bytes read, not client Content-Length.
- **Headers:** required `name`; optional `email, phone, website, industry,
  number_of_employees, annual_revenue, currency, address_line, city, state,
  postcode, country, description`. Unknown headers → header error.
- **Duplicate policy (per org):** company **name** is the dedup key,
  case-insensitive. A row whose name matches an existing account, or an earlier
  row in the same file, is a **hard error** (skipped on commit). This mirrors the
  DB `unique_account_name_per_org` constraint so users see a clean row-level
  message instead of an IntegrityError; commit also catches IntegrityError as a
  concurrency backstop.
- **Field validation:** `name` ≤255 non-blank; `email` well-formed if present;
  `phone` flexible-phone; `website` http/https URL; `industry` ∈ INDCHOICES;
  `currency` ∈ CURRENCY_CODES; `country` ∈ COUNTRIES; `number_of_employees`
  non-negative int; `annual_revenue` non-negative decimal (≤15 digits, 2 dp).
  Invalid choice/format → row error naming the field.
- **Isolation:** every reference/duplicate lookup is scoped to the caller's org;
  a CSV cannot reach or collide across tenants.
- **Assignment:** imported accounts are created **unassigned** (no owner/team),
  consistent with core-fields-only. Owners can be set afterward.

### Out of scope (this iteration)

- Assignees / teams / tags / linked-contacts columns (contacts importer has them;
  accounts import defers).
- Upsert/update-on-match and skip-silently modes (error-only this iteration).
- Excel (.xlsx) upload; CSV only.
- Match keys other than name (website/email dedup).
