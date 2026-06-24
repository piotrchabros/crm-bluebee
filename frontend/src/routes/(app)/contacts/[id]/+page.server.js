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
      tasks: response.tasks || []
    };
  } catch (err) {
    if (/** @type {any} */ (err)?.status) throw err;
    console.error('Failed to load contact detail:', err);
    throw error(500, 'Failed to load contact');
  }
}

/** @type {import('./$types').Actions} */
export const actions = {
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
