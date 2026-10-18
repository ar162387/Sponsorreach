import { NextResponse } from 'next/server';
import { supabase, gatewayHeaders, apiBase, publicOrigin } from '@/lib/server';
export const dynamic = 'force-dynamic';
export async function GET(request: Request) {
  const url = new URL(request.url);
  const client = await supabase();
  const code = url.searchParams.get('code');
  if (client && code) {
    const { error } = await client.auth.exchangeCodeForSession(code);
    if (!error) {
      const associated = await fetch(apiBase() + '/api/account/associate', { method: 'POST', headers: await gatewayHeaders(), cache: 'no-store' });
      if (!associated.ok) return NextResponse.redirect(new URL('/account?signin=association_failed', publicOrigin(request)));
      const next = url.searchParams.get('next') || '/account';
      return NextResponse.redirect(new URL(/^\/results\/[a-f0-9-]{36}$/.test(next) ? next : '/account', publicOrigin(request)));
    }
  }
  return NextResponse.redirect(new URL('/account?signin=failed', publicOrigin(request)));
}
