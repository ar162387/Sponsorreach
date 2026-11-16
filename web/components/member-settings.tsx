'use client';

import { useLayoutEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, Check, Link2, Mail, ShieldCheck, Trash2 } from 'lucide-react';
import { SocialButtons, VerificationForm, VerifySocial } from './social-signin';
import { api } from '@/lib/types';

const notices: Record<string, string> = {
  connected: 'Google is connected to your account.',
  disconnected: 'Your sign-in method has been disconnected.',
  cancelled: 'Connection cancelled.',
  already_connected: 'This Google account is connected to another SponsorReach account.',
  provider_failed: 'We couldn’t connect Google. Try again.',
  expired: 'Your connection attempt expired. Start again below.',
};

function GoogleMark() {
  return <svg viewBox="0 0 48 48" width="22" height="22" aria-hidden="true">
    <path fill="#4285f4" d="M43.6 24.5c0-1.4-.1-2.8-.4-4.1H24v7.8h11a9.4 9.4 0 0 1-4.1 6.2v5h6.6c3.9-3.6 6.1-8.8 6.1-14.9z"/>
    <path fill="#34a853" d="M24 44c5.5 0 10.1-1.8 13.5-4.9l-6.6-5a12 12 0 0 1-17.8-6.3H6.3V33A20 20 0 0 0 24 44z"/>
    <path fill="#fbbc05" d="M13.1 27.8a12 12 0 0 1 0-7.6V15H6.3a20 20 0 0 0 0 18l6.8-5.2z"/>
    <path fill="#ea4335" d="M24 12c3 0 5.7 1 7.8 3.1l5.9-5.8A19.5 19.5 0 0 0 24 4 20 20 0 0 0 6.3 15l6.8 5.2A12 12 0 0 1 24 12z"/>
  </svg>;
}

function ConfirmChange({ intent, onCancel }: { intent: 'google' | 'close'; onCancel: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const closing = intent === 'close';
  const title = closing ? 'Confirm account deletion' : 'Disconnect Google';
  useLayoutEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => { element?.close(); };
  }, []);

  return <dialog ref={dialog} className="settings-confirm" data-danger={closing} aria-label={title}
    onCancel={event => {
      event.preventDefault();
      if (!event.currentTarget.querySelector('[aria-busy="true"]')) onCancel();
    }}>
    <VerificationForm linking title={title} verifyLabel={closing ? 'Confirm deletion' : 'Disconnect Google'}
      description={closing
        ? 'Confirm with an email code. Your account will be locked, paid renewals will stop, and deletion will be scheduled for 30 days from now.'
        : 'Confirm with an email code. You’ll still be able to sign in with your SponsorReach email.'}
      onSubmit={(action, _email, code) => api('account/settings', { method: 'POST', body: JSON.stringify({ action, code, intent }) })}
      onCancel={onCancel}/>
  </dialog>;
}

export default function MemberSettings({ email, googleConnected, googleClientId, pending, signin, closureAvailable }: {
  email: string;
  googleConnected: boolean;
  googleClientId: string;
  pending?: boolean;
  signin?: string;
  closureAvailable: boolean;
}) {
  const [intent, setIntent] = useState<'google' | 'close'>();
  const [connect, setConnect] = useState(false);
  const notice = signin && Object.hasOwn(notices, signin) ? notices[signin] : undefined;

  return <>
    {notice && <p className="settings-feedback" role="status">{notice}</p>}
    <section className="settings-card" aria-labelledby="signin-methods-heading">
      <header className="settings-card-heading">
        <span className="settings-icon"><ShieldCheck size={21} aria-hidden="true"/></span>
        <div>
          <h2 id="signin-methods-heading">Sign-in methods</h2>
          <p>Choose how you access your SponsorReach account.</p>
        </div>
      </header>
      <ul className="settings-methods">
        <li className="settings-method">
          <span className="settings-icon settings-provider"><Mail size={21} aria-hidden="true"/></span>
          <div className="settings-method-copy"><strong>Email</strong><span>{email}</span></div>
          <span className="settings-status settings-active"><Check size={13} aria-hidden="true"/>Verified</span>
        </li>
        <li className="settings-method">
          <span className="settings-icon settings-provider"><GoogleMark/></span>
          <div className="settings-method-copy"><strong>Google</strong><span>Use your Google account to sign in.</span></div>
          <span className={googleConnected ? 'settings-status settings-active' : 'settings-status'}>
            {googleConnected && <Check size={13} aria-hidden="true"/>}
            {googleConnected ? 'Connected' : 'Not connected'}
          </span>
          {googleConnected
            ? <button type="button" className="button secondary small" onClick={() => setIntent('google')}>Disconnect</button>
            : googleClientId && !pending
              ? <button type="button" className="button secondary small" aria-expanded={connect} aria-controls="connect-google"
                onClick={() => setConnect(value => !value)}>{connect ? 'Cancel' : <><Link2 size={15} aria-hidden="true"/>Connect</>}</button>
              : null}
          {!googleConnected && <div className="settings-google-connect" id="connect-google" hidden={!connect && !pending}>
            {pending ? <VerifySocial provider="google" linking/>
              : connect && <SocialButtons googleClientId={googleClientId} linking/>}
          </div>}
        </li>
      </ul>
    </section>

    <section className="settings-card settings-deletion" aria-labelledby="delete-account-heading">
      <header className="settings-card-heading">
        <span className="settings-icon"><Trash2 size={21} aria-hidden="true"/></span>
        <div><h2 id="delete-account-heading">Delete account</h2><p>Close your account and schedule your data for deletion.</p></div>
      </header>
      <div className="settings-delete-content">
        <p>After you confirm, we’ll lock your account, stop paid renewals and permanently delete your account after 30 days. To request restoration during that period, email <a href="mailto:privacy@sponsorreach.uk">privacy@sponsorreach.uk</a>.</p>
        <div className="settings-delete-actions">
          <Link className="settings-policy-link" href="/data-deletion">Data deletion policy <ArrowUpRight size={15} aria-hidden="true"/></Link>
          {closureAvailable
            ? <button type="button" className="button small settings-danger-button" onClick={() => setIntent('close')}>Delete account</button>
            : <a className="button small settings-danger-button" href="mailto:privacy@sponsorreach.uk?subject=SponsorReach%20account%20deletion">Email a deletion request</a>}
        </div>
      </div>
    </section>

    {intent && <ConfirmChange intent={intent} onCancel={() => setIntent(undefined)}/>}
  </>;
}
