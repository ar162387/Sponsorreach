'use client';

import { useState } from 'react';
import Link from 'next/link';
import { SocialButtons, VerificationForm, VerifySocial, type SocialConfig } from './social-signin';
import { api } from '@/lib/types';

type Provider = 'google' | 'facebook';

export default function MemberSettings({ providers, config, pending, signin, closureAvailable }: {
  providers: Provider[]; config: SocialConfig; pending?: { provider: Provider; email?: string };
  signin?: string; closureAvailable: boolean;
}) {
  const [intent, setIntent] = useState<Provider | 'close'>();
  const [connect, setConnect] = useState(false);
  const google = !providers.includes('google') ? config.googleClientId : '';
  const facebook = !providers.includes('facebook') && config.facebook;
  const notices: Record<string, string> = {
    connected: 'Your sign-in method is connected.',
    disconnected: 'Your sign-in method is disconnected.',
    cancelled: 'Connection cancelled.',
    already_connected: 'That sign-in method is already connected to another account.',
    provider_failed: 'We couldn’t connect your sign-in method. Try again.',
    expired: 'Your connection attempt expired. Start again below.',
  };
  return <div className="dashboard-stack">
    <header><h1>Account settings</h1></header>
    {signin && Object.hasOwn(notices, signin) && <p className="notice" role="status">{notices[signin]}</p>}
    <section className="dashboard-card">
      <h2>Connected sign-in methods</h2>
      <p>You can always use a code sent to your SponsorReach email.</p>
      <ul>
        <li>Email code · Active</li>
        {providers.map(provider => <li key={provider}>
          {provider === 'google' ? 'Google' : 'Facebook'} · Connected{' '}
          <button type="button" className="text-button" onClick={() => setIntent(provider)}>Disconnect</button>
        </li>)}
      </ul>
      {pending ? <VerifySocial {...pending} linking/> : (google || facebook) && (
        connect ? <SocialButtons googleClientId={google} facebook={facebook} linking/>
          : <button type="button" className="button secondary small" onClick={() => setConnect(true)}>Connect a sign-in method</button>
      )}
      {intent && intent !== 'close' && <VerificationForm key={intent} linking title="Disconnect sign-in method"
        description="Confirm this change with a code sent to your SponsorReach email."
        onSubmit={(action, _email, code) => api('account/settings', { method: 'POST', body: JSON.stringify({ action, code, intent }) })}
        onCancel={() => setIntent(undefined)}/>}
    </section>
    <section className="dashboard-card">
      <h2>Delete account</h2>
      <p>We’ll lock your account and stop paid renewals as soon as you confirm. Your account is scheduled for permanent deletion after 30 days.</p>
      <p>To request restoration before then, email <a href="mailto:privacy@sponsorreach.uk">privacy@sponsorreach.uk</a>.</p>
      {intent === 'close' ? <VerificationForm linking title="Schedule permanent deletion"
        description="Entering your email code confirms that you want to close your account."
        onSubmit={(action, _email, code) => api('account/settings', { method: 'POST', body: JSON.stringify({ action, code, intent }) })}
        onCancel={() => setIntent(undefined)}/> : closureAvailable
        ? <button type="button" className="button secondary small" onClick={() => setIntent('close')}>Delete account</button>
        : <a className="button secondary small" href="mailto:privacy@sponsorreach.uk?subject=SponsorReach%20account%20deletion">Email a deletion request</a>}
      <p><Link href="/data-deletion">Read the data deletion instructions</Link></p>
    </section>
  </div>;
}
