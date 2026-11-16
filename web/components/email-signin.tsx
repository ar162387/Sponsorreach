'use client';
import { useEffect, useId, useState, type ReactNode } from 'react';
import { Mail } from 'lucide-react';
import { api } from '@/lib/types';

export default function EmailSignin({ sessionId, initialSent = false, inDialog, onComplete, alternatives }: {
  sessionId?: string;
  initialSent?: boolean;
  inDialog?: boolean;
  onComplete?: (next: string) => void;
  alternatives?: ReactNode;
}) {
  const emailId = useId();
  const codeId = useId();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(initialSent);
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [cooldown, setCooldown] = useState(initialSent ? 60 : 0);
  useEffect(() => {
    if (!cooldown) return;
    const timer = setTimeout(() => setCooldown(value => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);
  async function submit(verify: boolean) {
    setBusy(true); setNotice('');
    try {
      const result = await api<{ next?: string }>('auth/otp', { method: verify ? 'PUT' : 'POST', body: JSON.stringify({ ...(sessionId ? { session_id: sessionId } : { email }), ...(verify ? { token: token.trim() } : {}) }) });
      if (verify && result.next) {
        if (onComplete) onComplete(result.next);
        else window.location.assign(result.next);
        return;
      }
      setSent(true); setToken(''); setCooldown(60); setNotice('Code sent. Check your inbox and spam or junk folder.');
    } catch (error) { setNotice((error as Error).message); }
    finally { setBusy(false); }
  }
  return <>
    <form className="signin-panel" onSubmit={event => { event.preventDefault(); void submit(sent); }}>
      {inDialog
        ? sent && <p>Enter the code sent to <strong>{email.trim()}</strong>.</p>
        : <><Mail size={24}/><div><h3>{sent ? 'Enter your sign-in code.' : 'No password to remember.'}</h3><p>{sent ? 'Read the code on any device, then enter it here to sign in.' : 'We’ll email you a one-time sign-in code.'}</p></div></>}
      {!sessionId && !(inDialog && sent) && <>
        <label className={inDialog ? undefined : 'sr-only'} htmlFor={emailId}>Email address</label>
        <input id={emailId} autoFocus={inDialog} required autoComplete="email" type="email" maxLength={254} value={email}
          disabled={sent || busy} onChange={event => setEmail(event.target.value)} placeholder="you@example.com"/>
      </>}
      {sent && <>
        <label className={inDialog ? undefined : 'sr-only'} htmlFor={codeId}>{inDialog ? 'Verification code' : 'Email sign-in code'}</label>
        <input id={codeId} autoFocus required type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,10}"
          minLength={6} maxLength={10} value={token} onChange={event => setToken(event.target.value.replace(/\D/g, ''))} placeholder="Code from email"/>
      </>}
      <button disabled={busy} className="button small">{busy ? 'Please wait…' : sent ? 'Verify and sign in' : 'Send sign-in code'}</button>
      {notice && <p className="notice" role="status">{notice}</p>}
      {sent && <>
        <button type="button" className="text-button" disabled={busy || cooldown > 0} onClick={() => void submit(false)}>
          {cooldown ? `Resend code in ${cooldown}s` : 'Resend code'}
        </button>
        {!sessionId && <button type="button" className="text-button" disabled={busy} onClick={() => {
          setSent(false); setToken(''); setNotice('');
        }}>Use a different email</button>}
      </>}
      {!inDialog && <small className="signin-spam">Check your spam or junk folder too.</small>}
    </form>
    {!sent && alternatives}
  </>;
}
