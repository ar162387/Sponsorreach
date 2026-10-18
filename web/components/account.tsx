'use client';
import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { ArrowUpRight, ArrowRight, Mail, Compass, SlidersHorizontal, ListChecks, MapPin, GraduationCap, LockKeyhole } from 'lucide-react';
import { api, type Profile } from '@/lib/types';
type Session = { id: string; status: string; created_at: string; access: string; roles?: string[] };
type Overview = { first_name: string | null; profile: Profile | null; sessions: Session[] };
export default function Account({ authenticated = false, dashboard = false }: { authenticated?: boolean; dashboard?: boolean }) {
  const [sessions, setSessions] = useState<Session[]>([]), [overview, setOverview] = useState<Overview | null>(null);
  const [email, setEmail] = useState(''), [notice, setNotice] = useState(''), [error, setError] = useState(''), [loading, setLoading] = useState(true), [sending, setSending] = useState(false), [signedIn, setSignedIn] = useState(authenticated), [signinAvailable, setSigninAvailable] = useState(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError('');
    try {
      const response = await fetch('/api/account/overview', { cache: 'no-store', signal });
      if (response.status === 401) {
        if (authenticated) { window.location.replace('/account?signin=expired'); return; }
        setSignedIn(false); setOverview(null);
        const [history, status] = await Promise.all([api<{ sessions: Session[] }>('matches/history', { signal }), api<{ email_signin_available: boolean }>('catalogue/status', { signal })]);
        setSessions(history.sessions); setSigninAvailable(status.email_signin_available);
      } else {
        if (!response.ok) throw new Error('Your dashboard is temporarily unavailable. Your saved shortlists are safe.');
        const value: Overview = await response.json(); setOverview(value); setSessions(value.sessions); setSignedIn(true);
      }
    } catch (e) { if (!signal?.aborted) setError((e as Error).message); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, [authenticated]);
  useEffect(() => { const controller = new AbortController(); load(controller.signal); return () => controller.abort(); }, [load]);
  useEffect(() => {
    const status = new URLSearchParams(window.location.search).get('signin');
    if (status === 'expired') setNotice('Your sign-in expired. Request a new email link to return to your account.');
    if (status === 'failed' || status === 'association_failed') setNotice('That sign-in link could not finish connecting your account. Please request a fresh link in this browser.');
  }, []);
  async function signIn(e: React.FormEvent) {
    e.preventDefault(); setSending(true); setNotice('');
    try { await api('auth/magic-link', { method: 'POST', body: JSON.stringify({ email }) }); setNotice('Check your inbox and spam or junk folder for the sign-in link. Open it in this browser.'); }
    catch (e) { setNotice((e as Error).message); } finally { setSending(false); }
  }
  const profile = overview?.profile, latest = sessions[0];
  const title = signedIn && dashboard ? `Welcome back${overview?.first_name ? ', ' + overview.first_name : ''}.` : 'My sponsor shortlists.';
  return <section className={`account-shell shell ${signedIn ? 'personal-dashboard' : ''}`}>
    <div className="dashboard-heading"><div><p className="eyebrow">{signedIn ? 'YOUR SPONSORREACH WORKSPACE' : 'PICK UP YOUR SPONSOR SEARCH'}</p><h1>{title}</h1><p className="muted">{signedIn ? 'Your interests. Your saved employers. Your next move.' : 'Sign in to return to your personal sponsor shortlists.'}</p></div>{signedIn && <Link className="button secondary" href="/match"><SlidersHorizontal size={17}/>Refine my profile</Link>}</div>
    {notice && <p className="notice" role="status">{notice}</p>}
    {loading ? <div className="dashboard-loading" role="status">Opening your workspace…</div> : error ? <div className="empty-state" role="alert"><h2>Let’s reconnect your workspace.</h2><p>{error}</p><button className="button secondary" onClick={() => load()}>Try again</button></div> : <>
      {!signedIn && signinAvailable && <form className="signin-panel" onSubmit={signIn}><Mail size={24}/><div><h3>Your search, right where you left it.</h3><p>No password needed. We’ll email you a secure sign-in link.</p></div><label className="sr-only" htmlFor="signin-email">Email address</label><input id="signin-email" required autoComplete="email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com"/><button disabled={sending} className="button small">{sending ? 'Sending…' : 'Send sign-in link'}</button><small className="signin-spam">Check your spam or junk folder too.</small></form>}
      {!signedIn && !signinAvailable && <p className="notice">Email sign-in is unavailable right now. Saved searches in this browser are listed below.</p>}
      {signedIn && <div className="dashboard-grid">
        <article className="dashboard-profile"><span className="dashboard-label"><GraduationCap size={16}/>YOUR SEARCH PROFILE</span>{profile ? <><h2>{profile.role_intents.map(role => role.raw_label).join(' · ')}</h2><p>{profile.background.subject}{profile.background.specialization && ` · ${profile.background.specialization}`}</p><div className="dashboard-skills">{profile.skills.slice(0, 6).map(skill => <span className="tag" key={skill.label}>{skill.label}</span>)}</div><p className="dashboard-location"><MapPin size={15}/>{profile.location.preferred_regions.join(', ') || 'Anywhere in the UK'}{profile.location.relocate ? ' · Open to relocating' : ''}</p><Link className="text-link" href="/match">Update your interests<ArrowRight size={15}/></Link></> : <><h2>Make this space yours.</h2><p>Add your background and career interests to build your first personal shortlist.</p><Link className="button" href="/match">Build my profile<ArrowRight size={16}/></Link></>}</article>
        <article className="dashboard-next"><span className="dashboard-label"><Compass size={16}/>YOUR NEXT STEP</span><h2>{latest ? latest.status === 'ready' ? 'Pick up your latest shortlist.' : latest.status === 'failed' ? 'Give your search another go.' : 'Your shortlist is taking shape.' : 'Find employers connected to your work.'}</h2><p>{latest?.roles?.join(' · ') || 'Use the skills and experience you already have to focus your employer search.'}</p><Link className="button" href={latest && latest.status !== 'failed' ? '/results/' + latest.id : '/match'}>{latest ? latest.status === 'ready' ? 'Open latest shortlist' : latest.status === 'failed' ? 'Refine my search' : 'View search progress' : 'Find my sponsors'}<ArrowUpRight size={17}/></Link><span className="dashboard-preview"><LockKeyhole size={14}/>{latest?.access === 'demo_unlocked' ? 'Latest shortlist: demo access unlocked' : 'Up to 3 complete company previews free'}</span></article>
      </div>}
      <div className="dashboard-section-heading"><h2>{signedIn ? 'Your recent shortlists' : 'Searches in this browser'}</h2><span>{sessions.length} saved</span></div>
      {!sessions.length ? <div className="empty-state"><ListChecks size={32}/><h2>Your next shortlist starts here.</h2><p>Your searches will appear here so you can return to them.</p><Link className="button" href="/match">Find my sponsors<ArrowUpRight size={17}/></Link></div> : <div className="history-list">{sessions.map(s => <Link href={'/results/' + s.id} className="history-row" key={s.id}><span className="history-icon"><Compass size={22}/></span><div><h3>{s.roles?.join(' · ') || 'Sponsor shortlist'}</h3><span>{new Date(s.created_at).toLocaleDateString('en-GB', { dateStyle: 'medium' })} · {s.status === 'ready' ? 'Ready to explore' : s.status === 'failed' ? 'Needs another attempt' : s.status === 'needs_clarification' ? 'More detail needed' : 'Building your shortlist'}</span></div><span className="tag">{s.access === 'preview' ? 'Free preview' : 'Unlocked'}</span><ArrowUpRight size={19}/></Link>)}</div>}
    </>}
  </section>;
}
