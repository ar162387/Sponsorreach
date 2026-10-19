'use client';
import Link from '@/components/navigation-link';
import { useEffect, useState, useRef } from 'react';
import { ChevronDown, LogOut, ArrowUpRight } from 'lucide-react';

export default function AccountNav({ signedIn }: { signedIn: boolean }) {
  const menu = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    const outside = (event: PointerEvent) => { if (!menu.current?.contains(event.target as Node)) setMenuOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, []);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  useEffect(() => {
    let checking = false, active = true;
    async function check() {
      if (document.hidden || checking) return;
      checking = true;
      try {
        const response = await fetch('/api/account/identity', { cache: 'no-store', signal: AbortSignal.timeout(8000) });
        if (response.ok) {
          const state = await response.json();
          if (active && typeof state.signed_in === 'boolean' && state.signed_in !== signedIn) window.location.reload();
        }
      } catch { /* A temporary network failure does not sign the user out. */ }
      finally { checking = false; }
    }
    const changed = (event: StorageEvent) => { if (event.key === 'sponsorreach:auth-changed') window.location.reload(); };
    window.addEventListener('focus', check); window.addEventListener('pageshow', check); window.addEventListener('storage', changed);
    return () => { active = false; window.removeEventListener('focus', check); window.removeEventListener('pageshow', check); window.removeEventListener('storage', changed); };
  }, [signedIn]);
  async function signOut() {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/auth/sign-out', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!response.ok) throw new Error('Sign-out failed. Please try again.');
      try { Object.keys(sessionStorage).filter(key => key.startsWith('sponsorreach:onboarding:')).forEach(key => sessionStorage.removeItem(key)); } catch { /* Storage may be unavailable. */ }
      try { localStorage.setItem('sponsorreach:auth-changed', String(Date.now())); } catch { /* Sign-out also works without browser storage. */ }
      window.location.replace('/');
    } catch (e) { setError((e as Error).message); setBusy(false); }
  }
  return <nav aria-label="Main navigation" className="personal-nav">
    {!signedIn && <Link href="/about#how-it-works" className="nav-link marketing-nav">How it works</Link>}
    {signedIn ? <>
      <div ref={menu} className="account-menu" onMouseEnter={() => setMenuOpen(true)} onMouseLeave={() => setMenuOpen(false)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setMenuOpen(false); }}><button type="button" className="account-menu-trigger" aria-expanded={menuOpen} aria-controls="account-menu-panel" onClick={() => setMenuOpen(true)}><span className="status-dot"/>My account<ChevronDown size={14}/></button>{menuOpen && <div id="account-menu-panel" className="account-menu-panel" onClick={() => setMenuOpen(false)}><button disabled={busy} onClick={signOut}><LogOut size={15}/>{busy ? 'Signing out…' : 'Sign out'}</button>{error && <p role="alert" className="error">{error}</p>}</div>}</div>
    </> : <Link href="/account" className="nav-signin">Sign in</Link>}
    <>{!signedIn && <Link className="button small" href="/match">Find my sponsors<ArrowUpRight size={16}/></Link>}</>
  </nav>;
}
