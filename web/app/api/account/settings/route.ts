import { NextResponse, after } from 'next/server';
import { cookies } from 'next/headers';
import { isAdministrator, sameOrigin, verifiedUser } from '@/lib/server';
import { clearMemberSession, closureAvailable, detachedAuth, MemberAccessError, memberAccess, validCode } from '@/lib/member-access';
import { socialCookieOptions } from '@/lib/social-signin';
import { processAccountClosure } from '@/lib/account-closure';

const challenge = 'sr_settings_otp';

function reply(body: object, status = 200) {
  return NextResponse.json(body, { status, headers: { 'Cache-Control': 'private, no-store' } });
}

export async function POST(request: Request) {
  if (!request.headers.get('origin') || !sameOrigin(request)) return reply({ error: 'Invalid origin.' }, 403);
  try {
    const user = await verifiedUser();
    if (!user?.email || isAdministrator(user)) return reply({ error: 'Sign in to your member account.' }, 401);
    const raw = await request.text();
    if (raw.length > 1024) return reply({ error: 'Invalid account request.' }, 400);
    const body = JSON.parse(raw);
    const closing = body.intent === 'close';
    if (!closing && body.intent !== 'google' && body.intent !== 'facebook') return reply({ error: 'Invalid account request.' }, 422);
    if (closing && !closureAvailable()) return reply({ error: 'Email privacy@sponsorreach.uk to request account deletion.' }, 503);
    const expected = user.id + '.' + body.intent;
    const jar = await cookies();
    if (body.action === 'send') {
      const { error } = await detachedAuth().signInWithOtp({ email: user.email, options: { shouldCreateUser: false } });
      if (error) return reply({ error: 'Could not send a code. Wait a moment and try again.' }, 429);
      jar.set(challenge, expected, socialCookieOptions);
      return reply({ sent: true });
    }
    if (body.action !== 'verify' || jar.get(challenge)?.value !== expected || typeof body.code !== 'string' || !validCode.test(body.code)) {
      return reply({ error: 'Request a fresh email code for this change.' }, 422);
    }
    const { data, error } = await detachedAuth().verifyOtp({ email: user.email, token: body.code, type: 'email' });
    if (error || data.user?.id !== user.id || !data.session) return reply({ error: 'That code is invalid or has expired.' }, 400);
    jar.delete(challenge);
    if (!closing) {
      await memberAccess('disconnect', { provider: body.intent }, data.session.access_token);
      return reply({ next: '/account/settings?signin=disconnected' });
    }
    const closure = await memberAccess<{ request_id: string; purge_at: string }>('close', {}, data.session.access_token);
    await clearMemberSession();
    after(async () => {
      try { await processAccountClosure({ user_id: user.id, request_id: closure.request_id }); }
      catch { console.warn('Account closure processing will retry on its next scheduled run.'); }
    });
    jar.set('sr_closure_receipt', closure.purge_at, { ...socialCookieOptions, path: '/data-deletion', maxAge: 300 });
    return reply({ next: '/data-deletion' });
  } catch (error) {
    return error instanceof MemberAccessError ? reply({ error: error.message }, error.status)
      : reply({ error: 'We could not update your account. Please try again.' }, 503);
  }
}

