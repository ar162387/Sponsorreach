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
  if (error || !user?.email_confirmed_at) return null;
  const { data: { session } } = await client.auth.getSession();
  if (!session || !await memberSessionAllowed(user.id, session.access_token)) return null;
  return user;
});
export async function memberSessionAllowed(userId: string, accessToken: string) {
  // Local OTP-only previews can run without a gateway secret. Hosted social
  // sign-in and deletion require it, and the backend also guards member APIs.
  const secret = process.env.SPONSORMATCH_API_SECRET;
  if (!secret) return process.env.NODE_ENV !== 'production';
  const response = await fetch(apiBase() + '/api/internal/member-access/status', {
    method: 'POST', cache: 'no-store', signal: AbortSignal.timeout(8000),
    headers: { 'Content-Type': 'application/json', 'X-API-Secret': secret, Authorization: 'Bearer ' + accessToken },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) throw new Error('Your sign-in could not be checked. Please try again.');
  return (await response.json()).blocked === false;
}
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

export function isAdministrator(user: {id:string;email?:string|null}) {
 const ids=(process.env.SPONSORREACH_ADMIN_USER_IDS||'').split(',').map(id=>id.trim()).filter(Boolean);
 const email=process.env.SPONSORREACH_ADMIN_EMAIL?.trim().toLowerCase();
 return ids.length===1&&/^[a-f0-9-]{36}$/i.test(ids[0])&&ids[0]===user.id&&!!email&&user.email?.toLowerCase()===email;
}
