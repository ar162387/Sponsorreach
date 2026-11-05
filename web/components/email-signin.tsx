'use client';
import { useEffect, useState } from 'react';
import { Mail } from 'lucide-react';
import { api } from '@/lib/types';

export default function EmailSignin({ sessionId, initialSent = false }: { sessionId?: string; initialSent?: boolean }) {
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
      if (verify && result.next) { window.location.assign(result.next); return; }
      setSent(true); setToken(''); setCooldown(60); setNotice('Code sent. Check your inbox and spam or junk folder.');
    } catch (error) { setNotice((error as Error).message); }
    finally { setBusy(false); }
  }
  return <form className="signin-panel" onSubmit={event => { event.preventDefault(); void submit(sent); }}>
    <Mail size={24}/><div><h3>{sent ? 'Enter your sign-in code.' : 'No password to remember.'}</h3><p>{sent ? 'Read the code on any device, then enter it here to sign in.' : 'We’ll email you a one-time sign-in code.'}</p></div>
    {!sessionId && <><label className="sr-only" htmlFor="signin-email">Email address</label><input id="signin-email" required autoComplete="email" type="email" maxLength={254} value={email} disabled={sent || busy} onChange={event => setEmail(event.target.value)} placeholder="you@example.com"/></>}
    {sent && <><label className="sr-only" htmlFor="signin-code">Email sign-in code</label><input id="signin-code" autoFocus required type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,10}" minLength={6} maxLength={10} value={token} onChange={event => setToken(event.target.value.replace(/\D/g, ''))} placeholder="Code from email"/></>}
    <button disabled={busy} className="button small">{busy ? (sent ? 'Verifying…' : 'Sending…') : (sent ? 'Verify and sign in' : 'Send sign-in code')}</button>
    {sent && <><button type="button" className="text-button" disabled={busy || cooldown > 0} onClick={() => void submit(false)}>{cooldown ? `Resend code in ${cooldown}s` : 'Resend code'}</button>{!sessionId && <button type="button" className="text-button" disabled={busy} onClick={() => { setSent(false); setToken(''); setNotice(''); }}>Use a different email</button>}</>}
    <small className="signin-spam">Check your spam or junk folder too.</small>{notice && <p className="notice" role="status">{notice}</p>}
  </form>;
}
