'use client';
import EmailSignin from './email-signin';
import { SocialButtons, type SocialConfig } from './social-signin';
import {refreshCredits} from './dashboard-shell';
import { useState, useEffect, useRef } from 'react';
import Link from '@/components/navigation-link';
import { ArrowUpRight, ArrowRight, Mail, LockKeyhole, Check, Compass, X, Star } from 'lucide-react';
import { api, matchingContext, type EmployerCard, type MatchSession, type Profile, type LoadingContext, type ProfessionChoice } from '@/lib/types';
import { Card } from './employer-card';
import { ResultsSkeleton } from './skeletons';
import {DataRows} from './data-placeholder';
import {searchRequest} from '@/lib/search-request';
import ShortlistFilters from './shortlist-filters';
import PersonalizedLoader from '@/components/personalized-loader';

export type ShortlistView = { session: MatchSession; cards: EmployerCard[]; cursor: number | null };
export default function Results({ id, embedded = false, title, cache, externalStarred, onSessionChange, onBookmarkChange, knownStatus, pendingContext, newRun, onStartOver, social, wrongSignInEmail }: {
  id: string; social?: SocialConfig; wrongSignInEmail?: boolean; embedded?: boolean; title?: string; cache?: Map<string, ShortlistView>; externalStarred?: boolean;
  knownStatus?: string; pendingContext?: LoadingContext; newRun?: boolean; onStartOver?: () => void;
  onSessionChange?: (session: MatchSession) => void;
  onBookmarkChange?: (employer: EmployerCard, saved: boolean) => void;
}) {
  const cached = cache?.get(id);
  const [session, setSession] = useState<MatchSession | null>(cached?.session || null), [cards, setCards] = useState<EmployerCard[]>(cached?.cards || []), [error, setError] = useState(''), [modal, setModal] = useState(false), [busy, setBusy] = useState(false), [cursor, setCursor] = useState<number | null>(cached?.cursor ?? null);
  const [draft,setDraft]=useState<Profile>(),[choices,setChoices]=useState<ProfessionChoice[]>([]);
  const [submitting,setSubmitting]=useState(false);
  const refreshInFlight=useRef(false);
  const [confirmRefresh,setConfirmRefresh]=useState(false);
  const refreshDialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(confirmRefresh)refreshDialog.current?.showModal();else refreshDialog.current?.close();},[confirmRefresh]);
  const dialog = useRef<HTMLDialogElement>(null);
  const [refreshEpoch, setRefreshEpoch] = useState(0);
  const refreshKey = useRef<string | null>(null);
  const refreshPayload = useRef<string | undefined>(undefined);
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false, timer: ReturnType<typeof setTimeout>, failures = 0, received = false;
    async function poll() {
      try {
        const data = await api<MatchSession>('matches/' + id, { signal: controller.signal });
        if (cancelled) return;
        received = true; failures = 0; setSession(data); setError('');
        if (data.verification_required) { cache?.delete(id); setCards([]); timer = setTimeout(poll, 4000); return; }
        if (data.status === 'ready') {
          if(!onSessionChange)refreshCredits();
          const next = data.next_cursor !== undefined ? data.next_cursor : (data.access !== 'preview' && (data.total_count || 0) > (data.preview?.length || 0) ? data.preview?.length || null : null);
          setCards(data.preview || []); setCursor(next);
          cache?.set(id, { session: data, cards: data.preview || [], cursor: next });
        } else if (data.status === 'failed') setError('We couldn’t finish your sponsor shortlist. Please try again with a new search.');
        else timer = setTimeout(poll, 800);
        onSessionChange?.(data);
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
      const page=await api<{results:EmployerCard[];next_cursor:number|null}>(`matches/${id}/results${paid?'?cursor='+batch*5:''}`);
      const combined=paid&&batch>0?[...cards,...page.results.filter(c=>!cards.some(p=>p.employer_id===c.employer_id))]:page.results;
      refreshCredits();setSession(data);setCards(combined);setCursor(page.next_cursor);setModal(false);onSessionChange?.(data);
      cache?.set(id,{session:data,cards:combined,cursor:page.next_cursor});
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function more() {
    setBusy(true);
    try { const page = await api<{ results: EmployerCard[]; next_cursor: number | null }>(`matches/${id}/results?cursor=${cursor}`); setCards(c => { const combined = [...c, ...page.results.filter(result=>!c.some(card=>card.employer_id===result.employer_id))]; if (session) cache?.set(id, { session, cards: combined, cursor: page.next_cursor }); return combined; }); setCursor(page.next_cursor); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function refresh(profile?: Profile) {
    if (busy||refreshInFlight.current) return;
    if(session?.credit_mode&&!confirmRefresh&&!embedded){setConfirmRefresh(true);return;}
    refreshInFlight.current=true;
    setConfirmRefresh(false);setSubmitting(true);setError('');
    if(profile)setDraft(profile);
    const payloadKey=JSON.stringify(profile);
    if(refreshPayload.current!==payloadKey){refreshKey.current=null;refreshPayload.current=payloadKey;}
    refreshKey.current ||= crypto.randomUUID();
    try {
      const body=profile?searchRequest({profile,sourceSession:id,visaContext:session?.visa_context??null,creditConsent:true,idempotencyKey:refreshKey.current})
        :{idempotency_key:refreshKey.current,accept_credit_cost:!!session?.credit_mode};
      const result=await api<{session_id:string;status:string}>(`matches/${id}/refresh`, { method: 'POST', body: JSON.stringify(body) });
      if(result.session_id!==id)throw new Error('The service returned a different shortlist.');
      refreshKey.current=null;setDraft(undefined);setChoices([]);cache?.delete(id);
      if(session){
        const matching={...session,status:'queued',stage:'Understanding your career interests',loading_context:profile?matchingContext(profile):session.loading_context};
        setSession(matching);
        onSessionChange?.(matching);
      }
      setRefreshEpoch(value => value + 1);
    } catch (e) {
      const problem=e as Error&{choices?:ProfessionChoice[]};
      setChoices(problem.choices||[]);setError(problem.message);
    } finally {refreshInFlight.current=false;setSubmitting(false);}
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
  if(submitting)return <PersonalizedLoader context={draft?matchingContext(draft):session?.loading_context} error="" embedded={embedded}/>;
  if (!session) {
    if(error)return <div className="saved-results-error" role="alert"><h2>Couldn’t load the search</h2><p>{error}</p><button className="button secondary small" onClick={() => { setError(''); setRefreshEpoch(value => value + 1); }}>Try again</button></div>;
    if(newRun||knownStatus==='queued'||knownStatus==='processing')return <PersonalizedLoader context={pendingContext} error="" embedded={embedded}/>;
    return embedded ? <section className="embedded-results"><header className="research-detail-heading"><h2>{title||'Shortlist'}</h2></header><DataRows label="companies"/></section> : <ResultsSkeleton/>;
  }
  if (session.verification_required) return <section className="loader-page shell"><Mail size={48}/><p className="eyebrow">ONE LAST STEP</p><h1>Confirm your <em>email.</em></h1><p className="muted">Enter the code we emailed you to open your research.</p>{wrongSignInEmail && <p className="notice" role="status">That sign-in uses a different email from this shortlist. Try the original email or enter the code below.</p>}<EmailSignin key={id} sessionId={id} initialSent/>{social && <SocialButtons {...social} shortlist={id}/>}<Link className="text-button" href="/account">Use another account</Link></section>;
  if (['queued','processing'].includes(session.status)) return <PersonalizedLoader stage={session.stage} context={session.loading_context || pendingContext} error={error} embedded={embedded}/>;
  const filters = embedded&&!newRun&&session.profile&&<ShortlistFilters key={session.revision} profile={draft||session.profile} creditMode={session.credit_mode} onRefine={refresh} choices={choices} error={error}/>;
  if (!ready) return <section className="embedded-results"><header className="research-detail-heading"><h2>{session.status==='failed'?'Search couldn’t finish':'Your profile needs more detail'}</h2></header>{filters}<p className="muted">No credit was used for this search.</p>{onStartOver?<button className="button" onClick={onStartOver}>Start a new search</button>:!embedded&&<Link className="button" href={'/match?shortlist='+id}>Retry this shortlist</Link>}</section>;
  const unknown = cards.filter(c => c.location_section === 'unknown');
  const main = cards.filter(c => c.location_section !== 'unknown');
  const direct = main.filter(c => c.group === 'direct'), related = main.filter(c => c.group === 'related');
  const emptyMessage = session.empty_reason === 'location'
    ? 'No companies in this search had recorded evidence for your selected area. Edit your location preference to widen the search.'
    : session.empty_reason === 'eligibility'
      ? 'The companies retrieved did not meet our sponsor, identity or contact checks. You can refine the profile and search again.'
      : 'We couldn’t find enough evidence for this profession among the companies searched. Try a more specific role or choose to include related roles.';
  const empty = !(session.total_count||session.unknown_location_count);
  const companyCard = (company: EmployerCard) => <Card key={company.employer_id} employer={company} id={id}
    position={cards.indexOf(company)} compact={embedded} recent={!!session.revision&&company.added_revision===session.revision}
    onBookmarkChange={saved=>bookmarkChanged(company,saved)}/>;
  if(newRun){
    if(!empty)return <PersonalizedLoader context={session.loading_context||pendingContext} error="" embedded/>;
    return <div className="workspace-empty"><Compass size={32}/><h2>No matching companies</h2><p>{emptyMessage} No credit was used.</p><button className="button" onClick={onStartOver}>Start a new search</button></div>;
  }
  return <section className={embedded ? 'embedded-results' : 'results-shell shell'}>{embedded ?
    <><header className="research-detail-heading"><div><h2>{session.loading_context?.roles.join(' · ') || title || 'Sponsor shortlist'}</h2><p>{session.total_count || 0} matching {session.total_count===1?'company':'companies'}</p></div>
    <button className={`icon-button shortlist-star ${starred?'selected':''}`} disabled={busy} onClick={star} aria-pressed={!!starred} aria-label={starred?'Unstar shortlist':'Star shortlist'}><Star size={17} fill={starred?'currentColor':'none'}/></button></header>{filters}</>
    : <div className="results-heading"><div><h1>Your sponsor <em>shortlist.</em></h1><p className="muted">{session.total_count || 0} matching companies</p></div><Link href={"/match?shortlist=" + id} className="button secondary">Refine this shortlist <ArrowUpRight size={17}/></Link></div>}
    {session.refinement_empty&&<p className="notice" role="status">No additional companies found. No credit was used.</p>}
    {session.repeat_credit_saved && !session.refinement_empty && <p className="notice" role="status">No credit used for this search: more than half of these companies were already unlocked on your account.</p>}
    {session.is_demo && <div className="demo-banner"><Compass size={18}/><div><strong>Fictional sample shortlist</strong><span>These sample employers, contacts, and evidence are fictional. They show how your matching experience works.</span></div></div>}
    {session.error_code&&<p className="notice" role="status">Refinement couldn’t finish. Your saved companies are available and no credit was used.</p>}
    {!!direct.length && <><div className="section-label"><h2>Target roles</h2></div><div className="cards-grid">{direct.map(companyCard)}</div></>}
    {!!related.length && <><div className="section-label"><h2>Related roles</h2></div><div className="cards-grid">{related.map(companyCard)}</div></>}
    {empty && <div className="empty-state"><Compass size={32}/><h2>No matching companies</h2><p>{emptyMessage}</p></div>}
    {!!unknown.length && <details className="unknown-location-results"><summary>Companies with no recorded location ({unknown.length} shown)</summary><div className="cards-grid">{unknown.map(companyCard)}</div></details>}
    {!!session.locked_count && <div className="unlock-section"><div className="locked-grid" aria-hidden="true">{Array.from({ length: Math.min(3, session.locked_count) }).map((_, i) => <div className="locked-card" key={i}><div className="blur-content"><div className="fake-avatar"/><h3>A relevant sponsor company</h3><p>Reasons this company may fit</p><div className="fake-line"/><div className="fake-line short"/><span>Available outreach channels</span></div></div>)}</div><div className="unlock-callout"><span className="unlock-icon"><LockKeyhole size={22}/></span><h2>More relevant companies to reach.</h2><p>Unlock {session.locked_count} more sponsor {session.locked_count === 1 ? 'company' : 'companies'} from this saved shortlist, with available contacts and reasons each may fit.</p><button className="button" onClick={() => setModal(true)}>{session.credit_mode?(nextBatchCost===0?'Show more · Free':'Show more · 1 credit'):'Unlock my full sponsor shortlist'} <ArrowRight size={18}/></button><small>{session.credit_mode?'Up to 5 companies per newly opened batch. Reopening is free.':'Currently free · no payment details required'}</small></div></div>}
    {cursor !== null && <div className="load-more"><button className="button secondary" disabled={busy} onClick={more}>{busy ? 'Loading…' : session.credit_mode?'Show saved results · free':'Show more sponsor companies'}<ArrowRight size={17}/></button></div>}
    {!session.credit_mode&&session.access === 'demo_unlocked' && <div className="unlocked-notice"><Check size={17}/>Your full saved shortlist is unlocked. No payment was taken.</div>}
    {error && !filters && <p className="error" role="alert">{error}</p>}
    <dialog ref={refreshDialog} onCancel={()=>setConfirmRefresh(false)} aria-label="Run a new search" className="unlock-dialog"><p>Refining may use 1 credit. Empty or mostly repeated results are free.</p><button className="button small" disabled={busy||(session.balance??0)<1} onClick={()=>void refresh()}>Refine search</button><button className="text-button" onClick={()=>setConfirmRefresh(false)}>Keep this shortlist</button><Link href="/account/billing">Manage credits</Link></dialog>
    <dialog className="unlock-dialog" ref={dialog} onCancel={() => setModal(false)} aria-labelledby="unlock-title"><button className="dialog-close icon-button" aria-label="Close unlock window" onClick={() => setModal(false)}><X size={20}/></button>{session.credit_mode?<><span className="unlock-icon"><LockKeyhole size={24}/></span><p className="eyebrow">YOUR NEXT RESULTS BATCH</p><h2 id="unlock-title">Open up to 5 companies.</h2><p>{nextBatchCost===0?'This batch is free because more than half its companies are already unlocked on your account.':'This costs 1 credit and opens this results batch. Empty or mostly repeated batches are free.'} Reopening unlocked results is free.</p><p>{session.balance??0} credits available.</p><button className="button full" disabled={busy||(session.balance??0)<nextBatchCost} onClick={unlock}>{busy?'Opening…':nextBatchCost===0?'Open batch · Free':'Open batch · 1 credit'}</button><Link href="/account/billing">Manage credits and subscription</Link></>:<><span className="unlock-icon"><LockKeyhole size={24}/></span><p className="eyebrow">YOUR FULL SPONSOR SHORTLIST</p><h2 id="unlock-title">More companies.<br/>More ways to reach out.</h2><ul className="unlock-benefits"><li><Check size={17}/>All remaining companies in this saved shortlist</li><li><Check size={17}/>Available company contacts and application routes</li><li><Check size={17}/>Reasons each company may fit, with source details</li></ul><div className="checkout-note"><strong>SponsorReach Monthly · €24.99/month.</strong><p>A subscription provides 100 research credits each paid month. Visit billing to check subscription availability.</p></div><Link className="button full" href="/account/billing">View monthly subscription<ArrowRight size={18}/></Link></>}{error && <p className="error" role="alert">{error}</p>}</dialog>
  </section>;
}
