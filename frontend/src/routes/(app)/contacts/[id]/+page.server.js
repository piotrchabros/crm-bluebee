/**
 * Contact Detail Page - Server Load
 *
 * Django endpoint: GET /api/contacts/<id>/
 * Response shape: { contact_obj, address_obj, comments, attachments, assigned_data,
 *                   tasks, users_mention }
 * (see backend/contacts/views.py ContactDetailView.get)
 */

import { error } from '@sveltejs/kit';
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
