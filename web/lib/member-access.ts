import 'server-only';
import { cookies } from 'next/headers';
import { createClient } from '@supabase/supabase-js';
import { apiBase, gatewayHeaders, supabase } from './server';

export type SocialProvider = 'google' | 'facebook';
export const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const validId = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
export const validCode = /^\d{6,10}$/;

export class MemberAccessError extends Error {
  constructor(message: string, public status = 503) { super(message); }
}

export async function memberAccess<T>(action: string, body: object, accessToken?: string): Promise<T> {
  const response = await fetch(apiBase() + '/api/internal/member-access/' + action, {
    method: 'POST', cache: 'no-store', signal: AbortSignal.timeout(30000),
    headers: {
      'Content-Type': 'application/json',
      'X-API-Secret': process.env.SPONSORMATCH_API_SECRET || '',
      ...(accessToken ? { Authorization: 'Bearer ' + accessToken } : {}),
    },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new MemberAccessError(typeof result.detail === 'string' ? result.detail : 'The account service is unavailable.', response.status);
  return result;
}

export function detachedAuth() {
  if (!process.env.SUPABASE_URL || !process.env.SUPABASE_PUBLISHABLE_KEY) throw new MemberAccessError('Email verification is unavailable.');
  return createClient(process.env.SUPABASE_URL, process.env.SUPABASE_PUBLISHABLE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false, detectSessionInUrl: false },
  }).auth;
}

export async function currentAccessToken() {
  const client = await supabase();
  return client ? (await client.auth.getSession()).data.session?.access_token : undefined;
}

export async function installMemberSession(session: { access_token: string; refresh_token: string }, uid: string, shortlist?: string | null) {
  const client = await supabase();
  if (!client) throw new MemberAccessError('Sign-in is temporarily unavailable.');
  const { data, error } = await client.auth.setSession(session);
  if (error || data.user?.id !== uid) {
    if (data.session) await client.auth.signOut({ scope: 'local' });
    throw new MemberAccessError('We could not complete sign-in. Try an email code.');
  }
  try {
    const headers = await gatewayHeaders();
    if (shortlist && validId.test(shortlist)) {
      const confirmation = await fetch(apiBase() + '/api/matches/' + shortlist + '/confirmation', {
        method: 'POST', headers, cache: 'no-store', signal: AbortSignal.timeout(10000),
      });
      if (confirmation.ok) {
        const { email } = await confirmation.json();
        if (typeof email === 'string' && email.toLowerCase() !== data.user.email?.toLowerCase()) {
          // Keep the browser's shortlist ownership when the wrong provider
          // account was selected so the member can retry with the right email.
          await client.auth.signOut({ scope: 'local' });
          return '/results/' + shortlist + '?signin=shortlist_email';
        }
      }
    }
    const associated = await fetch(apiBase() + '/api/account/associate', {
      method: 'POST', headers, cache: 'no-store', signal: AbortSignal.timeout(15000),
    });
    if (associated.ok) return shortlist && validId.test(shortlist) ? '/results/' + shortlist : '/account';
    if (associated.status === 403) {
      await clearMemberSession();
      return '/account?signin=closed';
    }
  } catch { /* Keep the valid session so the member can retry association. */ }
  return '/account?signin=association_failed';
}

export async function clearMemberSession() {
  const jar = await cookies();
  // The backend has already revoked refresh tokens when closing the account.
  // Remove all cookie chunks even if the now-revoked session cannot sign out.
  const url = process.env.SUPABASE_URL;
  if (url) {
    const prefix = 'sb-' + new URL(url).hostname.split('.')[0] + '-auth-token';
    for (const cookie of jar.getAll()) {
      if (cookie.name === prefix || cookie.name.startsWith(prefix + '.') || cookie.name === prefix + '-code-verifier') jar.delete(cookie.name);
    }
  }
  for (const name of ['sm_owner', 'sr_social_google', 'sr_social_facebook', 'sr_social_verify', 'sr_settings_otp']) jar.delete(name);
}

export function socialConfig() {
  const active = !!(process.env.SPONSORMATCH_API_SECRET && process.env.SUPABASE_URL && process.env.SUPABASE_PUBLISHABLE_KEY && process.env.SUPABASE_SECRET_KEY);
  return {
    googleClientId: active && process.env.SOCIAL_GOOGLE_ENABLED === 'true' ? process.env.GOOGLE_WEB_CLIENT_ID || '' : '',
    facebook: active && process.env.SOCIAL_FACEBOOK_ENABLED === 'true' && !!(process.env.META_APP_ID && process.env.META_APP_SECRET && process.env.APP_ORIGIN?.startsWith('https://')),
  };
}

export function closureAvailable() {
  return !!(process.env.SUPABASE_SECRET_KEY && process.env.RESEND_API_KEY && process.env.SPONSORREACH_DELETION_FROM &&
    (process.env.SPONSORREACH_CLOSURE_JOB_SECRET || '').length >= 32);
}
