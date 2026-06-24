/**
 * Account Detail Page - Server Load
 *
 * Django endpoint: GET /api/accounts/<id>/
 * Response shape (see backend/accounts/views.py AccountDetailView.get):
 *   { account_obj, attachments, comments, contacts, opportunity_list, cases,
 *     tasks, invoices, emails, users, teams, users_mention,
 *     leads, status, stages, sources, countries, currencies,
 *     case_types, case_priority, case_status, comment_permission }
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
    const response = await apiRequest(`/accounts/${params.id}/`, {}, { cookies, org });

    if (response?.error) {
      throw error(404, response.errors || 'Account not found');
    }

    const account = response.account_obj || response.account || response;

    return {
      account,
      comments: response.comments || [],
      attachments: response.attachments || [],
      contacts: response.contacts || account?.contacts || [],
      opportunities: response.opportunity_list || [],
      cases: response.cases || [],
      tasks: response.tasks || [],
      invoices: response.invoices || [],
      emails: response.emails || [],
      tags: account?.tags || [],
      teams: account?.teams || [],
      assignedTo: account?.assigned_to || [],
      commentPermission: response.comment_permission || false,
      customFieldDefinitions: response.custom_field_definitions || [],
      customFieldValues: account?.custom_fields || {}
    };
  } catch (err) {
    if (/** @type {any} */ (err)?.status) throw err;
    console.error('Failed to load account detail:', err);
    throw error(500, 'Failed to load account');
  }
}

/** @type {import('./$types').Actions} */
export const actions = {
  uploadAttachment: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const file = form.get('file');
    if (!file || typeof file === 'string') return fail(400, { error: 'No file provided' });
    const fd = new FormData();
    fd.append('account_attachment', file);
    try {
      await apiRequest(`/accounts/${params.id}/`, { method: 'POST', body: fd }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Upload accounts attachment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to upload attachment' });
    }
  },
  deleteAttachment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const attachmentId = form.get('attachmentId')?.toString();
    if (!attachmentId) return fail(400, { error: 'Missing attachment id' });
    try {
      await apiRequest(`/accounts/attachment/${attachmentId}/`, { method: 'DELETE' }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Delete accounts attachment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to delete attachment' });
    }
  },
  addComment: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const comment = (form.get('comment')?.toString() || '').trim();
    if (!comment) return fail(400, { error: 'Comment cannot be empty' });
    try {
      await apiRequest(`/accounts/${params.id}/`, { method: 'POST', body: { comment } }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Add accounts comment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to add comment' });
    }
  },
  editComment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const commentId = form.get('commentId')?.toString();
    const comment = (form.get('comment')?.toString() || '').trim();
    if (!commentId || !comment) return fail(400, { error: 'Missing comment text' });
    try {
      await apiRequest(`/accounts/comment/${commentId}/`, { method: 'PATCH', body: { comment } }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Edit accounts comment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to edit comment' });
    }
  },
  deleteComment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const commentId = form.get('commentId')?.toString();
    if (!commentId) return fail(400, { error: 'Missing comment id' });
    try {
      await apiRequest(`/accounts/comment/${commentId}/`, { method: 'DELETE' }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Delete accounts comment error:', err);
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
        `/accounts/${params.id}/`,
        { method: 'PATCH', body: { [field]: value } },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Update accounts field error:', err);
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
        `/accounts/${params.id}/`,
        { method: 'PATCH', body: { custom_fields: parsed } },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Update account custom fields error:', err);
      return fail(400, {
        error: /** @type {any} */ (err)?.message || 'Failed to save custom fields'
      });
    }
  }
};
