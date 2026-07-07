/**
 * Opportunity Detail Page - Server Load
 *
 * Django endpoint: GET /api/opportunities/<id>/
 * Response shape: { opportunity_obj, comments, attachments, contacts, users, stage, lead_source, currency, comment_permission, users_mention, custom_field_definitions }
 */

import { error, fail } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ params, locals, cookies }) {
  const org = locals.org;
  if (!org) {
    throw error(401, 'Organization context required');
  }

  try {
    const response = await apiRequest(`/opportunities/${params.id}/`, {}, { cookies, org });

    if (response?.error) {
      throw error(404, response.errors || 'Opportunity not found');
    }

    const opportunity = response.opportunity_obj || null;

    return {
      opportunity,
      comments: response.comments || [],
      attachments: response.attachments || [],
      contacts: response.contacts || [],
      users: response.users || [],
      commentPermission: response.comment_permission || false,
      customFieldDefinitions: response.custom_field_definitions || [],
      customFieldValues: opportunity?.custom_fields || {}
    };
  } catch (err) {
    // SvelteKit `error()` throws a special object — let it bubble.
    if (/** @type {any} */ (err)?.status) throw err;
    console.error('Failed to load opportunity detail:', err);
    throw error(500, 'Failed to load opportunity');
  }
}

/** @type {import('./$types').Actions} */
export const actions = {
  uploadAttachment: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const file = form.get('file');
    if (!file || typeof file === 'string') return fail(400, { error: 'No file provided' });
    const fd = new FormData();
    fd.append('opportunity_attachment', file);
    try {
      await apiRequest(`/opportunities/${params.id}/`, { method: 'POST', body: fd }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Upload opportunities attachment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to upload attachment' });
    }
  },
  deleteAttachment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const attachmentId = form.get('attachmentId')?.toString();
    if (!attachmentId) return fail(400, { error: 'Missing attachment id' });
    try {
      await apiRequest(`/opportunities/attachment/${attachmentId}/`, { method: 'DELETE' }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Delete opportunities attachment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to delete attachment' });
    }
  },
  addComment: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const comment = (form.get('comment')?.toString() || '').trim();
    if (!comment) return fail(400, { error: 'Comment cannot be empty' });
    try {
      await apiRequest(
        `/opportunities/${params.id}/`,
        { method: 'POST', body: { comment } },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Add opportunity comment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to add comment' });
    }
  },
  editComment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const commentId = form.get('commentId')?.toString();
    const comment = (form.get('comment')?.toString() || '').trim();
    if (!commentId || !comment) return fail(400, { error: 'Missing comment text' });
    try {
      await apiRequest(
        `/opportunities/comment/${commentId}/`,
        { method: 'PATCH', body: { comment } },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Edit opportunity comment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to edit comment' });
    }
  },
  deleteComment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const commentId = form.get('commentId')?.toString();
    if (!commentId) return fail(400, { error: 'Missing comment id' });
    try {
      await apiRequest(
        `/opportunities/comment/${commentId}/`,
        { method: 'DELETE' },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Delete opportunity comment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to delete comment' });
    }
  },
  updateField: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const field = form.get('field')?.toString();
    const raw = form.get('value')?.toString() ?? 'null';
    if (!field) return fail(400, { error: 'Missing field' });
    let value;
    try {
      value = JSON.parse(raw);
    } catch {
      return fail(400, { error: 'Malformed value payload' });
    }
    try {
      await apiRequest(
        `/opportunities/${params.id}/`,
        { method: 'PATCH', body: { [field]: value } },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Update opportunities field error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to save field' });
    }
  },
  updateCustomFields: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const raw = form.get('custom_fields')?.toString() || '{}';
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return fail(400, { error: 'Malformed custom_fields payload' });
    }
    try {
      await apiRequest(
        `/opportunities/${params.id}/`,
        { method: 'PATCH', body: { custom_fields: parsed } },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Update opportunity custom fields error:', err);
      return fail(400, {
        error: /** @type {any} */ (err)?.message || 'Failed to save custom fields'
      });
    }
  },
  // Generate a BlueBee AI offer for this opportunity. The Django proxy holds the
  // API key and writes offer_id/offer_url/offer_brand/offer_status on success.
  generateOffer: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const brand = form.get('brand')?.toString() || undefined;
    try {
      const res = await apiRequest(
        `/opportunities/${params.id}/generate-offer/`,
        { method: 'POST', body: brand ? { brand } : {} },
        { cookies, org: locals.org }
      );
      return { success: true, action: 'generateOffer', offerUrl: res?.url };
    } catch (err) {
      console.error('Generate offer error:', err);
      return fail(400, {
        action: 'generateOffer',
        error: /** @type {any} */ (err)?.message || 'Failed to generate offer'
      });
    }
  },
  // Apply a natural-language edit to the already-generated offer (same link).
  editOffer: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const instruction = (form.get('instruction')?.toString() || '').trim();
    if (instruction.length < 3) {
      return fail(400, { action: 'editOffer', error: 'Wpisz, co zmienić.' });
    }
    try {
      const res = await apiRequest(
        `/opportunities/${params.id}/edit-offer/`,
        { method: 'POST', body: { instruction } },
        { cookies, org: locals.org }
      );
      return { success: true, action: 'editOffer', offerUrl: res?.url };
    } catch (err) {
      console.error('Edit offer error:', err);
      return fail(400, {
        action: 'editOffer',
        error: /** @type {any} */ (err)?.message || 'Failed to edit offer'
      });
    }
  }
};
