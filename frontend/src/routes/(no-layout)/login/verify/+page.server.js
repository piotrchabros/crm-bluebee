/**
 * Magic Link Verification Page
 *
 * Two-step flow to prevent email client link preview from consuming tokens:
 * 1. GET: Show "Sign In" button (token NOT verified yet)
 * 2. POST: User clicks button → token verified → redirect to /org
 */

import axios from 'axios';
import { redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { env as publicEnv } from '$env/dynamic/public';

/** @type {import('@sveltejs/kit').ServerLoad} */
export async function load({ url }) {
  const token = url.searchParams.get('token');

  if (!token) {
    return { error: 'Missing verification token.', token: null };
  }

  // Don't verify token on page load — email clients prefetch links
  // and would consume the token before the user clicks.
  // Instead, pass the token to the page and let the user click "Sign In".
  return { token, error: null };
}

/** @type {import('@sveltejs/kit').Actions} */
export const actions = {
  default: async ({ request, cookies }) => {
    const formData = await request.formData();
    const token = formData.get('token')?.toString();

    if (!token) {
      return { error: 'Missing verification token.' };
    }

    try {
      const apiUrl = publicEnv.PUBLIC_DJANGO_API_URL;
      const response = await axios.post(
        `${apiUrl}/api/auth/magic-link/verify/`,
        { token },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 10000
        }
      );

      const { access_token, refresh_token } = response.data;

      const secure = env.NODE_ENV === 'production';
      cookies.set('jwt_access', access_token, {
        path: '/',
        httpOnly: true,
        sameSite: 'lax',
        secure,
        maxAge: 60 * 60 * 24
      });
      cookies.set('jwt_refresh', refresh_token, {
        path: '/',
        httpOnly: true,
        sameSite: 'lax',
        secure,
        maxAge: 60 * 60 * 24 * 365
      });
    } catch (error) {
      const errorMessage = error.response?.data?.error || 'Verification failed';
      return { error: errorMessage };
    }

    throw redirect(307, '/org');
  }
};
