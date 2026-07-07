/**
 * Public offer page — server load (Feature 4, Task 13.1).
 *
 * Route: /oferta/{slug}-{accessToken}  (outside the authenticated (app) group).
 * Calls the anonymous Django endpoint GET /api/public/offers/<slug>/<token>/.
 * The visitor's User-Agent and the `?preview=1` flag are forwarded so the
 * backend's bot/preview view-tracking heuristics see the real client, not the
 * SvelteKit SSR fetch.
 */

import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';

/** @type {import('./$types').PageServerLoad} */
export async function load({ params, fetch, request, url, setHeaders }) {
  const slugToken = params.slugToken || '';
  const idx = slugToken.lastIndexOf('-');
  if (idx <= 0 || idx >= slugToken.length - 1) {
    throw error(404, 'Nie znaleziono oferty');
  }
  const slug = slugToken.slice(0, idx);
  const token = slugToken.slice(idx + 1);

  const preview = url.searchParams.get('preview') === '1' ? '?preview=1' : '';
  const endpoint =
    `${env.PUBLIC_DJANGO_API_URL}/api/public/offers/` +
    `${encodeURIComponent(slug)}/${encodeURIComponent(token)}/${preview}`;

  let res;
  try {
    res = await fetch(endpoint, {
      headers: { 'user-agent': request.headers.get('user-agent') || '' }
    });
  } catch {
    throw error(502, 'Nie można pobrać oferty');
  }
  if (res.status === 404) throw error(404, 'Nie znaleziono oferty');
  if (!res.ok) throw error(502, 'Błąd pobierania oferty');

  const offer = await res.json();
  // Public, immutable-ish content — allow brief CDN/proxy caching.
  setHeaders({ 'cache-control': 'public, max-age=60' });
  return { offer };
}
