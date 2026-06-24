/**
 * Lead Detail Page - Server Load
 *
 * Django endpoint: GET /api/leads/<id>/
 * Response shape: { lead_obj, attachments, comments, users_mention, assigned_data,
 *                   users, users_excluding_team, source, status, teams, countries }
 * (see backend/leads/views/lead_views.py LeadDetailView.get_context_data)
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
    const response = await apiRequest(`/leads/${params.id}/`, {}, { cookies, org });

    if (response?.error) {
      throw error(404, response.errors || 'Lead not found');
    }

    // Django LeadDetailView returns the lead under `lead_obj` (see backend/leads/views/lead_views.py).
    const lead = response.lead_obj || response.lead || response;

    return {
      lead,
      comments: response.comments || [],
      attachments: response.attachments || [],
      tags: response.tags || lead?.tags || [],
      users: response.users || [],
      commentPermission: response.comment_permission || false,
      customFieldDefinitions: response.custom_field_definitions || [],
      customFieldValues: lead?.custom_fields || {}
    };
  } catch (err) {
    if (/** @type {any} */ (err)?.status) throw err;
    console.error('Failed to load lead detail:', err);
    throw error(500, 'Failed to load lead');
  }
}

/** @type {import('./$types').Actions} */
export const actions = {
  addComment: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const comment = (form.get('comment')?.toString() || '').trim();
    if (!comment) return fail(400, { error: 'Comment cannot be empty' });
    try {
      await apiRequest(`/leads/${params.id}/`, { method: 'POST', body: { comment } }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Add leads comment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to add comment' });
    }
  },
  editComment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const commentId = form.get('commentId')?.toString();
    const comment = (form.get('comment')?.toString() || '').trim();
    if (!commentId || !comment) return fail(400, { error: 'Missing comment text' });
    try {
      await apiRequest(`/leads/comment/${commentId}/`, { method: 'PATCH', body: { comment } }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Edit leads comment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to edit comment' });
    }
  },
  deleteComment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const commentId = form.get('commentId')?.toString();
    if (!commentId) return fail(400, { error: 'Missing comment id' });
    try {
      await apiRequest(`/leads/comment/${commentId}/`, { method: 'DELETE' }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Delete leads comment error:', err);
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
        `/leads/${params.id}/`,
        { method: 'PATCH', body: { [field]: value } },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Update leads field error:', err);
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
        `/leads/${params.id}/`,
        { method: 'PATCH', body: { custom_fields: parsed } },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Update lead custom fields error:', err);
      return fail(400, {
        error: /** @type {any} */ (err)?.message || 'Failed to save custom fields'
      });
    }
  }
};
