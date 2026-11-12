import { NextResponse } from 'next/server';
import { supabase, sameOrigin, gatewayHeaders, apiBase } from '@/lib/server';

async function handle(request: Request, verify: boolean) {
  const reply = (body: object, status = 200) => NextResponse.json(body, { status, headers: { 'Cache-Control': 'private, no-store' } });
  if (!sameOrigin(request)) return reply({ error: 'Invalid origin' }, 403);
  try {
    const body = await request.json();
    let email = body.email;
    let next = '/account?new=1';
    if (body.session_id) {
      if (typeof body.session_id !== 'string' || !/^[a-f0-9-]{36}$/.test(body.session_id)) return reply({ error: 'Invalid shortlist.' }, 422);
      const pending = await fetch(apiBase() + '/api/matches/' + body.session_id + '/confirmation', { method: 'POST', headers: await gatewayHeaders(), cache: 'no-store', signal: AbortSignal.timeout(15000) });
      if (!pending.ok) return reply({ error: 'Your pending shortlist could not be found.' }, 404);
      email = (await pending.json()).email;
      next = '/results/' + body.session_id;
    }
    if (typeof email !== 'string') return reply({ error: 'Enter a valid email.' }, 422);
    email = email.trim().toLowerCase();
    if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return reply({ error: 'Enter a valid email.' }, 422);
    if (verify && (typeof body.token !== 'string' || !/^\d{6,10}$/.test(body.token))) return reply({ error: 'Enter the code from your email.' }, 422);
    const client = await supabase();
    if (!client) return reply({ error: 'Email sign-in is unavailable right now. Your shortlist is saved in this browser.' }, 503);
    if (!verify) {
      const { error } = await client.auth.signInWithOtp({ email, options: { shouldCreateUser: true } });
      if (error) return reply({ error: 'Unable to send a sign-in code right now. Please wait and try again.' }, 429);
      return reply({ sent: true });
    }
    const { data, error } = await client.auth.verifyOtp({ email, token: body.token, type: 'email' });
    if (error || !data.session) return reply({ error: 'That code is invalid or has expired. Try again or request a new code.' }, 400);
    const associated = await fetch(apiBase() + '/api/account/associate', { method: 'POST', headers: await gatewayHeaders(), cache: 'no-store', signal: AbortSignal.timeout(15000) });
    if (associated.status === 403) {
      await client.auth.signOut({ scope: 'local' });
      return reply({ next: '/account?signin=closed' });
    }
    if (!associated.ok) return reply({ next: '/account?signin=association_failed' });
    return reply({ next });
  } catch { return reply({ error: 'Unable to complete email sign-in. Please try again.' }, 400); }
}

export async function POST(request: Request) { return handle(request, false); }
export async function PUT(request: Request) { return handle(request, true); }
