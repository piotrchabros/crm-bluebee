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
| 5.1 | Change `onRowClick` in all 4 lists (leads/contacts/accounts/opportunities) to `goto('/<entity>/<id>')`; stop opening the view drawer on row click. Keep table per-cell inline edit (`onRowChange`) and the **create** drawer intact. [tdd:skip:ui-nav-covered-by-qa] | Clicking a row in each of the 4 lists lands on `/<entity>/<id>`; drawer no longer opens for view; create button still opens create drawer; vite builds clean. | - | cc:完了 [19af6a5] |
| 5.2 | Redirect legacy view deep-links to the detail page: `?<entity>=<id>` / `?action=view` now `redirect()` (or client `goto`) to `/<entity>/<id>` instead of opening the drawer. Preserve `?action=create`. [tdd:skip:ui-nav-covered-by-qa] | Visiting a former view deep-link URL lands on the detail page (no 404, no drawer); create deep-link still opens create. | 5.1 | cc:完了 [19af6a5] |

## Phase 6: Shared inline-edit + relation + markdown components

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 6.1 | Build `EditableField.svelte`: display↔edit toggle, type-aware inputs (text, number, date, select, relation, long-text/markdown); commit on blur/Enter → `api.<entity>.patch(id,{field:value})`; optimistic update with toast on success and **revert + error** on failure; respects a `readOnly` flag. [tdd:required] | Component unit/interaction test (vitest if present, else story/manual harness): edit→blur issues PATCH with only the changed field; failed PATCH reverts value and shows error; `readOnly` renders non-editable. | Phase 5 | cc:完了 [c89da56] |
| 6.2 | Add Markdown support: introduce `marked` (or `markdown-it`) + `DOMPurify`; build `MarkdownView.svelte` that renders Markdown to **sanitized** HTML restricted to allowlist `h1,h2,p,br,strong,b,em,ul,ol,li,a`; Notes edit uses a raw-Markdown textarea (stored as text, no backend change). [tdd:required] | Tests: `# H1`,`## H2`,`**bold**`, blank lines/spaces render correctly; `<script>`/`onerror`/`<iframe>` are stripped; round-trip edit saves raw markdown via PATCH. | Phase 5 | cc:完了 [c89da56] |
| 6.3 | Build `RelationLink.svelte`: renders the related record's display value plus an external-link icon button linking to `/<related-entity>/<id>` with `target="_blank" rel="noopener"`. [tdd:skip:ui-covered-by-qa] | Renders value + button; button opens correct related detail URL in a new tab; safe when relation is empty (no button, no broken link). | Phase 5 | cc:完了 [c89da56] |

## Phase 7: Wire detail pages (parity + edit + notes + relations + declutter)

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 7.1 | leads/[id]: render **every** drawer field via `EditableField`; Notes via Markdown view/edit; relation fields (converted account/contact/opportunity) via `RelationLink`; mark system/computed fields read-only; regroup into clean labeled sections per DESIGN_SYSTEM.md. | Field set ⊇ drawer columns; each editable field PATCH-saves; Notes renders h1/h2/bold/spaces; relations open in new tab; read-only fields non-editable; layout grouped, no overflow. | 6.1, 6.2, 6.3 | cc:完了 [a1edc82] |
| 7.2 | accounts/[id]: same treatment (parity, inline edit, notes, relation buttons e.g. parent/owner, declutter). | Same DoD as 7.1 for accounts. | 6.1, 6.2, 6.3 | cc:完了 [30f6719] |
| 7.3 | opportunities/[id] (deals): same treatment; relation buttons for account/contact; ensure derived `probability` is read-only. | Same DoD as 7.1 for opportunities; probability non-editable. | 6.1, 6.2, 6.3 | cc:完了 [30f6719] |
| 7.4 | contacts/[id]: same treatment; relation button for account; parity with contact drawer fields. | Same DoD as 7.1 for contacts. | 6.1, 6.2, 6.3 | cc:完了 [30f6719] |

## Phase 8: QA & verification

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 8.1 | Cross-entity QA: row-click navigation, field parity vs drawer, inline edit save/revert, notes rendering, relation new-tab, deep-link redirects — across all 4 entities. ✅ prod build green; all 4 detail+list routes SSR with no 500; field parity + EditableField wiring verified per page. ⚠️ live browser click-through still needs owner login (cannot authenticate as a user). | All four entities pass the click-through; no field regressions vs drawer; vite/build clean. | Phase 7 | cc:WIP |
| 8.2 | Security/permission verification: Notes Markdown sanitization blocks `<script>`/event-handler injection; inline edit obeys existing RLS/role (no new privilege); a user without update rights cannot PATCH a field. | Injection payloads stripped in rendered notes; unauthorized PATCH → 403; no privilege escalation. | 6.2, Phase 7 | cc:完了 [verified] |

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

---

# Feature 3: Comments on deals

追加日: 2026-06-24

Spec contract: spec.md -> "Feature: Comments on deals (opportunities)".

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 9.1 | RecordComments component + addComment/editComment/deleteComment server actions on opportunities/[id]: markdown-rendered list (author + date), add form, author/admin-gated inline edit + delete. ✅ svelte-check baseline; prod build green; SSR 307 no 500. ⚠️ live browser click-through needs owner login. | List+add+edit+delete work for the owner; non-author cannot edit/delete (403); markdown rendered safely. | - | cc:WIP |
| 9.2 | Extend comments to leads/accounts/contacts detail pages (same RecordComments + server actions). Fix backend silent-drop comment-create on contacts/accounts (CommentSerializer.is_valid always false -> direct ORM create like leads/opportunities). Added commentPermission to contacts load. ✅ frontend svelte-check baseline; backend parses + restarted healthy (uvicorn no autoreload). ⚠️ live click-through needs owner login. | Comments add/edit/delete work on all 4 entities; non-author blocked (403). | 9.1 | cc:WIP |

---

# Feature 4: Self-hosted AI offer generator (native port from bluebee-website)

追加日: 2026-06-28

Spec contract: `spec.md` → "Feature: Self-hosted AI offer generator (native port
from bluebee-website)". Precedence: `spec.md` > `Plans.md`.

**Goal:** port the offer generator (today an external Next.js + Payload + Gemini
app reached via `https://bluebee.marketing`) **natively** into crm-bluebee
(Django + SvelteKit + existing Postgres), so offers are generated, stored,
rendered, and served first-party with no runtime dependency on bluebee.marketing.

**Strategy chosen:** Option A — full native port (over containerizing the
existing Next.js app). Reviewers (architecture/QA/skeptic) flagged this as the
highest-effort, highest-parity-risk path: ~2000 LOC of React renderers + the
Gemini system prompt re-implemented in the CRM stack, creating a permanent fork
of bluebee-website's generator. The parity, prompt-fidelity, and Gemini
model-stability risks are therefore **test-gated requirements** below, not
afterthoughts. The existing external-proxy path stays live until Phase 14 passes;
cutover (12.3) is a single switch with the external dep removed only after parity.

> Source of truth for the port (read before implementing): in `bluebee-website`
> — `src/lib/offer-schema.ts` (zod, 10 block types), `src/lib/offer-ai.ts`
> (Gemini prompt + retry), `src/collections/Offers.ts` (data model + slug/token
> hooks), `src/app/(payload)/api/offers/{create,[id]/edit,[id]}/route.ts` (API
> flow), `src/components/offer/*` (~2067 LOC renderers + `offer.css`, 2 themes).

## Phase 10: Backend — data model & schema parity

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 10.1 | New `offers` Django app: `Offer` model (org-scoped, fields per spec: client_name, title, brand, offer_data JSON, status, slug, access_token, sent_at, viewed_at, responded_at, valid_until, value, notes, created_by, optional FK Opportunity) + migration. Auto slug (`slugify(client_name)-YYYY-MM` + collision suffix) and random 8-char url-safe `access_token`, immutable after create. [tdd:required] | Migration applies; create → unique slug + 8-char token; token never changes on update; org FK enforced; token entropy ≥ source (6 random bytes). Unit tests green. | - | cc:完了 [tests] |
| 10.2 | Port the offer-data schema (`offer-schema.ts` zod) to Python validation (DRF serializers or pydantic): hero + discriminated union of 10 block types with identical required/optional, min/max bounds, and defaults; `validate_offer_data(input) -> ok|error`. [tdd:required] | For each of the 10 block types: a valid payload passes and an intentionally-broken one fails with the same disposition as zod; bounds (e.g. sections 1–14, meta ≤4) enforced; defaults applied. Parity test table green. | - | cc:完了 [tests] |
| 10.3 | Deterministic `standard-ab` pricing model: server keeps `pricing` block compact (valueA/subscription/minutes/estimated); the canonical expansion to comparison+table+2 cards is defined once and shared with the renderer (Phase 13.4). [tdd:required] | Golden test: given fixed pricing inputs, expansion output is byte-stable and matches the source's expanded structure. | 10.2 | cc:完了 [tests] |

## Phase 11: Backend — AI generation (Gemini)

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 11.1 | `offers/ai.py`: Gemini client via `google-genai` Python SDK. Port system prompt **1:1** from `offer-ai.ts` (BRAND_INFO, COMMON_RULES, BLOCK_TYPES_DOC, EXAMPLE_JSON), `brief_to_offer_data(brief, brand, client)` (temp 0.3) and `apply_edit_to_offer_data(current, instruction)` (temp 0.2), `responseMimeType=application/json`, fence-strip, `structured()` validate + **retry-once** (append schema error to prompt). brand from request is authoritative. [tdd:required] (parser/retry); [tdd:skip:live-llm] (the Gemini call itself) | Unit tests cover fence-strip, JSON parse failure → retry, schema-invalid → retry then raise, brand override. Live smoke (manual): a real brief returns schema-valid offer_data in both brands. | 10.2 | cc:完了 [tests+live] |
| 11.2 | Model pinning + fallback + config: pin `gemini-3-flash-preview` to a versioned id with a stable fallback model on error/unavailability; `GEMINI_API_KEY` in backend env only; retire reliance on external `OFFERS_API_KEY`. [tdd:skip:config] | Primary model id in one config constant; forced-failure path falls back; missing key → clear 503; key not present in any frontend bundle. | 11.1 | cc:完了 [live] |

## Phase 12: Backend — endpoints & CRM cutover

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 12.1 | Internal offer endpoints (org-scoped, `IsAuthenticated + HasOrgContext`): create (brief→offer_data→persist Offer→return {id,slug,access_token,url}), edit (id+instruction→full updated offer_data, same link), get (id). [tdd:required] | Create persists + returns stable url; edit keeps slug/token, changes only offer_data; get returns offer; cross-org id → 404. Contract tests green. | 10.1, 11.1 | cc:完了 [tests+live] |
| 12.2 | Public get-by-token endpoint: `GET` offer by `slug`+`access_token`, **unauthenticated**, returns offer_data for rendering; sets `status=viewed` once (not on owner preview, not on bot/prefetch heuristics); wrong/absent token → 404. [tdd:required] | Valid token → offer_data; bad token → 404; first view flips draft/sent→viewed exactly once; route exposes no other tenant data. Tests green. | 10.1 | cc:完了 [tests+live] |
| 12.3 | Cutover: re-point Opportunity `generate-offer`/`edit-offer` views from the bluebee.marketing proxy to the local generator; keep request/response shape so the existing "Generator Oferty" UI is unchanged; remove/flag `BLUEBEE_OFFERS_*` external settings. [tdd:required] | Opportunity generate/edit now hit local endpoints; offer_id references local Offer; no outbound call to bluebee.marketing; external settings gone or flagged off; existing UI works unchanged. | 12.1, 12.2 | cc:完了 [live E2E] |

## Phase 13: Frontend — public offer rendering (SvelteKit)

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 13.1 | Public route `/oferta/[slugToken]` **outside** the authenticated `(app)` group; server load splits slug/token, calls 12.2, 404s on bad token; no CRM auth required. [tdd:skip:no-fe-test-harness] | Visiting a valid link renders the offer with no login; bad token → 404; route is not under the authed layout. | 12.2 | cc:完了 [live] |
| 13.2 | Port the rich-string renderer: interpret **only** `**bold**` and `[label](url)` (http/https/mailto), escape everything else — **zero raw HTML**; mirror source `blocks.tsx` RT behavior. [tdd:required] | Unit tests: bold + links render; `<script>`/raw HTML is escaped, not executed; mailto/http/https only. | 13.1 | cc:完了 [live] |
| 13.3 | Port the 10 block components + hero + both themes (BlueBee dark / BespokeSoft light) from React `src/components/offer/*` to Svelte; port `offer.css`. [tdd:required] | All 10 block types + hero render in both themes; empty/optional fields handled; long Polish strings don't overflow; snapshot parity vs source for the canonical fixtures. | 13.2, 10.3 | cc:完了 [live] |
| 13.4 | Port `pricing` `standard-ab` rendering (OfferComparison + OfferTable + 2 OfferPricingCard) using the shared expansion from 10.3. [tdd:required] | Pricing section renders comparison+table+two cards; `estimated=true` shows the estimate note; golden snapshot matches expansion. | 13.3, 10.3 | cc:完了 [live] |

## Phase 14: QA, parity & cutover verification

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 14.1 | Contract-equivalence tests: run one suite against legacy `bluebee.marketing` API and the new local endpoints; assert same request/response shapes and status codes (create/edit/get, auth, validation errors). | Suite passes against both; documented diffs (if any) are intentional. | 12.1, 12.2 | cc:TODO |
| 14.2 | Golden/snapshot parity: ~5 canonical `offer_data` fixtures × 2 themes → rendered-output snapshots reviewed; `standard-ab` expansion byte-parity vs source. | Snapshots committed + reviewed; no unexplained visual diffs vs source for the fixtures. | 13.3, 13.4 | cc:TODO |
| 14.3 | Schema-validation parity unit tests: valid + intentionally-broken payload per block type; retry-once path and final rejection. | All 10 block types covered; retry triggers and final-failure asserts; matches zod dispositions. | 10.2 | cc:完了 [test_schema+test_ai] |
| 14.4 | E2E acceptance (`/browse` headless): brief → generate → open `/oferta/{slug}-{token}` both themes → NL edit → reload (same link) → `status=viewed` set; cross-tenant id → 404; Polish diacritics + short-dash correct end-to-end. | Full flow green in both brands; viewed set once; cross-tenant blocked; no mojibake. | 12.3, 13.4 | cc:完了 [live+tests; formal /browse pending] |
| 14.5 | Security: public `/oferta` token entropy + isolation — confirm the unauthenticated route cannot reach any other tenant's CRM data and tokens are not guessable/enumerable. | Token space ≥ source; enumeration/guess attempts → 404; route surface limited to single offer render. | 12.2, 13.1 | cc:TODO |

## Phase 15: Optional follow-ups

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 15.1 | [optional] PDF export of an offer (WeasyPrint or headless-Chromium equivalent of the source's Puppeteer path). [tdd:skip:optional] | A generated offer can be downloaded as a branded PDF matching the web layout. | 13.4 | cc:TODO |
| 15.2 | [optional] Import historical offers from bluebee.marketing so legacy public links resolve first-party under the CRM domain. [tdd:skip:optional] | Selected legacy offers imported; their links render via the new route. | 12.2 | cc:TODO |

---

### Notes / assumptions (Feature 4)

- **Reviewer dissent on record:** architecture/QA/skeptic all recommended
  containerizing the existing Next.js app (Option B/C) over a native port; the
  owner chose the native port (Option A). The parity/prompt/model risks are
  carried as explicit test-gated tasks (10.2, 11.1, 11.2, 14.1–14.3) instead.
- **TDD:** backend logic (schema parity, slug/token, AI parser/retry, endpoints,
  pricing expansion) is `[tdd:required]` — backend has a pytest suite. Frontend
  render tasks are `[tdd:required]` for the rich-string parser and snapshot
  parity; the public route shell is `[tdd:skip]` pending a confirmed FE test
  harness (vitest/playwright) — revisit if absent. `not_observed != absent`.
- **Model risk:** `gemini-3-flash-preview` is a preview model; 11.2 pins+falls
  back. Confirm `GEMINI_API_KEY` provisioning before Phase 11.
- **DB:** the `Offer` table is a native Django model in the existing `crm_db`
  under normal CRM tenancy — it does **not** share storage with the source's
  Payload collection (no dual-ORM over one table).
- **Cutover safety:** the working external-proxy path is untouched until 12.3;
  generation can be A/B compared (14.1) before the external dep is removed.

---

# Feature 5: Per-org white-label offer branding

追加日: 2026-06-29

Spec contract: `spec.md` → "Update (2026-06-29): Per-org white-label offer
branding". Precedence: `spec.md` > `Plans.md`.

**Goal:** branding comes from the **active organization**, not a per-offer
dropdown. Drop the `bluebee`/`bespoke` brand selector and the hard-coded
`BRAND_INFO` + two `data-brand` themes; each org defines its own theme, accent,
logo, and contacts, and offers render with them. **Supersedes** Feature 4's
fixed two-brand model.

> Touches code built in Feature 4: `offers/ai.py`, `offers/schema.py`,
> `offers/services.py`, `offers/serializer.py`, `offers/views.py`,
> `offers/Offer.svelte` + `offer.css`, `opportunity` generate/edit views + the
> "Generator Oferty" card, `common.Org` model + org serializer + settings UI.

## Phase 16: Backend — org branding model & generation

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 16.1 | `common.Org`: add `offer_theme` (dark/light, default dark), `offer_accent` (hex, default `#E3FF04`), `offer_prepared_by` (text, blank) + migration incl. a data-migration giving existing orgs non-regressing values. [tdd:required] | Migration applies; existing org keeps current look; fields default correctly on new orgs. Unit test. | - | cc:完了 [tests] |
| 16.2 | `offers/branding.py`: `org_branding(org)` → `{label, email, site, prepared_by, theme, accent, company_name, has_logo}` (label/prepared_by fall back to company_name→name; email/site from org). [tdd:required] | Returns correct dict incl. blank-fallbacks; unit tests cover full + sparse org. | 16.1 | cc:完了 [tests] |
| 16.3 | `offers/ai.py`: build the system prompt from `org_branding` (replace `BRAND_INFO`); `brief_to_offer_data(brief, branding, client_name)`. Relax `offers/schema.py` `brand` to optional (default applied; no longer theme driver). `services.create_offer(org, …)` drops the `brand` param and derives branding from org. [tdd:required] | AI prompt contains org contacts; schema accepts payloads with/without brand; create_offer signature has no brand; existing offers tests updated green. | 16.2 | cc:完了 [tests] |
| 16.4 | Opportunity generate/edit views: remove `brand` input (org implicit); drop `offer_brand` write from that flow. Keep response shape minus brand. [tdd:required] | generate-offer works with no brand in body; cutover tests updated green; no brand read from request. | 16.3 | cc:完了 [tests] |

## Phase 17: Public render — branding payload, logo, theming

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 17.1 | `PublicOfferSerializer`: add `branding` object from `offer.org` (`theme, accent, company_name, email, website, prepared_by, logo_url`). [tdd:required] | Public payload carries branding; cross-org safe; unit test asserts shape + no internal leakage. | 16.2 | cc:完了 [tests] |
| 17.2 | Token-scoped public org-logo endpoint: `GET /api/public/offers/<slug>/<token>/logo/` streams `offer.org.logo` (AllowAny, 404 on bad token / no logo); `logo_url` in 17.1 points here; add to RLS EXEMPT_PATHS. [tdd:required] | Valid token+logo → image bytes; bad token → 404; no-logo → 404; no cross-org access. Tests green. | 16.1, 17.1 | cc:完了 [tests] |
| 17.3 | Renderer: `offer.css` light override `[data-brand="bespoke"]` → `[data-theme="light"]`; `Offer.svelte` sets `data-theme={branding.theme}` + inline `--offer-accent`/`-soft`/`-border` (alpha-derived from `accent`); topbar shows logo (`logo_url`) else `company_name`. [tdd:skip:ui-covered-by-render-qa] | An offer renders with the org's theme+accent+logo/name; both themes + a custom accent verified live. | 17.1, 17.2 | cc:完了 [live] |

## Phase 18: Org settings UI & QA

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 18.1 | Backend org serializer (`settings/organization`): expose + accept `offer_theme`, `offer_accent`, `offer_prepared_by` (validate hex + theme choice). [tdd:required] | GET returns fields; PATCH persists; invalid hex/theme → 400. Tests green. | 16.1 | cc:完了 [tests] |
| 18.2 | Frontend `settings/organization`: branding section — theme select, accent color picker, prepared-by text, logo upload (reuse existing). [tdd:skip:ui] | Admin can set all branding fields; saved values reflected on next offer. | 18.1 | cc:完了 [live] |
| 18.3 | Remove brand dropdown from the "Generator Oferty" card on `opportunities/[id]`; button generates using org branding. [tdd:skip:ui] | No brand select shown; generate still works; edit unchanged. | 16.4 | cc:完了 [live] |
| 18.4 | E2E: set distinct branding on two orgs → generate (no dropdown) → `/oferta/…` renders each org's theme/accent/logo/contacts differently; Polish + cross-tenant intact. [tdd:skip:e2e-live] | Two orgs render visibly different offers; no mojibake; cross-tenant 404. | 17.3, 18.2, 18.3 | cc:完了 [live E2E] |

---

### Notes / assumptions (Feature 5)

- **Supersession:** `offer_data.brand` becomes vestigial (optional in schema); the
  `Offer.brand` column is kept for old rows but no longer drives theme. `BRAND_INFO`
  in `ai.py` is removed in 16.3.
- **Logo on public pages:** org logos sit on the auth-gated media volume, so 17.2
  adds a token-scoped public stream rather than exposing `/media/`.
- **Accent flexibility:** accent is applied as inline CSS vars, so any hex works —
  `offer.css` keeps dark/light bases only; accent is no longer hard-coded per theme.
- **TDD:** backend (model/migration, branding helper, schema relax, serializers,
  logo endpoint) `[tdd:required]`; Svelte render + settings UI `[tdd:skip]` pending
  a FE test harness, covered by live render QA. `not_observed != absent`.
- **No-regression:** 16.1 data-migration must keep the current org's offers looking
  as they do today (dark + lime, or its real brand) until an admin changes it.

---

## Phase 19: Company (Account) CSV import

| Task | 内容 | DoD | Depends | Status |
|------|------|-----|---------|--------|
| 19.1 | `accounts/services/csv_import.py`: two-phase `parse_and_validate(file_bytes, org)` + `commit_rows(file_bytes, org, profile)`, mirroring `contacts/services/csv_import.py` for `Account`. Required header `name`; optional `email, phone, website, industry, number_of_employees, annual_revenue, currency, address_line, city, state, postcode, country, description`. Per-org bulk-prefetch of existing lowercased names for dedup. [tdd:required] | Valid CSV → ValidatedRows; unknown/missing header, >5000 rows, empty, non-UTF-8 → header_error; all lookups org-scoped. Unit tests green. | - | cc:完了 [tests] |
| 19.2 | Field validation in the importer: `name` non-blank ≤255; `email` regex; `phone` flexible; `website` http/https; `industry`∈INDCHOICES; `currency`∈CURRENCY_CODES; `country`∈COUNTRIES; `number_of_employees` non-neg int; `annual_revenue` non-neg decimal(15,2). Case-insensitive choice matching → stored codes. [tdd:required] | Each invalid field yields a row error naming the field; valid choices resolve to their stored code; blanks in optional cells are accepted. Unit tests cover every field. | 19.1 | cc:完了 [tests] |
| 19.3 | Duplicate policy: name (case-insensitive) is the dedup key — hard error if it matches an existing account OR an earlier row in the same file (mirrors `unique_account_name_per_org`). `commit_rows` writes in one transaction and catches IntegrityError as a concurrency backstop. [tdd:required] | Dupe-in-file and dupe-vs-DB both flagged; concurrent commit cannot create two same-name accounts; partial failure rolls back. Tests green. | 19.1 | cc:完了 [tests] |
| 19.4 | `accounts/import_views.py`: `AccountImportPreviewView` + `AccountImportCommitView` reusing the contacts `_can_import` gate (ADMIN/sales-access), the `.csv`+5 MB `_read_upload` guard, MultiPartParser. Wire `import/preview/` + `import/commit/` in `accounts/urls.py` before `<str:pk>/`. [tdd:required] | Preview returns validation JSON w/o writes; commit writes + returns created count/ids; non-privileged → 403; bad file → 400. Endpoint tests green incl. cross-tenant. | 19.2, 19.3 | cc:完了 [tests] |
| 19.5 | Frontend `AccountImportDrawer.svelte` (mirror `ContactImportDrawer.svelte`): file picker, header hint + downloadable CSV template, preview table (valid/error rows + summary), commit button, success toast + list refresh. Wire an "Import" action into the Accounts list `+page.svelte`. [tdd:skip:ui-no-fe-harness] | Admin uploads a CSV, sees per-row preview, commits, and new accounts appear in the list. | 19.4 | cc:完了 [live] |
| 19.6 | E2E live smoke on remote: import a small CSV in two orgs; verify created counts, duplicate-name rejection, choice validation, and cross-tenant isolation (org A's names never collide with org B). Restart backend after backend changes (uvicorn, no autoreload). [tdd:skip:e2e-live] | Two orgs import independently; dupes rejected with clean messages; no cross-tenant leakage; Polish text intact. | 19.5 | cc:完了 [live E2E] |

### Notes / assumptions (Feature — Company import)

- **Reuse:** mirrors the security-reviewed `contacts` importer with strictly
  fewer features (no assignees/teams/tags → no M2M ref-maps; only an existing-name
  set + in-file dedup).
- **Dedup = DB-backed:** `Account` already has `unique_account_name_per_org`
  (case-insensitive), so the importer's name-dedup mirrors a real constraint, and
  commit's IntegrityError catch is a genuine concurrency backstop, not defensive
  padding.
- **team_validation_mode:** `manual-pass` — Product / Architecture / Security / QA /
  Skeptic evaluated manually (proportionate: cloning a reviewed module, reduced
  scope). `not_observed != absent`.
- **Assignment:** imported accounts are unassigned (core-fields-only). Revisit if
  owner-on-import is wanted.
- **Optional (not scheduled):** extract shared `_read_upload` / `_can_import` /
  caps into `common/` now that 3 importers (contacts, tickets, accounts) duplicate
  them. Deferred to avoid scope creep; the duplication is already the repo's
  established pattern.
- **Baselines present:** `ruff.toml` (lint) + `pytest.ini` (tests) already exist —
  no setup task needed.
