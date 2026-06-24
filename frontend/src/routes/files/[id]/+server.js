import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';

/**
 * Authenticated attachment proxy. The browser opens /files/<attachmentId>;
 * this server route reads the httpOnly jwt_access cookie and streams the file
 * from the backend's org-scoped download endpoint. Replaces the public
 * /media/ link so attachments are no longer world-readable.
 * @type {import('./$types').RequestHandler}
 */
export async function GET({ params, cookies }) {
  const token = cookies.get('jwt_access');
  if (!token) throw error(401, 'Not authenticated');

  const base = env.PUBLIC_DJANGO_API_URL || 'http://localhost:8000';
  let res;
  try {
    res = await fetch(`${base}/api/attachments/${params.id}/download/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    throw error(502, 'Could not reach file service');
  }

  if (!res.ok || !res.body) {
    throw error(res.status === 404 ? 404 : res.status === 401 || res.status === 403 ? 403 : 502, 'File not available');
  }

  const headers = new Headers();
  for (const h of ['content-type', 'content-disposition', 'content-length', 'cache-control']) {
    const v = res.headers.get(h);
    if (v) headers.set(h, v);
  }
  if (!headers.has('cache-control')) headers.set('cache-control', 'private, max-age=0');

  return new Response(res.body, { status: 200, headers });
}
