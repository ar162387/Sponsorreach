import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { sameOrigin, supabase } from '@/lib/server';

export async function POST(request: Request) {
  if (!sameOrigin(request)) return NextResponse.json({ error: 'Invalid origin' }, { status: 403 });
  const client = await supabase();
  if (client) {
    const { error } = await client.auth.signOut({ scope: 'local' });
    if (error) return NextResponse.json({ error: 'We couldn’t sign you out. Please try again.' }, { status: 503 });
  }
  (await cookies()).delete('sm_owner');
  return NextResponse.json({ signed_out: true }, { headers: { 'Cache-Control': 'private, no-store' } });
}
