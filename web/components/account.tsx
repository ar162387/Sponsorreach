'use client';
import { useState, useEffect, useCallback, useRef } from 'react';
import Link from '@/components/navigation-link';
import { ArrowUpRight, Mail, Compass, Search, Star, Bookmark, Plus, LayoutList, LoaderCircle, X } from 'lucide-react';
import { api, type Profile, type EmployerCard, type MatchSession } from '@/lib/types';
import Results, { type ShortlistView } from './results';
import { Card } from './employer-card';
import { WorkspaceSkeleton } from './skeletons';

type Session = { starred?: boolean; id: string; status: string; created_at: string; updated_at?: string; access: string; roles?: string[] };
type Overview = { first_name: string | null; profile: Profile | null; sessions: Session[]; bookmarks?: EmployerCard[] };
function sortSessions(rows: Session[]) { return [...rows].sort((a, b) => Number(!!b.starred) - Number(!!a.starred) || Date.parse(b.updated_at || b.created_at) - Date.parse(a.updated_at || a.created_at)); }
function statusLabel(status: string) { return status === 'ready' ? 'Ready' : status === 'failed' ? 'Retry needed' : status === 'needs_clarification' ? 'More detail needed' : 'Matching'; }

export default function Account({ authenticated = false }: { authenticated?: boolean; dashboard?: boolean }) {
  const [sessions, setSessions] = useState<Session[]>([]), [overview, setOverview] = useState<Overview | null>(null);
  const [email, setEmail] = useState(''), [notice, setNotice] = useState(''), [error, setError] = useState(''), [loading, setLoading] = useState(true), [sending, setSending] = useState(false), [signedIn, setSignedIn] = useState(authenticated), [signinAvailable, setSigninAvailable] = useState(false);
  const [activeId, setActiveId] = useState(''), [view, setView] = useState<'shortlists' | 'bookmarks'>('shortlists'), [filter, setFilter] = useState<'all' | 'starred'>('all'), [query, setQuery] = useState('');
  const [pendingStars, setPendingStars] = useState<Set<string>>(new Set());
  const starRequests = useRef(new Set<string>()), cache = useRef(new Map<string, ShortlistView>());
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError('');
    try {
      const response = await fetch('/api/account/overview', { cache: 'no-store', signal });
      if (response.status === 401) {
        cache.current.clear(); setOverview(null); setSessions([]);
        if (authenticated) { window.location.replace('/account?signin=expired'); return; }
        setSignedIn(false);
        const [history, status] = await Promise.all([api<{ sessions: Session[] }>('matches/history', { signal }), api<{ email_signin_available: boolean }>('catalogue/status', { signal })]);
        setSessions(history.sessions); setSigninAvailable(status.email_signin_available);
      } else {
        if (!response.ok) throw new Error('Your workspace is temporarily unavailable. Your saved shortlists are safe.');
        const value: Overview = await response.json(); setOverview(value); setSessions(value.sessions); setSignedIn(true);
        const requested = new URLSearchParams(window.location.search).get('shortlist');
        setActiveId(current => value.sessions.some(row => row.id === (requested || current)) ? requested || current : sortSessions(value.sessions)[0]?.id || '');
        if (!requested && value.sessions.length) { const url = new URL(window.location.href); url.searchParams.set('shortlist', sortSessions(value.sessions)[0].id); window.history.replaceState(null, '', url.pathname + url.search); }
      }
    } catch (e) { if (!signal?.aborted) setError((e as Error).message); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, [authenticated]);
  useEffect(() => { const controller = new AbortController(); load(controller.signal); return () => controller.abort(); }, [load]);
  useEffect(() => {
    const status = new URLSearchParams(window.location.search).get('signin');
    if (status === 'expired') setNotice('Your sign-in expired. Request a new email link to return to your account.');
    if (status === 'failed' || status === 'association_failed') setNotice('That sign-in link could not finish connecting your account. Please request a fresh link in this browser.');
    const back = () => { const id = new URLSearchParams(window.location.search).get('shortlist'); if (id && sessions.some(row => row.id === id)) { setActiveId(id); setView('shortlists'); } };
    window.addEventListener('popstate', back); return () => window.removeEventListener('popstate', back);
  }, [sessions]);
  function select(id: string) {
    setActiveId(id); setView('shortlists');
    const url = new URL(window.location.href); url.searchParams.set('shortlist', id);
    if (url.href !== window.location.href) window.history.pushState(null, '', url.pathname + url.search);
  }
  async function signIn(event: React.FormEvent) {
    event.preventDefault(); setSending(true); setNotice('');
    try { await api('auth/magic-link', { method: 'POST', body: JSON.stringify({ email }) }); setNotice('Check your inbox and spam or junk folder for the sign-in link. Open it in this browser.'); }
    catch (e) { setNotice((e as Error).message); } finally { setSending(false); }
  }
  async function toggleStar(session: Session) {
    if (starRequests.current.has(session.id)) return;
    starRequests.current.add(session.id); setPendingStars(new Set(starRequests.current));
    const previous = !!session.starred; setSessions(rows => rows.map(row => row.id === session.id ? { ...row, starred: !previous } : row));
    try {
      const value = await api<{ starred: boolean }>(`matches/${session.id}/star`, { method: 'POST', body: JSON.stringify({ saved: !previous }) });
      setSessions(rows => rows.map(row => row.id === session.id ? { ...row, starred: value.starred } : row));
      const cached = cache.current.get(session.id); if (cached) cache.current.set(session.id, { ...cached, session: { ...cached.session, starred: value.starred } });
    } catch { setSessions(rows => rows.map(row => row.id === session.id ? { ...row, starred: previous } : row)); setNotice('That star could not be saved. Your previous choice has been restored.'); }
    finally { starRequests.current.delete(session.id); setPendingStars(new Set(starRequests.current)); }
  }
  const sessionChanged = useCallback((value: MatchSession) => {
    setSessions(rows => rows.map(row => row.id === value.session_id ? { ...row, status: value.status, access: value.access, starred: starRequests.current.has(row.id) ? row.starred : value.starred } : row));
  }, []);
  const bookmarkChanged = useCallback((company: EmployerCard, saved: boolean) => {
    setOverview(current => {
      if (!current) return current;
      const rest = (current.bookmarks || []).filter(item => item.employer_id !== company.employer_id);
      return { ...current, bookmarks: saved ? [{ ...company, bookmarked: true, session_id: company.session_id || activeId }, ...rest] : rest };
    });
    for (const [id, cached] of cache.current) cache.current.set(id, { ...cached, cards: cached.cards.map(item => item.employer_id === company.employer_id ? { ...item, bookmarked: saved } : item) });
  }, [activeId]);
  const active = sessions.find(row => row.id === activeId);
  const filtered = sortSessions(sessions).filter(row => (filter === 'all' || row.starred) && (row.roles?.join(' ') || 'Sponsor shortlist').toLowerCase().includes(query.trim().toLowerCase()));
  const bookmarks = overview?.bookmarks || [];

  if (loading) return <WorkspaceSkeleton/>;
  if (error) return <section className="shell saved-results-error" role="alert"><h1>Let’s reconnect your workspace.</h1><p>{error}</p><button className="button secondary" onClick={() => load()}>Try again</button></section>;
  if (!signedIn) return <section className="account-shell shell guest-account"><p className="eyebrow">YOUR SPONSORREACH WORKSPACE</p><h1>Pick up where you left off.</h1><p className="muted">Sign in to open your shortlists and bookmarked companies.</p>{notice && <p className="notice" role="status">{notice}</p>}{signinAvailable ? <form className="signin-panel" onSubmit={signIn}><Mail size={24}/><div><h3>No password to remember.</h3><p>We’ll email you a secure sign-in link.</p></div><label className="sr-only" htmlFor="signin-email">Email address</label><input id="signin-email" required autoComplete="email" type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com"/><button disabled={sending} className="button small">{sending ? 'Sending…' : 'Send sign-in link'}</button><small className="signin-spam">Check your spam or junk folder too.</small></form> : <p>Email sign-in is temporarily unavailable.</p>}{!!sessions.length && <div className="history-list">{sessions.map(row => <Link key={row.id} className="history-row" href={'/results/' + row.id}>Sponsor shortlist · {new Date(row.created_at).toLocaleDateString('en-GB')}<ArrowUpRight size={16}/></Link>)}</div>}</section>;

  return <section className="research-workspace">
    <header className="workspace-heading"><div><span className="workspace-kicker">YOUR WORKSPACE</span><h1>{overview?.first_name ? `${overview.first_name}’s sponsor workspace` : 'Your sponsor workspace'}</h1><p>Research companies. Keep your next move in view.</p></div><div className="workspace-stats"><span><strong>{sessions.length}</strong> shortlists</span><span><strong>{bookmarks.length}</strong> saved companies</span></div></header>
    {notice && <div className="workspace-notice" role="status">{notice}<button className="icon-button" aria-label="Dismiss message" onClick={() => setNotice('')}><X size={14}/></button></div>}
    <div className="workspace-tabs" aria-label="Workspace view"><button aria-pressed={view === 'shortlists'} onClick={() => setView('shortlists')}><LayoutList size={16}/>Shortlists<span>{sessions.length}</span></button><button aria-pressed={view === 'bookmarks'} onClick={() => setView('bookmarks')}><Bookmark size={16}/>Bookmarked companies<span>{bookmarks.length}</span></button></div>
    <div className="workspace-columns">
      <aside className="shortlist-sidebar" aria-label="Saved shortlists"><div className="sidebar-heading"><h2>Your shortlists</h2><span>{sessions.length}</span></div><label className="workspace-search"><Search size={15}/><span className="sr-only">Find a shortlist</span><input type="search" placeholder="Find a shortlist…" value={query} onChange={event => setQuery(event.target.value)}/></label><div className="shortlist-filters"><button aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>All</button><button aria-pressed={filter === 'starred'} onClick={() => setFilter('starred')}><Star size={13}/>Starred</button></div>
      <div className="shortlist-scroll">{filtered.length ? filtered.map(row => <article key={row.id} className={`shortlist-item ${activeId === row.id && view === 'shortlists' ? 'active' : ''}`}><button className={`shortlist-item-star ${row.starred ? 'selected' : ''}`} disabled={pendingStars.has(row.id)} aria-busy={pendingStars.has(row.id)} aria-pressed={!!row.starred} aria-label={row.starred ? 'Unstar shortlist' : 'Star shortlist'} onClick={() => toggleStar(row)}>{pendingStars.has(row.id) ? <LoaderCircle size={15} className="spin"/> : <Star size={16} fill={row.starred ? 'currentColor' : 'none'}/>}</button><button className="shortlist-select" aria-pressed={activeId === row.id && view === 'shortlists'} onClick={() => select(row.id)}><strong>{row.roles?.join(' · ') || 'Sponsor shortlist'}</strong><span><i className={`session-dot ${row.status}`}/>{statusLabel(row.status)} · {new Date(row.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</span><small>{row.access === 'preview' ? 'Free preview' : 'Unlocked shortlist'}</small></button><Link className="shortlist-open" href={'/results/' + row.id} aria-label={`Open full shortlist: ${row.roles?.join(' · ') || 'Sponsor shortlist'}`} title="Open full shortlist page"><ArrowUpRight size={16}/></Link></article>) : <div className="sidebar-empty"><Search size={22}/><p>{query ? 'No shortlists match that search.' : filter === 'starred' ? 'Star a shortlist to pin it here.' : 'Your first shortlist starts with your background and skills.'}</p>{!sessions.length && <Link className="button small" href="/match?new=1">Start a search</Link>}</div>}</div><div className="sidebar-hint"><Compass size={14}/><span>Select to preview · ↗ opens the full page</span></div></aside>
      <div className="workspace-details" id="shortlist-detail" aria-label={view === 'bookmarks' ? 'Bookmarked companies' : 'Selected shortlist'}>
        {view === 'bookmarks' ? <><header className="research-detail-heading"><div><span className="workspace-kicker">YOUR COMPANY LIBRARY</span><h2>Bookmarked companies</h2><p>Contact routes and company research, saved across your shortlists.</p></div><span className="tag">{bookmarks.length} saved</span></header>{bookmarks.length ? <div className="workspace-bookmarks">{bookmarks.map((company, position) => <Card compact dashboard key={company.employer_id} employer={company} id={company.session_id || ''} position={position} onBookmarkChange={saved => bookmarkChanged(company, saved)}/>)}</div> : <div className="workspace-empty"><Bookmark size={30}/><h2>Keep the companies you want to approach.</h2><p>Bookmark a company in any shortlist. Its available contacts will be saved here.</p><button className="button secondary small" onClick={() => setView('shortlists')}>Explore your shortlists</button></div>}</>
        : active ? <Results key={active.id} id={active.id} embedded externalStarred={active.starred} title={active.roles?.join(' · ')} cache={cache.current} onSessionChange={sessionChanged} onBookmarkChange={bookmarkChanged}/>
        : <div className="workspace-empty"><LayoutList size={32}/><h2>Your company research starts here.</h2><p>Create a shortlist around your background, skills and career interests.</p><Link className="button small" href="/match?new=1">Build my first shortlist<ArrowUpRight size={16}/></Link></div>}
      </div>
    </div>
  </section>;
}
