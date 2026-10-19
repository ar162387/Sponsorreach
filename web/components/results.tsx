'use client';
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
      await api(`matches/${id}/demo-unlock`, { method: 'POST', body: '{}' });
      const data = await api<MatchSession>('matches/' + id);
      const next = data.next_cursor ?? (data.access !== 'preview' && (data.total_count || 0) > (data.preview?.length || 0) ? data.preview?.length || null : null);
      setSession(data); setCards(data.preview || []); setCursor(next); setModal(false); onSessionChange?.(data);
      cache?.set(id, { session: data, cards: data.preview || [], cursor: next });
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function more() {
    setBusy(true);
    try { const page = await api<{ results: EmployerCard[]; next_cursor: number | null }>(`matches/${id}/results?cursor=${cursor}`); setCards(c => { const combined = [...c, ...page.results]; if (session) cache?.set(id, { session, cards: combined, cursor: page.next_cursor }); return combined; }); setCursor(page.next_cursor); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function refresh() {
    if (busy) return;
    setBusy(true); setError('');
    refreshKey.current ||= crypto.randomUUID();
    try {
      await api(`matches/${id}/refresh`, { method: 'POST', body: JSON.stringify({ idempotency_key: refreshKey.current }) });
      refreshKey.current = null; cache?.delete(id); setCards([]); setCursor(null);
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
  if (!session) return error ? <div className="saved-results-error" role="alert"><h2>Let’s reconnect your shortlist.</h2><p>{error}</p><button className="button secondary small" onClick={() => { setError(''); setRefreshEpoch(value => value + 1); }}>Try loading again</button></div> : <ResultsSkeleton embedded={embedded}/>;
  if (session?.verification_required) return <section className="loader-page shell"><Mail size={48}/><p className="eyebrow">ONE LAST STEP</p><h1>Confirm your <em>email.</em></h1><p className="muted">Your shortlist is saved. Open the confirmation link we sent to see your free sponsor previews. Use this browser to connect the link to your pending shortlist.</p><p className="email-spam-note" role="note"><strong>Check your spam or junk folder too.</strong> If the email lands there, mark it as not spam so future sign-in links reach your inbox.</p><button className="button" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { const response=await fetch('/api/auth/magic-link',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:id})}); const result=await response.json(); if(!response.ok)throw new Error(result.error || 'Email could not be sent.'); setError('Confirmation email sent. Please check your inbox and spam folder.'); } catch(e){setError((e as Error).message);} finally {setBusy(false);} }}>Resend confirmation email</button>{error && <p role="status">{error}</p>}<Link className="text-button" href="/account">Already confirmed? Sign in</Link></section>;
  if (session?.status === 'failed') return <section className="loader-page shell"><Compass size={38}/><h1>Let’s try your shortlist again.</h1><p className="muted">Your profile and saved choices are safe. Retry the search or refine this shortlist.</p><button className="button" disabled={busy} onClick={refresh}><RefreshCw size={17}/>Retry this shortlist</button><>{onRefine ? <button className="text-button" onClick={() => onRefine(session)}>Refine this shortlist</button> : <Link className="text-link" href={"/match?shortlist=" + id}>Refine this shortlist</Link>}</>{error && <p className="error" role="alert">{error}</p>}</section>;
  if (!ready && !['queued', 'processing'].includes(session.status)) return <div className="saved-results-error"><h2>Your profile needs a little more detail.</h2><>{onRefine ? <button className="text-button" onClick={() => onRefine(session)}>Refine this shortlist</button> : <Link href={'/match?shortlist=' + id}>Refine this shortlist</Link>}</></div>;
  if (!ready) return <PersonalizedLoader stage={session?.stage} context={session?.loading_context} error={error}/>;
  const direct = cards.filter(c => c.group === 'direct'), related = cards.filter(c => c.group === 'related');
  return <section className={embedded ? 'embedded-results' : 'results-shell shell'}>{embedded ? <header className="research-detail-heading"><div><span className="workspace-kicker">SAVED SHORTLIST</span><h2>{title || session.loading_context?.roles.join(' · ') || 'Your sponsor shortlist'}</h2><p>{session.total_count || 0} relevant companies · {session.access === 'preview' ? 'Free preview' : 'Full shortlist unlocked'}</p>{session.loading_context && <details className="selected-profile-context"><summary>Profile context</summary><p>{session.loading_context.background}{session.loading_context.specialization && ' · ' + session.loading_context.specialization}</p><div>{session.loading_context.skills.map(skill => <span className="tag" key={skill}>{skill}</span>)}</div><p>{session.loading_context.locations.join(', ') || 'Anywhere in the UK'}</p></details>}</div><div className="research-detail-actions"><button className="button secondary small" disabled={!session.profile} onClick={() => onRefine?.(session)}>Refine profile</button></div></header> : <div className="results-heading"><div><p className="eyebrow"><span className="status-dot"/>RELEVANT COMPANIES. YOUR NEXT STEP.</p><h1>Your sponsor <em>shortlist.</em></h1><p className="muted">{session.total_count ? `${session.total_count} relevant sponsor ${session.total_count === 1 ? 'company' : 'companies'} to research and approach.` : 'We don’t yet have enough company evidence to recommend sponsors for this profile.'}</p></div><Link href={"/match?shortlist=" + id} className="button secondary">Refine this shortlist <ArrowUpRight size={17}/></Link></div>}
    {session.is_demo && <div className="demo-banner"><Compass size={18}/><div><strong>Demonstration shortlist</strong><span>These sample employers, contacts, and evidence are fictional. They show how your matching experience works.</span></div></div>}
    <div className="results-toolbar"><span>{session.access === 'preview' ? 'YOUR FREE PREVIEW' : 'YOUR SAVED SPONSOR SHORTLIST'}</span><div><button className="icon-button shortlist-refresh" disabled={busy} onClick={refresh} aria-label="Refresh companies in this shortlist" title="Run this profile against the latest company data">{busy ? <LoaderCircle size={17} className="spin"/> : <RefreshCw size={17}/>}</button><button className={`icon-button shortlist-star ${starred ? 'selected' : ''}`} disabled={busy} onClick={star} aria-pressed={!!starred} aria-label={starred ? 'Unstar shortlist' : 'Star shortlist'}><Star size={17} fill={starred ? 'currentColor' : 'none'}/></button><span className="tag">{session.direct_count || 0} direct</span>{!!session.related_count && <span className="tag">{session.related_count} related</span>}<span className="tiny muted">{embedded ? 'Company research & contact routes' : 'Relevant companies, with supporting sources'}</span></div></div>
    {!!direct.length && <><div className="section-label"><h2>Companies for your target roles</h2><span>Company work that connects with your background</span></div><div className="cards-grid">{direct.map(c => <Card key={c.employer_id} employer={c} id={id} position={cards.indexOf(c)} compact={embedded} onBookmarkChange={saved => bookmarkChanged(c, saved)}/>)}</div></>}
    {!!related.length && <><div className="section-label"><h2>Companies for related roles</h2><span>Alternative roles you chose to include</span></div><div className="cards-grid">{related.map(c => <Card key={c.employer_id} employer={c} id={id} position={cards.indexOf(c)} compact={embedded} onBookmarkChange={saved => bookmarkChanged(c, saved)}/>)}</div></>}
    {!cards.length && <div className="empty-state"><Compass size={38}/><h2>Let’s give your search more direction.</h2><p>There isn’t enough supported company information for this search yet. Try a more specific role, add your skills or responsibilities, or include related roles. This is about the information available, not your potential.</p><>{onRefine ? <button className="button" disabled={!session.profile} onClick={() => onRefine(session)}>Refine this shortlist<ArrowRight size={17}/></button> : <Link href={"/match?shortlist=" + id} className="button">Refine this shortlist<ArrowRight size={17}/></Link>}</></div>}
    {!!session.locked_count && <div className="unlock-section"><div className="locked-grid" aria-hidden="true">{Array.from({ length: Math.min(3, session.locked_count) }).map((_, i) => <div className="locked-card" key={i}><div className="blur-content"><div className="fake-avatar"/><h3>A relevant sponsor company</h3><p>Reasons this company may fit</p><div className="fake-line"/><div className="fake-line short"/><span>Available outreach channels</span></div></div>)}</div><div className="unlock-callout"><span className="unlock-icon"><LockKeyhole size={22}/></span><h2>More relevant companies to reach.</h2><p>Unlock {session.locked_count} more sponsor {session.locked_count === 1 ? 'company' : 'companies'} from this saved shortlist, with available contacts and reasons each may fit.</p><button className="button" onClick={() => setModal(true)}>Unlock my full sponsor shortlist <ArrowRight size={18}/></button><small>Demo unlock · no payment details or charge</small></div></div>}
    {cursor !== null && <div className="load-more"><button className="button secondary" disabled={busy} onClick={more}>{busy ? 'Loading…' : 'Show more sponsor companies'}<ArrowRight size={17}/></button></div>}
    {session.access === 'demo_unlocked' && <div className="unlocked-notice"><Check size={17}/>Your full saved shortlist is unlocked. No payment was taken.</div>}
    {error && <p className="error" role="alert">{error}</p>}<p className="qualification">Discover employers and use their official channels to explore opportunities.</p>
    <dialog className="unlock-dialog" ref={dialog} onCancel={() => setModal(false)} aria-labelledby="unlock-title"><button className="dialog-close icon-button" aria-label="Close unlock window" onClick={() => setModal(false)}><X size={20}/></button><span className="unlock-icon"><LockKeyhole size={24}/></span><p className="eyebrow">YOUR FULL SPONSOR SHORTLIST</p><h2 id="unlock-title">More companies.<br/>More ways to reach out.</h2><div className="price">£{session.demo_price_gbp}<span>Example one-time access price</span></div><ul className="unlock-benefits"><li><Check size={17}/>All remaining companies in this saved shortlist</li><li><Check size={17}/>Available company contacts and application routes</li><li><Check size={17}/>Reasons each company may fit, with source details</li></ul><div className="checkout-note"><strong>This is a demonstration checkout.</strong><p>No card details are requested. Continuing unlocks your shortlist without a charge.</p></div><button className="button full" disabled={busy} onClick={unlock}>{busy ? 'Unlocking…' : 'Unlock demo access'}<ArrowRight size={18}/></button>{error && <p className="error" role="alert">{error}</p>}</dialog>
  </section>;
}
