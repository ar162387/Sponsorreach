import { NextResponse } from 'next/server';
import { timingSafeEqual } from 'node:crypto';
import { runAccountClosures } from '@/lib/account-closure';

export async function POST(request: Request) {
  const secret = process.env.SPONSORREACH_CLOSURE_JOB_SECRET || '';
  const expected = Buffer.from('Bearer ' + secret);
  const received = Buffer.from(request.headers.get('authorization') || '');
  if (secret.length < 32 || expected.length !== received.length || !timingSafeEqual(expected, received)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  try {
    return NextResponse.json(await runAccountClosures(), { headers: { 'Cache-Control': 'private, no-store' } });
  } catch {
    return NextResponse.json({ error: 'Account closure processing is unavailable' }, { status: 503 });
  }
}
