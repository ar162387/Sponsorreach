import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { sameOrigin } from '@/lib/server';
import { currentAccessToken, detachedAuth, installMemberSession, memberAccess, MemberAccessError, validCode, validEmail } from '@/lib/member-access';
import { completeGoogle, pendingSocial, startSocial } from '@/lib/social-signin';

function reply(body: object, status = 200) {
  return NextResponse.json(body, { status, headers: { 'Cache-Control': 'private, no-store' } });
}

export async function POST(request: Request) {
  if (!request.headers.get('origin') || !sameOrigin(request)) return reply({ error: 'Invalid origin.' }, 403);
  try {
    const raw = await request.text();
    if (raw.length > 12000) return reply({ error: 'Invalid sign-in request.' }, 400);
    const body = JSON.parse(raw);
    if (body.action === 'start' && (body.provider === 'google' || body.provider === 'facebook')) {
      return reply(await startSocial(body.provider, body.linking === true, typeof body.shortlist === 'string' ? body.shortlist : undefined));
    }
    if (body.action === 'google' && typeof body.credential === 'string') return reply({ next: await completeGoogle(body.credential) });
    if (body.action === 'cancel') {
      (await cookies()).delete('sr_social_verify');
      return reply({ cancelled: true });
    }
    const attempt = await pendingSocial();
    const accessToken = body.linking === true ? await currentAccessToken() : undefined;
    if (body.action === 'send') {
      const email = typeof body.email === 'string' ? body.email.trim().toLowerCase() : '';
      if (body.linking !== true && (email.length > 254 || !validEmail.test(email))) return reply({ error: 'Enter a valid email address.' }, 422);
      const challenge = await memberAccess<{ email: string; linking: boolean }>('challenge', { ...attempt, email }, accessToken);
      const { error } = await detachedAuth().signInWithOtp({ email: challenge.email, options: { shouldCreateUser: !challenge.linking } });
      if (error) return reply({ error: 'Could not send a code. Wait a moment and try again.' }, 429);
      return reply({ sent: true });
    }
    if (body.action === 'verify' && typeof body.code === 'string' && validCode.test(body.code)) {
      const pending = await memberAccess<{ email?: string; linking: boolean }>('pending', attempt, accessToken);
      const email = pending.linking ? pending.email : typeof body.email === 'string' ? body.email.trim().toLowerCase() : '';
      if (!email || email.length > 254 || !validEmail.test(email)) return reply({ error: 'Enter a valid email address.' }, 422);
      const { data, error } = await detachedAuth().verifyOtp({ email, token: body.code, type: 'email' });
      if (error || !data.session) return reply({ error: 'That code is invalid or has expired. Request a new code and try again.' }, 400);
      const result = await memberAccess<{ user_id: string; linking: boolean; shortlist?: string }>('complete',
        { ...attempt, proof: data.session.access_token }, accessToken);
      (await cookies()).delete('sr_social_verify');
      return reply({ next: result.linking ? '/account/settings?signin=connected' : await installMemberSession(data.session, result.user_id, result.shortlist) });
    }
    return reply({ error: 'Enter the code from your email.' }, 422);
  } catch (error) {
    return error instanceof MemberAccessError ? reply({ error: error.message }, error.status)
      : reply({ error: 'Sign-in is temporarily unavailable. Try an email code.' }, 503);
  }
}
