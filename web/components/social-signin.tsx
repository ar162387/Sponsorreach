'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import Script from 'next/script';
import { api } from '@/lib/types';

type GoogleIdentity = {
  accounts: { id: {
    initialize(options: { client_id: string; nonce: string; callback: (response: { credential: string }) => void; use_fedcm_for_button: boolean }): void;
    renderButton(element: HTMLElement, options: { theme: string; size: string; text: string; width: number }): void;
  } };
};
type Provider = 'google' | 'facebook';
export type SocialConfig = { googleClientId: string; facebook: boolean };

export function SocialButtons({ googleClientId, facebook, shortlist, linking = false }: SocialConfig & {
  shortlist?: string; linking?: boolean;
}) {
  const googleContainer = useRef<HTMLDivElement>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!googleClientId || !scriptReady || !googleContainer.current) return;
    const target = googleContainer.current;
    const controller = new AbortController();
    async function renderGoogle() {
      const google = (window as Window & { google?: GoogleIdentity }).google;
      if (!google) return;
      const result = await api<{ nonce: string }>('auth/social', {
        method: 'POST', body: JSON.stringify({ action: 'start', provider: 'google', shortlist, linking }),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      google.accounts.id.initialize({
        client_id: googleClientId, nonce: result.nonce, use_fedcm_for_button: true,
        callback: async ({ credential }) => {
          if (controller.signal.aborted) return;
          setNotice('');
          try {
            const result = await api<{ next: string }>('auth/social', {
              method: 'POST', body: JSON.stringify({ action: 'google', credential }),
            });
            window.location.assign(result.next);
          } catch (error) {
            setNotice((error as Error).message + ' Refresh this page to try Google again.');
          }
        },
      });
      target.replaceChildren();
      google.accounts.id.renderButton(target, { theme: 'outline', size: 'large', text: 'continue_with', width: Math.min(300, target.clientWidth || 300) });
    }
    void renderGoogle().catch(error => {
      if (!controller.signal.aborted) setNotice((error as Error).message);
    });
    return () => { controller.abort(); target.replaceChildren(); };
  }, [googleClientId, linking, scriptReady, shortlist]);

  async function continueFacebook() {
    setBusy(true);
    setNotice('');
    try {
      const result = await api<{ url: string }>('auth/social', {
        method: 'POST', body: JSON.stringify({ action: 'start', provider: 'facebook', shortlist, linking }),
      });
      window.location.assign(result.url);
    } catch (error) {
      setNotice((error as Error).message);
      setBusy(false);
    }
  }

  if (!googleClientId && !facebook) return null;
  return <div className="social-signin" aria-label={linking ? 'Connect a sign-in method' : 'Other sign-in methods'}>
    {googleClientId && <>
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive"
        onReady={() => setScriptReady(true)} onError={() => setNotice('Google is unavailable. You can still use an email code.')}/>
      <div className="google-signin" ref={googleContainer}/>
    </>}
    {facebook && <button type="button" className="facebook-signin" disabled={busy} onClick={continueFacebook}>
      <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
        <path d="M24 12a12 12 0 1 0-13.875 11.85v-8.39H7.078V12h3.047V9.356c0-3.007 1.792-4.67 4.533-4.67 1.312 0 2.686.235 2.686.235v2.952h-1.513c-1.49 0-1.956.925-1.956 1.874V12h3.328l-.532 3.46h-2.796v8.39A12 12 0 0 0 24 12Z"/>
      </svg>
      {busy ? 'Opening Facebook…' : 'Continue with Facebook'}
    </button>}
    {notice && <p className="notice" role="status">{notice}</p>}
  </div>;
}

export function VerificationForm({ title, description, email: initialEmail, linking, onSubmit, onCancel }: {
  title: string; description: string; email?: string | null; linking?: boolean;
  onSubmit: (action: 'send' | 'verify', email: string, code: string) => Promise<{ next?: string }>;
  onCancel: () => void;
}) {
  const [email, setEmail] = useState(initialEmail || '');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [cooldown, setCooldown] = useState(0);
  useEffect(() => {
    if (!cooldown) return;
    const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);
  async function submit(action: 'send' | 'verify') {
    setBusy(true);
    setNotice('');
    try {
      const result = await onSubmit(action, email, code);
      if (result.next) { window.location.assign(result.next); return; }
      setSent(true);
      setCode('');
      setCooldown(60);
      setNotice('Code sent. Check your inbox and spam or junk folder.');
    } catch (error) { setNotice((error as Error).message); }
    finally { setBusy(false); }
  }
  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submit(sent ? 'verify' : 'send');
  }
  return <form className="signin-panel" onSubmit={handleSubmit}>
    <div><h3>{title}</h3><p>{description}</p></div>
    {!linking && <label>Email address<input type="email" autoComplete="email" required maxLength={254}
      value={email} disabled={sent || busy} onChange={event => setEmail(event.target.value)}/></label>}
    {sent && <label>Email code<input required autoFocus inputMode="numeric" autoComplete="one-time-code"
      pattern="[0-9]{6,10}" maxLength={10} value={code} onChange={event => setCode(event.target.value.replace(/\D/g, ''))}/></label>}
    <button className="button small" disabled={busy}>{busy ? 'Please wait…' : sent ? 'Verify and continue' : 'Send email code'}</button>
    {sent && <button className="text-button" type="button" disabled={busy || !!cooldown}
      onClick={() => void submit('send')}>{cooldown ? `Resend code in ${cooldown}s` : 'Resend code'}</button>}
    {sent && !linking && <button className="text-button" type="button" disabled={busy} onClick={() => {
      setSent(false); setCode(''); setNotice('');
    }}>Use a different email</button>}
    <button className="text-button" type="button" onClick={onCancel} disabled={busy}>Cancel</button>
    {notice && <p className="notice" role="status">{notice}</p>}
  </form>;
}

export function VerifySocial({ provider, email, linking }: { provider: Provider; email?: string | null; linking: boolean }) {
  return <VerificationForm title={linking ? 'Confirm this connection' : 'Confirm your email'}
    description={linking
      ? `We’ll send a code to your SponsorReach email before connecting ${provider === 'google' ? 'Google' : 'Facebook'}.`
      : 'Enter the email you use for SponsorReach so we can keep your research in one account.'}
    email={email} linking={linking}
    onSubmit={(action, address, code) => api('auth/social', { method: 'POST', body: JSON.stringify({ action, email: address, code, linking }) })}
    onCancel={async () => {
      try { await api('auth/social', { method: 'POST', body: JSON.stringify({ action: 'cancel' }) }); }
      finally { window.location.assign(linking ? '/account/settings' : '/account'); }
    }}/>;
}
