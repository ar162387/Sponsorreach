'use client';
import {NEW_SEARCH_REQUESTED,useWorkspaceRouter} from './workspace-navigation';
import {usePathname,useSearchParams} from 'next/navigation';
import {refreshCredits} from './dashboard-shell';
import { useState, useEffect, useCallback, useRef } from 'react';
import Link from '@/components/navigation-link';
import { ArrowUpRight, Search, Star, Bookmark, Plus, LayoutList, LoaderCircle, X, ArrowLeft } from 'lucide-react';
import { api, matchingContext, type LoadingContext, type Profile, type EmployerCard, type MatchSession } from '@/lib/types';
import Intake from './intake';
import EmailSignin from './email-signin';
import Results, { type ShortlistView } from './results';
import { Card } from './employer-card';
import {DataValue,DataRows} from './data-placeholder';

type Session = { starred?: boolean; id: string; status: string; created_at: string; updated_at?: string; access: string; roles?: string[] };
const isShortlistId = (value: string | null): value is string => !!value && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(value);

type Overview = { sessions: Session[]; bookmarks?: EmployerCard[] };
function sortSessions(rows: Session[]) { return [...rows].sort((a, b) => Number(!!b.starred) - Number(!!a.starred) || Date.parse(b.updated_at || b.created_at) - Date.parse(a.updated_at || a.created_at)); }
function statusLabel(status: string) { return status === 'ready' ? 'Ready' : status === 'failed' ? 'Retry needed' : status === 'needs_clarification' ? 'More detail needed' : 'Matching'; }

export default function Account({ authenticated = false }: { authenticated?: boolean; dashboard?: boolean }) {
  const pathname=usePathname(),router=useWorkspaceRouter(),params=useSearchParams();
  const [sessions, setSessions] = useState<Session[]>([]), [overview, setOverview] = useState<Overview | null>(null);
  const [notice, setNotice] = useState(''), [error, setError] = useState(''), [loading, setLoading] = useState(true), [signedIn, setSignedIn] = useState(authenticated), [signinAvailable, setSigninAvailable] = useState(false);
  const requestedId=params.get('shortlist');
  const [activeId, setActiveId] = useState(isShortlistId(requestedId)?requestedId:''), [view, setView] = useState<'shortlists' | 'bookmarks'>('shortlists'), [filter, setFilter] = useState<'all' | 'starred'>('all'), [query, setQuery] = useState('');
  const [runContext,setRunContext]=useState<LoadingContext>();
  const [searchVersion,setSearchVersion]=useState(0);
  useEffect(()=>{
    const reset=()=>setSearchVersion(version=>version+1);
    window.addEventListener(NEW_SEARCH_REQUESTED,reset);
    return ()=>window.removeEventListener(NEW_SEARCH_REQUESTED,reset);
  },[]);
  const run=params.get('run');
  const runId=pathname==='/account/search'&&isShortlistId(run)?run:null;
  const [mobileDetail, setMobileDetail] = useState(pathname==='/account/search'||pathname==='/account/saved'||!!params.get('shortlist'));
  const [pendingStars, setPendingStars] = useState<Set<string>>(new Set());
  const starRequests = useRef(new Set<string>()), cache = useRef(new Map<string, ShortlistView>());
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError('');
    try {
      const section=pathname==='/account/saved'?'bookmarks':'shortlists';
      const response = await fetch('/api/account/overview'+(authenticated?'?section='+section:''), { cache: 'no-store', signal });
      if (response.status === 401) {
        cache.current.clear(); setOverview(null); setSessions([]);
        if (authenticated) { window.location.replace('/account?signin=expired'); return; }
        setSignedIn(false);
        const [history, status] = await Promise.all([api<{ sessions: Session[] }>('matches/history', { signal }), api<{ email_signin_available: boolean }>('catalogue/status', { signal })]);
        setSessions(history.sessions); setSigninAvailable(status.email_signin_available);
      } else {
        if (!response.ok) throw new Error('Your workspace is temporarily unavailable. Your saved shortlists are safe.');
        const value: Overview = await response.json(); setOverview(current=>({...current,...value,bookmarks:value.bookmarks??current?.bookmarks})); setSignedIn(true);
        if(section==='bookmarks'&&authenticated)return;
        setSessions(value.sessions);
        const params = new URLSearchParams(window.location.search);
        const requested = params.get('shortlist');
        if (requested) setMobileDetail(true);
        setActiveId(current => value.sessions.some(row => row.id === (requested || current)) ? requested || current : sortSessions(value.sessions)[0]?.id || '');
        if (pathname==='/account/shortlists' && !requested && value.sessions.length) { const url = new URL(window.location.href); url.searchParams.set('shortlist', sortSessions(value.sessions)[0].id); window.history.replaceState(null, '', url.pathname + url.search); }
      }
    } catch (e) { if (!signal?.aborted) setError((e as Error).message); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, [authenticated, pathname]);
  useEffect(() => {
    if(authenticated&&!['/account/shortlists','/account/saved'].includes(pathname))return;
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load,authenticated,pathname]);
  useEffect(() => {
    const status = new URLSearchParams(window.location.search).get('signin');
    if (status === 'expired') setNotice('Your sign-in expired. Request a new email code to return to your account.');
    if (status === 'failed' || status === 'association_failed') setNotice('Your account could not be connected to your saved shortlist. Sign in again from the browser where you started your search.');
    const back = () => { const id = new URLSearchParams(window.location.search).get('shortlist'); if (id && sessions.some(row => row.id === id)) { setActiveId(id); setView('shortlists'); setMobileDetail(true); } };
    window.addEventListener('popstate', back); return () => window.removeEventListener('popstate', back);
  }, [sessions]);
  useEffect(()=>{
    if(pathname==='/account/saved'){setView('bookmarks');setMobileDetail(true);}
    if(pathname==='/account/shortlists'){
      setView('shortlists');
      const id=params.get('shortlist');
      if(isShortlistId(id)){setActiveId(id);setMobileDetail(true);}
      else setMobileDetail(false);
    }
  },[pathname,params]);
  function select(id: string) {
    setActiveId(id); setView('shortlists'); setMobileDetail(true);
    if(pathname!=='/account/shortlists'){router.push('/account/shortlists?shortlist='+id);return;}
    const url = new URL(window.location.href); url.searchParams.set('shortlist', id); url.searchParams.delete('new'); url.searchParams.delete('edit');
    if (url.href !== window.location.href) window.history.pushState(null, '', url.pathname + url.search);
  }
  useEffect(() => { const panel = document.getElementById('shortlist-detail'); if (panel) panel.scrollTop = 0; }, [activeId, view]);
  function newSearch() { router.push('/account/search'); }
  function completed(id: string, profile: Profile) {
    setRunContext(matchingContext(profile));
    router.replace('/account/search?run='+id,{scroll:false});
  }
  function saveDelivered(value: MatchSession) {
    if(value.status==='ready'||value.status==='failed')refreshCredits();
    if(value.status!=='ready'||!(value.total_count||value.unknown_location_count))return;
    const id=value.session_id;
    setSessions(rows=>{
      if(rows.some(row=>row.id===id))return rows;
      const now=new Date().toISOString();
      return [{id,status:value.status,created_at:now,access:value.access,roles:value.loading_context?.roles},...rows];
    });
    select(id);
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
    if(value.status==='ready'||value.status==='failed')refreshCredits();
    setSessions(rows => rows.map(row => row.id === value.session_id ? { ...row, status: value.status, access: value.access, roles:value.loading_context?.roles||row.roles, starred: starRequests.current.has(row.id) ? row.starred : value.starred } : row));
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
  const bookmarksLoading=loading&&!overview?.bookmarks;

  const searching=pathname==='/account/search';
  const savedView=pathname==='/account/saved';
  if (!signedIn) return <section className="account-shell shell guest-account"><p className="eyebrow">YOUR SPONSORREACH WORKSPACE</p><h1>Your next step starts here.</h1><p className="muted">Create your account or sign in. New members receive 5 free research credits after confirming their email.</p>{notice && <p className="notice" role="status">{notice}</p>}{signinAvailable ? <EmailSignin/> : <p>Email sign-in is temporarily unavailable.</p>}{!!sessions.length && <div className="history-list">{sessions.map(row => <Link key={row.id} className="history-row" href={'/results/' + row.id}>Sponsor shortlist · {new Date(row.created_at).toLocaleDateString('en-GB')}<ArrowUpRight size={16}/></Link>)}</div>}</section>;

  return <section className={`research-workspace dashboard-research ${searching?'research-search-only':''} ${savedView?'research-saved-only':''} ${mobileDetail ? 'show-mobile-detail' : 'show-mobile-list'}`}>
    {savedView&&<header className="dashboard-page-heading"><h1>Saved companies</h1></header>}
    {error&&<p className="error" role="alert">{error} <button className="text-button" onClick={()=>load()}>Try again</button></p>}
    {notice && <div className="workspace-notice" role="status">{notice}<button className="icon-button" aria-label="Dismiss message" onClick={() => setNotice('')}><X size={14}/></button></div>}
    <div className="workspace-columns">
      <aside className="shortlist-sidebar" aria-label="Saved shortlists"><div className="sidebar-heading"><h1>Shortlists</h1><button className="button secondary small shortlist-new-search" onClick={newSearch}><Plus size={15}/>New search</button></div><label className="workspace-search"><Search size={15}/><span className="sr-only">Find a shortlist</span><input type="search" placeholder="Find a shortlist…" value={query} onChange={event => setQuery(event.target.value)}/></label><div className="shortlist-filters"><button aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>All</button><button aria-pressed={filter === 'starred'} onClick={() => setFilter('starred')}><Star size={13}/>Starred</button></div>
      <div className="shortlist-scroll">{loading&&!overview?<DataRows label="shortlists"/>:filtered.length ? filtered.map(row => <article key={row.id} className={`shortlist-item ${activeId === row.id && view === 'shortlists' ? 'active' : ''}`}><button className={`shortlist-item-star ${row.starred ? 'selected' : ''}`} disabled={pendingStars.has(row.id)} aria-busy={pendingStars.has(row.id)} aria-pressed={!!row.starred} aria-label={row.starred ? 'Unstar shortlist' : 'Star shortlist'} onClick={() => toggleStar(row)}>{pendingStars.has(row.id) ? <LoaderCircle size={15} className="spin"/> : <Star size={16} fill={row.starred ? 'currentColor' : 'none'}/>}</button><button className="shortlist-select" aria-pressed={activeId === row.id && view === 'shortlists'} onClick={() => select(row.id)}><strong>{row.roles?.join(' · ') || 'Sponsor shortlist'}</strong><span><i className={`session-dot ${row.status}`}/>{statusLabel(row.status)} · {new Date(row.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</span></button></article>) : <div className="sidebar-empty"><Search size={22}/><p>{query ? 'No shortlists match that search.' : filter === 'starred' ? 'Star a shortlist to pin it here.' : 'Your first shortlist starts with your background and skills.'}</p>{!sessions.length && <button className="button small" onClick={newSearch}>Start a search</button>}</div>}</div></aside>
      <div className="workspace-details" id="shortlist-detail" aria-label={view === 'bookmarks' ? 'Bookmarked companies' : 'Selected shortlist'}>
        <button className="mobile-workspace-back text-button" onClick={() => { setMobileDetail(false); }}><ArrowLeft size={16}/>Your shortlists</button>
        {searching ? (runId ? <Results key={runId} id={runId} embedded pendingContext={runContext} newRun onSessionChange={saveDelivered} cache={cache.current} onStartOver={newSearch}/> : <Intake key={searchVersion} embedded newSearch onCancel={()=>router.push('/account/shortlists')} onComplete={completed}/>) : savedView ? <><header className="research-detail-heading"><div><h2>Bookmarks</h2></div><span className="tag"><DataValue loading={bookmarksLoading} label="saved company count">{bookmarks.length}</DataValue> saved</span></header>{bookmarksLoading?<DataRows label="saved companies"/>:bookmarks.length ? <div className="workspace-bookmarks">{bookmarks.map((company, position) => <Card compact dashboard key={company.employer_id} employer={company} id={company.session_id || ''} position={position} onOpenShortlist={select} onBookmarkChange={saved => bookmarkChanged(company, saved)}/>)}</div> : <div className="workspace-empty"><Bookmark size={30}/><h2>Keep the companies you want to approach.</h2><p>Bookmark a company in any shortlist. Its available contacts will be saved here.</p><button className="button secondary small" onClick={() => router.push('/account/shortlists')}>Explore your shortlists</button></div>}</>
        : activeId ? <Results key={activeId} id={activeId} embedded externalStarred={active?.starred} title={active?.roles?.join(' · ')} knownStatus={active?.status} cache={cache.current} onSessionChange={sessionChanged} onBookmarkChange={bookmarkChanged}/>
        : loading&&!overview ? null : <div className="workspace-empty"><LayoutList size={32}/><h2>Your company research starts here.</h2><p>Create a shortlist around your background, skills and career interests.</p><button className="button small" onClick={newSearch}>Build my first shortlist<Plus size={16}/></button></div>}
      </div>
    </div>
  </section>;
}
