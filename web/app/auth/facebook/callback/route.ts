import { NextResponse } from 'next/server';
import { publicOrigin } from '@/lib/server';
import { MemberAccessError } from '@/lib/member-access';
import { completeFacebook } from '@/lib/social-signin';

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  let next: string;
  try {
    next = await completeFacebook(params.get('state') || '', params.get('code'));
  } catch (error) {
    next = '/account?signin=' + (error instanceof MemberAccessError && error.status === 409 ? 'already_connected' : 'provider_failed');
  }
  return NextResponse.redirect(new URL(next, publicOrigin(request)), { status: 303, headers: {
    'Cache-Control': 'private, no-store', 'Referrer-Policy': 'no-referrer',
  } });
}
