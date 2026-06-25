/**
 * Contact Detail Page - Server Load
 *
 * Django endpoint: GET /api/contacts/<id>/
 * Response shape: { contact_obj, address_obj, comments, attachments, assigned_data,
 *                   tasks, users_mention }
 * (see backend/contacts/views.py ContactDetailView.get)
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
    const response = await apiRequest(`/contacts/${params.id}/`, {}, { cookies, org });

    if (response?.error) {
      throw error(404, response.errors || 'Contact not found');
    }

    const contact = response.contact_obj || response.contact || response;

    return {
      contact,
      attachments: response.attachments || contact?.contact_attachment || [],
      comments: response.comments || [],
      commentPermission: response.comment_permission ?? true,
      tasks: response.tasks || [],
      accounts: response.accounts || []
    };
  } catch (err) {
    if (/** @type {any} */ (err)?.status) throw err;
    console.error('Failed to load contact detail:', err);
    throw error(500, 'Failed to load contact');
  }
}

/** @type {import('./$types').Actions} */
export const actions = {
  uploadAttachment: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const file = form.get('file');
    if (!file || typeof file === 'string') return fail(400, { error: 'No file provided' });
    const fd = new FormData();
    fd.append('contact_attachment', file);
    try {
      await apiRequest(`/contacts/${params.id}/`, { method: 'POST', body: fd }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Upload contacts attachment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to upload attachment' });
    }
  },
  deleteAttachment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const attachmentId = form.get('attachmentId')?.toString();
    if (!attachmentId) return fail(400, { error: 'Missing attachment id' });
    try {
      await apiRequest(`/contacts/attachment/${attachmentId}/`, { method: 'DELETE' }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Delete contacts attachment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to delete attachment' });
    }
  },
  addComment: async ({ request, params, locals, cookies }) => {
    const form = await request.formData();
    const comment = (form.get('comment')?.toString() || '').trim();
    if (!comment) return fail(400, { error: 'Comment cannot be empty' });
    try {
      await apiRequest(`/contacts/${params.id}/`, { method: 'POST', body: { comment } }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Add contacts comment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to add comment' });
    }
  },
  editComment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const commentId = form.get('commentId')?.toString();
    const comment = (form.get('comment')?.toString() || '').trim();
    if (!commentId || !comment) return fail(400, { error: 'Missing comment text' });
    try {
      await apiRequest(`/contacts/comment/${commentId}/`, { method: 'PATCH', body: { comment } }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Edit contacts comment error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to edit comment' });
    }
  },
  deleteComment: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const commentId = form.get('commentId')?.toString();
    if (!commentId) return fail(400, { error: 'Missing comment id' });
    try {
      await apiRequest(`/contacts/comment/${commentId}/`, { method: 'DELETE' }, { cookies, org: locals.org });
      return { success: true };
    } catch (err) {
      console.error('Delete contacts comment error:', err);
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
        `/contacts/${params.id}/`,
        { method: 'PATCH', body: { [field]: value } },
        { cookies, org: locals.org }
      );
      return { success: true };
    } catch (err) {
      console.error('Update contacts field error:', err);
      return fail(400, { error: /** @type {any} */ (err)?.message || 'Failed to save field' });
    }
  },
};
