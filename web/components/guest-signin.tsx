import EmailSignin from '@/components/email-signin';
import Link from 'next/link';
import { SocialButtons, VerifySocial } from './social-signin';
import { memberAccess, socialConfig, type SocialProvider } from '@/lib/member-access';
import { pendingSocial } from '@/lib/social-signin';

const notices: Record<string, string> = {
  provider_failed: 'Social sign-in could not be completed. Try again or use an email code.',
  already_connected: 'This sign-in method is already connected to another account. Use your existing sign-in method.',
  cancelled: 'Sign-in was cancelled. Try again or use an email code.',
  closed: 'This account is scheduled for deletion.',
  expired: 'Your sign-in expired. Request a new email code to return to your account.',
  failed: 'Your account could not be connected to your saved shortlist. Sign in again from the browser where you started your search.',
  association_failed: 'Your account could not be connected to your saved shortlist. Sign in again from the browser where you started your search.',
};

export default async function GuestSignin({ signin, available }: { signin?: string; available: boolean }) {
  let pending;
  if (signin === 'verify') {
    try {
      const attempt = await memberAccess<{provider: SocialProvider; email?: string; linking: boolean}>('pending', await pendingSocial());
      if (!attempt.linking) pending = attempt;
    } catch { /* Offer the ordinary sign-in choices if the attempt expired. */ }
    if (!pending) signin = 'expired';
  }
  const notice = signin && Object.hasOwn(notices, signin) ? notices[signin] : undefined;
  return <section className="account-shell shell guest-account">
    <p className="eyebrow">YOUR SPONSORREACH WORKSPACE</p>
    <h1>Your next step starts here.</h1>
    <p className="muted">Create your account or sign in. New members receive 5 free research credits after confirming their email.</p>
    {notice && <p className="notice" role="status">{notice}</p>}
    {signin === 'closed' && <p><Link href="/data-deletion">Get help with a deletion request</Link></p>}
    {pending ? <VerifySocial {...pending} linking={false}/> : <>
      {available ? <EmailSignin/> : <p>Email sign-in is temporarily unavailable.</p>}
      <SocialButtons {...socialConfig()}/>
    </>}
  </section>;
}
