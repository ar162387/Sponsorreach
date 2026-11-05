import EmailSignin from '@/components/email-signin';

const notices: Record<string, string> = {
  expired: 'Your sign-in expired. Request a new email code to return to your account.',
  failed: 'Your account could not be connected to your saved shortlist. Sign in again from the browser where you started your search.',
  association_failed: 'Your account could not be connected to your saved shortlist. Sign in again from the browser where you started your search.',
};

export default function GuestSignin({ signin, available }: { signin?: string; available: boolean }) {
  const notice = signin && Object.hasOwn(notices, signin) ? notices[signin] : undefined;
  return <section className="account-shell shell guest-account">
    <p className="eyebrow">YOUR SPONSORREACH WORKSPACE</p>
    <h1>Your next step starts here.</h1>
    <p className="muted">Create your account or sign in. New members receive 10 free research credits after confirming their email.</p>
    {notice && <p className="notice" role="status">{notice}</p>}
    {available ? <EmailSignin/> : <p>Email sign-in is temporarily unavailable.</p>}
  </section>;
}
