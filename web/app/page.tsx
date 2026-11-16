import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import MarketingHome from '@/components/marketing-home';
import { OpenSigninOnArrival } from '@/components/signin-dialog';
import { memberAccess, type SocialProvider } from '@/lib/member-access';
import { verifiedUser } from '@/lib/server';
import { signinDestination } from '@/lib/signin-destination';
import { pendingSocial } from '@/lib/social-signin';

export const metadata: Metadata = { alternates: { canonical: 'https://sponsorreach.uk' } };

const notices: Record<string, string> = {
  provider_failed: 'Social sign-in could not be completed. Try again or use an email code.',
  already_connected: 'This sign-in method is already connected to another account. Use your existing sign-in method.',
  cancelled: 'Sign-in was cancelled. Try again or use an email code.',
  closed: 'This account is scheduled for deletion.',
  expired: 'Your sign-in expired. Request a new email code to return to your account.',
  failed: 'Your account could not be connected to your saved shortlist. Sign in again from the browser where you started your search.',
  association_failed: 'Your account could not be connected to your saved shortlist. Sign in again from the browser where you started your search.',
};

export default async function Home({ searchParams }: {
  searchParams: Promise<{ signin?: string; returnTo?: string }>;
}) {
  const user = await verifiedUser();
  if (user) redirect('/account');
  const params = await searchParams;
  let signin = typeof params.signin === 'string' ? params.signin : undefined;
  let pending;
  if (signin === 'verify') {
    try {
      const attempt = await memberAccess<{ provider: SocialProvider; email?: string; linking: boolean }>('pending', await pendingSocial());
      if (!attempt.linking) pending = { provider: attempt.provider, email: attempt.email };
    } catch { /* The visitor can restart sign-in if their attempt expired. */ }
    if (!pending) signin = 'expired';
  }
  const notice = signin && Object.hasOwn(notices, signin) ? notices[signin] : undefined;
  return <>
    <MarketingHome/>
    {signin && <OpenSigninOnArrival request={{
      destination: signinDestination(params.returnTo), notice, pending, closed: signin === 'closed',
    }}/>}
  </>;
}
