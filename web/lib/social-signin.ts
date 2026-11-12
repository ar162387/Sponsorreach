import 'server-only';
import { createHmac, randomBytes, randomUUID } from 'node:crypto';
import { cookies } from 'next/headers';
import { createRemoteJWKSet, jwtVerify } from 'jose';
import { apiBase, gatewayHeaders } from './server';
import { currentAccessToken, installMemberSession, memberAccess, MemberAccessError, socialConfig, validEmail, validId, type SocialProvider } from './member-access';

const googleKeys = createRemoteJWKSet(new URL('https://www.googleapis.com/oauth2/v3/certs'), { timeoutDuration: 6000 });
const graph = 'https://graph.facebook.com/v27.0';
const continuation = 'sr_social_verify';
const cookieName = (provider: SocialProvider) => 'sr_social_' + provider;

export const socialCookieOptions = { httpOnly: true, sameSite: 'lax' as const, secure: process.env.APP_ORIGIN?.startsWith('https://') || false, path: '/', maxAge: 900 };

function parseAttempt(value: string | undefined) {
  const [id, browser] = (value || '').split('.');
  if (!validId.test(id) || !/^[a-f0-9]{64}$/.test(browser || '')) throw new MemberAccessError('Your sign-in attempt expired. Start again or use an email code.', 410);
  return { id, browser };
}

export async function pendingSocial() {
  const jar = await cookies();
  return parseAttempt(jar.get(continuation)?.value);
}

export async function startSocial(provider: SocialProvider, linking: boolean, shortlist?: string) {
  const config = socialConfig();
  if (provider === 'google' ? !config.googleClientId : !config.facebook) throw new MemberAccessError('This sign-in method is temporarily unavailable.');
  const accessToken = linking ? await currentAccessToken() : undefined;
  if (linking && !accessToken) throw new MemberAccessError('Sign in to change your sign-in methods.', 401);
  if (shortlist) {
    if (linking || !validId.test(shortlist)) throw new MemberAccessError('Invalid shortlist.', 422);
    const response = await fetch(apiBase() + '/api/matches/' + shortlist + '/confirmation', {
      method: 'POST', headers: await gatewayHeaders(), cache: 'no-store', signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new MemberAccessError('Your pending shortlist could not be found.', 404);
  }
  const id = randomUUID();
  const browser = randomBytes(32).toString('hex');
  await memberAccess('attempt', { id, browser, provider, shortlist }, accessToken);
  (await cookies()).set(cookieName(provider), id + '.' + browser, { ...socialCookieOptions, maxAge: 600 });
  if (provider === 'google') return { nonce: id };
  const url = new URL('https://www.facebook.com/v27.0/dialog/oauth');
  url.search = new URLSearchParams({
    client_id: process.env.META_APP_ID!, redirect_uri: facebookRedirect(),
    state: id, response_type: 'code', scope: 'email',
  }).toString();
  return { url: url.toString() };
}

function facebookRedirect() { return new URL('/auth/facebook/callback', process.env.APP_ORIGIN).toString(); }

async function claim(provider: SocialProvider, state?: string) {
  const jar = await cookies();
  const value = jar.get(cookieName(provider))?.value;
  const attempt = parseAttempt(value);
  if (provider === 'facebook' && state !== attempt.id) throw new MemberAccessError('This Facebook sign-in attempt could not be verified.', 400);
  const info = await memberAccess<{ linking: boolean }>('claim', { ...attempt, provider });
  jar.delete(cookieName(provider));
  return { attempt, value: value!, linking: info.linking };
}

function emailClaim(value: unknown) {
  return typeof value === 'string' && value.length <= 254 && validEmail.test(value) ? value.toLowerCase() : undefined;
}

async function finish(flow: Awaited<ReturnType<typeof claim>>, proof: { subject: string; email?: string; authoritative?: boolean }) {
  const result = await memberAccess<{
    verify?: boolean; linking?: boolean; user_id: string; shortlist?: string;
    session?: { access_token: string; refresh_token: string };
  }>('proof', { ...flow.attempt, ...proof });
  if (result.verify) {
    (await cookies()).set(continuation, flow.value, socialCookieOptions);
    return (result.linking ? '/account/settings' : '/account') + '?signin=verify';
  }
  if (!result.session) throw new MemberAccessError('We could not complete sign-in. Try an email code.');
  return installMemberSession(result.session, result.user_id, result.shortlist);
}

export async function completeGoogle(credential: string) {
  const config = socialConfig();
  if (!config.googleClientId || credential.length > 10000) throw new MemberAccessError('Google sign-in is unavailable.');
  const flow = await claim('google');
  let payload;
  try {
    ({ payload } = await jwtVerify(credential, googleKeys, {
      algorithms: ['RS256'], audience: config.googleClientId,
      issuer: ['https://accounts.google.com', 'accounts.google.com'],
      requiredClaims: ['sub', 'iat', 'exp', 'nonce'],
    }));
  } catch {
    throw new MemberAccessError('Google sign-in could not be verified. Try again or use an email code.', 400);
  }
  if (payload.nonce !== flow.attempt.id || !payload.sub || payload.sub.length > 255 ||
      (payload.azp && payload.azp !== config.googleClientId)) {
    throw new MemberAccessError('This Google sign-in attempt could not be verified.', 400);
  }
  const email = emailClaim(payload.email);
  const authoritative = payload.email_verified === true && !!email &&
    (email.endsWith('@gmail.com') || (typeof payload.hd === 'string' && !!payload.hd));
  return finish(flow, { subject: payload.sub, email, authoritative });
}

export async function completeFacebook(state: string, code: string | null) {
  if (!socialConfig().facebook) throw new MemberAccessError('Facebook sign-in is unavailable.');
  const flow = await claim('facebook', state);
  if (!code || code.length > 4096) return (flow.linking ? '/account/settings' : '/account') + '?signin=cancelled';
  try {
    const secret = process.env.META_APP_SECRET!;
    const tokenUrl = new URL(graph + '/oauth/access_token');
    tokenUrl.search = new URLSearchParams({
      client_id: process.env.META_APP_ID!, client_secret: secret,
      redirect_uri: facebookRedirect(), code,
    }).toString();
    const exchange = await fetch(tokenUrl, { cache: 'no-store', signal: AbortSignal.timeout(8000) });
    if (!exchange.ok) throw new MemberAccessError('Facebook sign-in could not be completed. Try again or use an email code.');
    const { access_token: token } = await exchange.json();
    if (typeof token !== 'string' || !token) throw new MemberAccessError('Facebook sign-in could not be completed.');
    const profile = new URL(graph + '/me');
    profile.search = new URLSearchParams({ fields: 'id,email', appsecret_proof: createHmac('sha256', secret).update(token).digest('hex') }).toString();
    const response = await fetch(profile, {
      headers: { Authorization: 'Bearer ' + token }, cache: 'no-store', signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) throw new MemberAccessError('Facebook sign-in could not be completed.');
    const data = await response.json();
    if (typeof data.id !== 'string' || !/^\d{1,64}$/.test(data.id)) throw new MemberAccessError('Facebook sign-in could not be verified.');
    return await finish(flow, { subject: data.id, email: emailClaim(data.email) });
  } catch (error) {
    const notice = error instanceof MemberAccessError && error.status === 409 ? 'already_connected' : 'provider_failed';
    return (flow.linking ? '/account/settings' : '/account') + '?signin=' + notice;
  }
}
