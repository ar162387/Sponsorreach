'use client';
import EmailSignin from './email-signin';
import {refreshCredits} from './dashboard-shell';
import { useState, useEffect, useRef } from 'react';
import Link from '@/components/navigation-link';
import { ArrowUpRight, ArrowRight, MapPin, Mail, Phone, Link2, LockKeyhole, Check, Compass, X, ThumbsUp, Bookmark, BriefcaseBusiness, ShieldCheck, ExternalLink, Globe, ChevronDown, Sparkles, RefreshCw, Star, LoaderCircle } from 'lucide-react';
import { api, type EmployerCard, type MatchSession } from '@/lib/types';
import { Card } from './employer-card';
import { ResultsSkeleton } from './skeletons';
import PersonalizedLoader from '@/components/personalized-loader';

export type ShortlistView = { session: MatchSession; cards: EmployerCard[]; cursor: number | null };
export default function Results({ id, embedded = false, title, cache, externalStarred, onSessionChange, onBookmarkChange, onRefine }: {
  id: string; embedded?: boolean; title?: string; cache?: Map<string, ShortlistView>; externalStarred?: boolean;
  onRefine?: (session: MatchSession) => void;
  onSessionChange?: (session: MatchSession) => void;
  onBookmarkChange?: (employer: EmployerCard, saved: boolean) => void;
}) {
  const cached = cache?.get(id);
  const [session, setSession] = useState<MatchSession | null>(cached?.session || null), [cards, setCards] = useState<EmployerCard[]>(cached?.cards || []), [error, setError] = useState(''), [modal, setModal] = useState(false), [busy, setBusy] = useState(false), [cursor, setCursor] = useState<number | null>(cached?.cursor ?? null);
  const [confirmRefresh,setConfirmRefresh]=useState(false);
  const refreshDialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(confirmRefresh)refreshDialog.current?.showModal();else refreshDialog.current?.close();},[confirmRefresh]);
  const dialog = useRef<HTMLDialogElement>(null);
  const [refreshEpoch, setRefreshEpoch] = useState(0);
  const refreshKey = useRef<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false, timer: ReturnType<typeof setTimeout>, failures = 0, received = false;
    async function poll() {
      try {
        const data = await api<MatchSession>('matches/' + id, { signal: controller.signal });
        if (cancelled) return;
        received = true; failures = 0; setSession(data); onSessionChange?.(data); setError('');
        if (data.verification_required) { cache?.delete(id); setCards([]); timer = setTimeout(poll, 4000); return; }
        if (data.status === 'ready') {
          refreshCredits();
          const next = data.next_cursor !== undefined ? data.next_cursor : (data.access !== 'preview' && (data.total_count || 0) > (data.preview?.length || 0) ? data.preview?.length || null : null);
          setCards(data.preview || []); setCursor(next);
          cache?.set(id, { session: data, cards: data.preview || [], cursor: next });
        } else if (data.status === 'failed') setError('We couldn’t finish your sponsor shortlist. Please try again with a new search.');
        else timer = setTimeout(poll, 800);
      } catch (e) {
        if (!cancelled && [401, 403, 404].includes((e as Error & { status?: number }).status || 0)) { cache?.clear(); setSession(null); setCards([]); }
        if (!cancelled) { failures++; if (received && failures < 3) timer = setTimeout(poll, 2000); else setError((e as Error).message); }
      }
    }
    poll(); return () => { cancelled = true; controller.abort(); clearTimeout(timer); };
  }, [id, refreshEpoch]);
  useEffect(() => { if (modal) dialog.current?.showModal(); else dialog.current?.close(); }, [modal]);
  async function unlock() {
    setBusy(true); setError('');
    try {
      const paid=session?.credit_mode, batch=session?.next_locked_batch??0;
      await api(paid?`matches/${id}/batches/${batch}/unlock`:`matches/${id}/demo-unlock`, {method:'POST',body:'{}'});
      const data=await api<MatchSession>('matches/'+id);
      const page=await api<{results:EmployerCard[];next_cursor:number|null}>(`matches/${id}/results${paid?'?cursor='+batch*20:''}`);
      const combined=paid&&batch>0?[...cards,...page.results.filter(c=>!cards.some(p=>p.employer_id===c.employer_id))]:page.results;
      refreshCredits();setSession(data);setCards(combined);setCursor(page.next_cursor);setModal(false);onSessionChange?.(data);
      cache?.set(id,{session:data,cards:combined,cursor:page.next_cursor});
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function more() {
    setBusy(true);
    try { const page = await api<{ results: EmployerCard[]; next_cursor: number | null }>(`matches/${id}/results?cursor=${cursor}`); setCards(c => { const combined = [...c, ...page.results]; if (session) cache?.set(id, { session, cards: combined, cursor: page.next_cursor }); return combined; }); setCursor(page.next_cursor); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function refresh() {
    if (busy) return;
    if(session?.credit_mode&&!confirmRefresh){setConfirmRefresh(true);return;}
    setBusy(true); setError('');
    refreshKey.current ||= crypto.randomUUID();
    try {
      const result=await api<{session_id:string}>(`matches/${id}/refresh`, { method: 'POST', body: JSON.stringify({ idempotency_key: refreshKey.current,accept_credit_cost:!!session?.credit_mode }) });
      if(result.session_id!==id){window.location.assign('/account?shortlist='+result.session_id);return;}
      setConfirmRefresh(false);refreshKey.current = null; cache?.delete(id); setCards([]); setCursor(null);
      setSession(current => current ? { ...current, status: 'queued', stage: 'Understanding your career interests' } : current);
      setRefreshEpoch(value => value + 1);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function star() {
    if (busy) return;
    const previous = !!(externalStarred ?? session?.starred);
    setSession(current => current ? { ...current, starred: !previous } : current);
    if (session) onSessionChange?.({ ...session, starred: !previous });
    setBusy(true); setError('');
    try {
      const value = await api<{ starred: boolean }>(`matches/${id}/star`, { method: 'POST', body: JSON.stringify({ saved: !previous }) });
      setSession(current => current ? { ...current, starred: value.starred } : current);
      if (session) { const next = { ...session, starred: value.starred }; onSessionChange?.(next); if (cache?.has(id)) cache.set(id, { ...cache.get(id)!, session: next }); }
    } catch (e) {
      setSession(current => current ? { ...current, starred: previous } : current);
      if (session) onSessionChange?.({ ...session, starred: previous });
      setError((e as Error).message);
    } finally { setBusy(false); }
  }
  function bookmarkChanged(employer: EmployerCard, saved: boolean) {
    setCards(values => values.map(item => item.employer_id === employer.employer_id ? { ...item, bookmarked: saved } : item));
    const current = cache?.get(id);
    if (current) cache?.set(id, { ...current, cards: current.cards.map(item => item.employer_id === employer.employer_id ? { ...item, bookmarked: saved } : item) });
    onBookmarkChange?.(employer, saved);
  }

  const starred = externalStarred ?? session?.starred;
  const ready = session?.status === 'ready';
  const nextBatchCost=session?.next_batch_cost??1;
  if (!session) return error ? <div className="saved-results-error" role="alert"><h2>Let’s reconnect your shortlist.</h2><p>{error}</p><button className="button secondary small" onClick={() => { setError(''); setRefreshEpoch(value => value + 1); }}>Try loading again</button></div> : <ResultsSkeleton embedded={embedded}/>;
  if (session?.verification_required) return <section className="loader-page shell"><Mail size={48}/><p className="eyebrow">ONE LAST STEP</p><h1>Confirm your <em>email.</em></h1><p className="muted">Your shortlist is saved. Enter the code we emailed you to open your research.</p><EmailSignin key={id} sessionId={id} initialSent/><Link className="text-button" href="/account">Use another account</Link></section>;
  if (session?.status === 'failed') return <section className="loader-page shell"><Compass size={38}/><h1>Let’s try your shortlist again.</h1><p className="muted">Your profile and saved choices are safe. Failed searches use no credits. Retry the search or refine this shortlist.</p><button className="button" disabled={busy} onClick={refresh}><RefreshCw size={17}/>Retry this shortlist</button><>{onRefine ? <button className="text-button" onClick={() => onRefine(session)}>Refine this shortlist</button> : <Link className="text-link" href={"/match?shortlist=" + id}>Refine this shortlist</Link>}</>{error && <p className="error" role="alert">{error}</p>}</section>;
  if (!ready && !['queued', 'processing'].includes(session.status)) return <div className="saved-results-error"><h2>Your profile needs a little more detail.</h2><>{onRefine ? <button className="text-button" onClick={() => onRefine(session)}>Refine this shortlist</button> : <Link href={'/match?shortlist=' + id}>Refine this shortlist</Link>}</></div>;
  if (!ready) return <PersonalizedLoader stage={session?.stage} context={session?.loading_context} error={error}/>;
  const direct = cards.filter(c => c.group === 'direct'), related = cards.filter(c => c.group === 'related');
  return <section className={embedded ? 'embedded-results' : 'results-shell shell'}>{embedded ? <header className="research-detail-heading"><div><span className="workspace-kicker">SAVED SHORTLIST</span><h2>{title || session.loading_context?.roles.join(' · ') || 'Your sponsor shortlist'}</h2><p>{session.total_count || 0} relevant companies · {session.credit_mode ? 'Saved research' : 'Full shortlist unlocked'}</p>{session.loading_context && <details className="selected-profile-context"><summary>Profile context</summary><p>{session.loading_context.background}{session.loading_context.specialization && ' · ' + session.loading_context.specialization}</p><div>{session.loading_context.skills.map(skill => <span className="tag" key={skill}>{skill}</span>)}</div><p>{session.loading_context.locations.join(', ') || 'Anywhere in the UK'}</p></details>}</div><div className="research-detail-actions"><button className="button secondary small" disabled={!session.profile} onClick={() => onRefine?.(session)}>Refine profile</button></div></header> : <div className="results-heading"><div><p className="eyebrow"><span className="status-dot"/>RELEVANT COMPANIES. YOUR NEXT STEP.</p><h1>Your sponsor <em>shortlist.</em></h1><p className="muted">{session.total_count ? `${session.total_count} relevant sponsor ${session.total_count === 1 ? 'company' : 'companies'} to research and approach.` : 'We don’t yet have enough company evidence to recommend sponsors for this profile.'}</p></div><Link href={"/match?shortlist=" + id} className="button secondary">Refine this shortlist <ArrowUpRight size={17}/></Link></div>}
    {session.repeat_credit_saved && <p className="notice" role="status">No credit used for this search: more than half of these companies were already unlocked on your account.</p>}
    {session.is_demo && <div className="demo-banner"><Compass size={18}/><div><strong>Fictional sample shortlist</strong><span>These sample employers, contacts, and evidence are fictional. They show how your matching experience works.</span></div></div>}
    <div className="results-toolbar">{session.credit_mode&&<Link href="/account/billing">{session.balance??0} credits · Billing</Link>}<span>{'YOUR SAVED SPONSOR SHORTLIST'}</span><div><button className="icon-button shortlist-refresh" disabled={busy} onClick={refresh} aria-label="Refresh companies in this shortlist" title="Run this profile against the latest company data">{busy ? <LoaderCircle size={17} className="spin"/> : <RefreshCw size={17}/>}</button><button className={`icon-button shortlist-star ${starred ? 'selected' : ''}`} disabled={busy} onClick={star} aria-pressed={!!starred} aria-label={starred ? 'Unstar shortlist' : 'Star shortlist'}><Star size={17} fill={starred ? 'currentColor' : 'none'}/></button><span className="tag">{session.direct_count || 0} direct</span>{!!session.related_count && <span className="tag">{session.related_count} related</span>}<span className="tiny muted">{embedded ? 'Company research & contact routes' : 'Relevant companies, with supporting sources'}</span></div></div>
    {!!direct.length && <><div className="section-label"><h2>Companies for your target roles</h2><span>Company work that connects with your background</span></div><div className="cards-grid">{direct.map(c => <Card key={c.employer_id} employer={c} id={id} position={cards.indexOf(c)} compact={embedded} onBookmarkChange={saved => bookmarkChanged(c, saved)}/>)}</div></>}
    {!!related.length && <><div className="section-label"><h2>Companies for related roles</h2><span>Alternative roles you chose to include</span></div><div className="cards-grid">{related.map(c => <Card key={c.employer_id} employer={c} id={id} position={cards.indexOf(c)} compact={embedded} onBookmarkChange={saved => bookmarkChanged(c, saved)}/>)}</div></>}
    {session.credit_mode&&session.total_count===0&&session.search_credit_charged===false&&<p className="notice" role="status">No credit was used for this empty search.</p>}
    {!cards.length && <div className="empty-state"><Compass size={38}/><h2>Let’s give your search more direction.</h2><p>There isn’t enough supported company information for this search yet. Try a more specific role, add your skills or responsibilities, or include related roles. This is about the information available, not your potential.</p><>{onRefine ? <button className="button" disabled={!session.profile} onClick={() => onRefine(session)}>Refine this shortlist<ArrowRight size={17}/></button> : <Link href={"/match?shortlist=" + id} className="button">Refine this shortlist<ArrowRight size={17}/></Link>}</></div>}
    {!!session.locked_count && <div className="unlock-section"><div className="locked-grid" aria-hidden="true">{Array.from({ length: Math.min(3, session.locked_count) }).map((_, i) => <div className="locked-card" key={i}><div className="blur-content"><div className="fake-avatar"/><h3>A relevant sponsor company</h3><p>Reasons this company may fit</p><div className="fake-line"/><div className="fake-line short"/><span>Available outreach channels</span></div></div>)}</div><div className="unlock-callout"><span className="unlock-icon"><LockKeyhole size={22}/></span><h2>More relevant companies to reach.</h2><p>Unlock {session.locked_count} more sponsor {session.locked_count === 1 ? 'company' : 'companies'} from this saved shortlist, with available contacts and reasons each may fit.</p><button className="button" onClick={() => setModal(true)}>{session.credit_mode?(nextBatchCost===0?'Show more · Free':'Show more · 1 credit'):'Unlock my full sponsor shortlist'} <ArrowRight size={18}/></button><small>{session.credit_mode?'Up to 20 companies per newly opened batch. Reopening is free.':'Currently free · no payment details required'}</small></div></div>}
    {cursor !== null && <div className="load-more"><button className="button secondary" disabled={busy} onClick={more}>{busy ? 'Loading…' : session.credit_mode?'Show saved results · free':'Show more sponsor companies'}<ArrowRight size={17}/></button></div>}
    {!session.credit_mode&&session.access === 'demo_unlocked' && <div className="unlocked-notice"><Check size={17}/>Your full saved shortlist is unlocked. No payment was taken.</div>}
    {error && <p className="error" role="alert">{error}</p>}<p className="qualification">Discover employers and use their official channels to explore opportunities.</p>
    <dialog ref={refreshDialog} onCancel={()=>setConfirmRefresh(false)} aria-label="Run a new search" className="unlock-dialog"><p>This creates a separate shortlist and reserves 1 credit. Empty results and batches with more than half the companies already unlocked on your account are free. Your saved shortlist stays accessible.</p><button className="button small" disabled={busy||(session.balance??0)<1} onClick={refresh}>Run new search · 1 credit</button><button className="text-button" onClick={()=>setConfirmRefresh(false)}>Keep this shortlist</button><Link href="/account/billing">Manage credits</Link></dialog>
    <dialog className="unlock-dialog" ref={dialog} onCancel={() => setModal(false)} aria-labelledby="unlock-title"><button className="dialog-close icon-button" aria-label="Close unlock window" onClick={() => setModal(false)}><X size={20}/></button>{session.credit_mode?<><span className="unlock-icon"><LockKeyhole size={24}/></span><p className="eyebrow">YOUR NEXT RESULTS BATCH</p><h2 id="unlock-title">Open up to 20 companies.</h2><p>{nextBatchCost===0?'This batch is free because more than half its companies are already unlocked on your account.':'This costs 1 credit and opens this results batch. Empty or mostly repeated batches are free.'} Reopening unlocked results is free.</p><p>{session.balance??0} credits available.</p><button className="button full" disabled={busy||(session.balance??0)<nextBatchCost} onClick={unlock}>{busy?'Opening…':nextBatchCost===0?'Open batch · Free':'Open batch · 1 credit'}</button><Link href="/account/billing">Manage credits and subscription</Link></>:<><span className="unlock-icon"><LockKeyhole size={24}/></span><p className="eyebrow">YOUR FULL SPONSOR SHORTLIST</p><h2 id="unlock-title">More companies.<br/>More ways to reach out.</h2><ul className="unlock-benefits"><li><Check size={17}/>All remaining companies in this saved shortlist</li><li><Check size={17}/>Available company contacts and application routes</li><li><Check size={17}/>Reasons each company may fit, with source details</li></ul><div className="checkout-note"><strong>SponsorReach Monthly · US$24.99/month.</strong><p>A subscription provides 800 research credits each paid month. Visit billing to check subscription availability.</p></div><Link className="button full" href="/account/billing">View monthly subscription<ArrowRight size={18}/></Link></>}{error && <p className="error" role="alert">{error}</p>}</dialog>
  </section>;
}
