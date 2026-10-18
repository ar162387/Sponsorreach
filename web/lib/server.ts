import { cookies } from 'next/headers';
import { createServerClient } from '@supabase/ssr';
import { randomBytes } from 'node:crypto';
import { cache } from 'react';

export async function supabase() {
  if (!process.env.SUPABASE_URL || !process.env.SUPABASE_PUBLISHABLE_KEY) return null;
  const jar = await cookies();
  return createServerClient(process.env.SUPABASE_URL, process.env.SUPABASE_PUBLISHABLE_KEY, {
    cookies: { getAll: () => jar.getAll(), setAll: (values) => {
      // Proxy refreshes page cookies. Route handlers can write them directly.
      try { values.forEach(({ name, value, options }) => jar.set(name, value, options)); } catch { /* Server Component is read-only. */ }
    } }
  });
}
export const verifiedUser = cache(async () => {
  const client = await supabase();
  if (!client) return null;
  const { data: { user }, error } = await client.auth.getUser();
  if (error && error.name !== 'AuthSessionMissingError' && ![400, 401, 403].includes(error.status || 0)) {
    throw new Error('Your sign-in could not be checked. Please try again.');
  }
  return !error && user?.email_confirmed_at ? user : null;
});
export async function sessionToken() {
  const jar = await cookies();
  let token = jar.get('sm_owner')?.value;
  if (!token || !/^[a-f0-9]{64}$/.test(token)) {
    token = randomBytes(32).toString('hex');
    const localPreview = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(process.env.APP_ORIGIN || '');
    jar.set('sm_owner', token, { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production' && !localPreview, path: '/', maxAge: 30 * 86400 });
  }
  return token;
}
export async function gatewayHeaders() {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', 'X-Session-Token': await sessionToken(), 'X-API-Secret': process.env.SPONSORMATCH_API_SECRET || '' };
  const client = await supabase();
  if (client) {
    const { data: { user } } = await client.auth.getUser();
    if (user) {
      const { data: { session } } = await client.auth.getSession();
      if (session) headers.Authorization = 'Bearer ' + session.access_token;
    }
  }
  return headers;
}
export function apiBase() { return process.env.SPONSORMATCH_API_URL || 'http://127.0.0.1:8001'; }
export function sameOrigin(request: Request) {
  const origin = request.headers.get('origin');
  if (!origin) return true;
  if (process.env.APP_ORIGIN) return origin === process.env.APP_ORIGIN;
  try { const source = new URL(origin); return ['http:', 'https:'].includes(source.protocol) && source.host === request.headers.get('host'); } catch { return false; }
}
export function publicOrigin(request: Request) { return process.env.APP_ORIGIN || new URL(request.url).protocol + '//' + (request.headers.get('host') || new URL(request.url).host); }
