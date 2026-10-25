import { NextResponse } from 'next/server';
import { apiBase, gatewayHeaders, sameOrigin, verifiedUser } from '@/lib/server';

import { APPLICATIONS_CLOSED_MESSAGE } from '@/lib/applications';

export const dynamic = 'force-dynamic';
const allowed = /^(catalogue\/status|profiles\/(?:normalize|suggestions)|matches(?:\/history|\/[a-f0-9-]{36}(?:\/results|\/demo-unlock|\/refresh|\/star|\/bookmarks\/[a-f0-9-]{36})?)?|feedback|account\/(?:matches|identity|profile|overview|bookmarks\/[a-f0-9-]{36}))$/;
async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = path.join('/');
  if (!allowed.test(target)) return NextResponse.json({ error: 'Not found' }, { status: 404 });
  if (request.method !== 'GET' && !sameOrigin(request)) return NextResponse.json({ error: 'Invalid origin' }, { status: 403 });
  if (request.method !== 'GET' && !request.headers.get('content-type')?.includes('application/json')) return NextResponse.json({ error: 'JSON required' }, { status: 415 });
  if (request.method === 'POST' && target === 'matches' && !await verifiedUser()) {
    return NextResponse.json({ error: APPLICATIONS_CLOSED_MESSAGE }, { status: 403, headers: { 'Cache-Control': 'private, no-store' } });
  }
  try {
    const body = request.method === 'GET' ? undefined : await request.text();
    if (body && body.length > 20000) return NextResponse.json({ error: 'Request too large' }, { status: 413 });
    const query = new URL(request.url).search;
    const response = await fetch(apiBase() + '/api/' + target + query, { method: request.method, headers: await gatewayHeaders(), body, cache: 'no-store', signal: AbortSignal.timeout(20000) });
    return new NextResponse(await response.text(), { status: response.status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'private, no-store' } });
  } catch { return NextResponse.json({ error: 'Your sponsor search is temporarily unavailable. Please try again or open your saved shortlists.' }, { status: 503 }); }
}
export const GET = proxy;
export const POST = proxy;
