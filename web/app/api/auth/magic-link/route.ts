import { NextResponse } from 'next/server';
import { supabase, sameOrigin, publicOrigin, gatewayHeaders, apiBase } from '@/lib/server';
import { APPLICATIONS_CLOSED_MESSAGE } from '@/lib/applications';
export async function POST(request: Request) {
  if (!sameOrigin(request)) return NextResponse.json({ error: 'Invalid origin' }, { status: 403 });
  const client = await supabase();
  if (!client) return NextResponse.json({ error: 'Email sign-in is unavailable right now. Your shortlist is saved in this browser.' }, { status: 503 });
  try {
    const body = await request.json();
    let email = body.email;
    let next = '/account';
    if (body.session_id) {
      if (typeof body.session_id !== 'string' || !/^[a-f0-9-]{36}$/.test(body.session_id)) return NextResponse.json({error:'Invalid shortlist.'},{status:422});
      const pending = await fetch(apiBase() + '/api/matches/' + body.session_id + '/confirmation', {method:'POST',headers:await gatewayHeaders(),cache:'no-store',signal:AbortSignal.timeout(15000)});
      if (!pending.ok) return NextResponse.json({error:'Your pending shortlist could not be found.'},{status:404});
      email = (await pending.json()).email;
      next = '/results/' + body.session_id;
    }
    if (typeof email !== 'string' || email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return NextResponse.json({ error: 'Enter a valid email.' }, { status: 422 });
    const origin = publicOrigin(request);
    const { error } = await client.auth.signInWithOtp({ email, options: { shouldCreateUser: false, emailRedirectTo: origin + '/auth/callback?next=' + encodeURIComponent(next) } });
    if (error) return NextResponse.json({ error: APPLICATIONS_CLOSED_MESSAGE + ' Existing members can try signing in again later.' }, { status: 429 });
    return NextResponse.json({ sent: true }, { headers: { 'Cache-Control': 'private, no-store' } });
  } catch { return NextResponse.json({ error: 'Unable to send a sign-in link.' }, { status: 400 }); }
}
