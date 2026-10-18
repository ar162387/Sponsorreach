'use client';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { ArrowUpRight, ArrowRight, MapPin, Mail, Phone, Link2, LockKeyhole, Check, Compass, X, ThumbsUp, Bookmark, BriefcaseBusiness, ShieldCheck, ExternalLink, Globe, ChevronDown, Sparkles } from 'lucide-react';
import { api, type EmployerCard, type MatchSession } from '@/lib/types';
import boardIcons from '@/lib/job-board-icons.json';
import PersonalizedLoader from '@/components/personalized-loader';

function date(value: string) { return new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); }
const labels: Record<string, string> = { website: 'Website', email: 'Email', phone: 'Phone', careers: 'Careers', linkedin_company: 'LinkedIn', linkedin_jobs: 'LinkedIn jobs', job_board: 'Job board', search_page: 'Search results', linkedin_person: 'LinkedIn profile' };
function routeKey(value: string) {
  try { const url = new URL(value); return url.hostname.toLowerCase().replace(/^www\./, '') + url.pathname.replace(/\/$/, '') + url.search; }
  catch { return value.trim().toLowerCase(); }
}
type Channel = EmployerCard['channels'][number];
function linkName(channel: Channel) {
  if (channel.kind.startsWith('linkedin')) return 'LinkedIn';
  if (channel.kind === 'website') return 'Website';
  if (channel.kind === 'careers') return 'Careers';
  return (channel.label || labels[channel.kind] || 'Other link').split(' · ')[0];
}
function BoardIcon({ name }: { name: string }) {
  const [failed, setFailed] = useState(false);
  const src = (boardIcons as Record<string, string>)[name];
  if (src && !failed) return <Image src={src} width={16} height={16} alt="" unoptimized onError={() => setFailed(true)}/>;
  return name === 'Website' ? <Globe size={15}/> : name === 'LinkedIn' ? <Link2 size={15}/> : <BriefcaseBusiness size={15}/>;
}
function Card({ employer, id, position }: { employer: EmployerCard; id: string; position: number }) {
  const [saved, setSaved] = useState(false), [helpful, setHelpful] = useState(false), [error, setError] = useState('');
  useEffect(() => { api('feedback', { method: 'POST', body: JSON.stringify({ session_id: id, employer_id: employer.employer_id, event: 'impression', position }) }).catch(() => {}); }, [id, employer.employer_id, position]);
  async function feedback(event: string) {
    try { await api('feedback', { method: 'POST', body: JSON.stringify({ session_id: id, employer_id: employer.employer_id, event, position }) }); if (event === 'save') setSaved(true); if (event === 'helpful') setHelpful(true); }
    catch { setError('Your feedback couldn’t be saved. Please try again.'); }
  }
  const direct = employer.channels.filter(c => c.kind === 'email' || c.kind === 'phone' || c.kind === 'address');
  const groups = new Map<string, Channel[]>();
  for (const channel of employer.channels.filter(c => !['email','phone','address'].includes(c.kind))) {
    const name = linkName(channel), items = groups.get(name) || [];
    if (!items.some(item => routeKey(item.value) === routeKey(channel.value))) items.push(channel);
    groups.set(name,items);
  }
  const websiteGroups = [...groups].filter(([name]) => ['Website','Careers','LinkedIn'].includes(name));
  const boardGroups = [...groups].filter(([name]) => !['Website','Careers','LinkedIn'].includes(name));
  function renderGroup([name, items]: [string, Channel[]]) {
    const title = (channel: Channel, index: number) => channel.kind === 'search_page' ? 'Search jobs' : channel.label?.includes('job link') ? 'Job listing' : channel.kind === 'linkedin_company' ? 'Company page' : channel.kind === 'linkedin_jobs' ? 'Jobs page' : channel.kind === 'linkedin_person' ? 'Profile' : items.length > 1 ? `Company link ${index + 1}` : name;
    if (items.length === 1) {
      const channel=items[0], content=<><BoardIcon name={name}/><span>{name}</span></>;
      return employer.is_demo || channel.linkable === false ? <span className="reach-route disabled" key={name}>{content}</span> : <a className="reach-route" key={name} href={channel.value} target="_blank" rel="noreferrer" onClick={() => feedback('channel_click')}>{content}</a>;
    }
    return <details className="reach-menu" key={name}><summary className="reach-route"><BoardIcon name={name}/><span>{name}</span><span className="route-count">{items.length}</span><ChevronDown size={12}/></summary><div className="reach-menu-panel">{items.map((channel,index) => employer.is_demo || channel.linkable === false ? <span key={channel.value}>{title(channel,index)}</span> : <a href={channel.value} key={channel.value} target="_blank" rel="noreferrer" onClick={() => feedback('channel_click')}>{title(channel,index)}<ArrowUpRight size={13}/></a>)}</div></details>;
  }
  return <article className="employer-card reach-card">
    <div className="reach-card-top"><span className="reach-licence"><ShieldCheck size={14}/>{employer.is_demo ? 'Sample sponsor' : 'Licensed sponsor'}</span><button className={`reach-save ${saved ? 'selected' : ''}`} aria-label={saved ? 'Employer saved' : `Save ${employer.name}`} onClick={() => feedback('save')}><Bookmark size={18} fill={saved ? 'currentColor' : 'none'}/></button></div>
    <div className="reach-identity"><h3>{employer.name}</h3><p><MapPin size={13}/>{employer.town || 'UK'}</p></div>
    <div className="reach-fit"><span><Sparkles size={14}/>Why it fits</span><p>{employer.explanation.summary || employer.explanation.text.replace(/^Published business activity:\s*/, '').split(' This aligns with your interest in ')[0]}</p></div>
    {!!direct.length && <div className="reach-contacts">{direct.map(channel => {
      const href = channel.kind === 'address' ? '' : channel.kind === 'email' ? 'mailto:' + channel.value : 'tel:' + channel.value.replace(/[^+\d]/g, '');
      const content=<>{channel.kind === 'email' ? <Mail size={15}/> : channel.kind === 'address' ? <MapPin size={15}/> : <Phone size={15}/>}<span>{channel.value}</span>{channel.kind !== 'address' && <ArrowUpRight size={13}/>}</>;
      return employer.is_demo || channel.kind === 'address' || channel.linkable === false ? <span className="reach-direct disabled" key={channel.kind + channel.value}>{content}</span> : <a className="reach-direct" key={href} href={href} onClick={() => feedback('channel_click')}>{content}</a>;
    })}</div>}
    {!!websiteGroups.length && <div className="reach-route-row">{websiteGroups.map(renderGroup)}</div>}
    {!!boardGroups.length && <div className="reach-job-boards"><span className="reach-section-label">EXPLORE JOB BOARDS</span><div className="reach-route-row">{boardGroups.map(renderGroup)}</div></div>}
    {!!employer.verified_open_vacancies.length && <div className="reach-openings">{employer.verified_open_vacancies.filter(v => !employer.channels.some(c => routeKey(c.value) === routeKey(v.url))).map(v => <a href={v.url} key={v.url} target="_blank" rel="noreferrer"><BriefcaseBusiness size={14}/>{v.title}<ArrowUpRight size={13}/></a>)}</div>}
    <div className="reach-feedback"><button className={helpful ? 'selected' : ''} onClick={() => feedback('helpful')}><ThumbsUp size={14}/>{helpful ? 'Thanks!' : 'Relevant to me'}</button><button onClick={() => feedback('not_relevant')}>Not relevant</button></div>{error && <p className="error" role="alert">{error}</p>}
  </article>;
}

export default function Results({ id }: { id: string }) {
  const [session, setSession] = useState<MatchSession | null>(null), [cards, setCards] = useState<EmployerCard[]>([]), [error, setError] = useState(''), [modal, setModal] = useState(false), [busy, setBusy] = useState(false), [cursor, setCursor] = useState<number | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    let cancelled = false, timer: ReturnType<typeof setTimeout>, failures = 0;
    async function poll() {
      try {
        const data = await api<MatchSession>('matches/' + id);
        if (cancelled) return;
        failures = 0; setSession(data); setError('');
        if (data.verification_required) { timer = setTimeout(poll, 4000); return; }
        if (data.status === 'ready') {
          const page = await api<{ results: EmployerCard[]; next_cursor: number | null }>(`matches/${id}/results`);
          if (!cancelled) { setCards(page.results); setCursor(page.next_cursor); }
        } else if (data.status === 'failed') setError('We couldn’t finish your sponsor shortlist. Please try again with a new search.');
        else timer = setTimeout(poll, 800);
      } catch (e) {
        if (!cancelled) { failures++; if (failures < 4) timer = setTimeout(poll, 2000); else setError((e as Error).message); }
      }
    }
    poll(); return () => { cancelled = true; clearTimeout(timer); };
  }, [id]);
  useEffect(() => { if (modal) dialog.current?.showModal(); else dialog.current?.close(); }, [modal]);
  async function unlock() {
    setBusy(true); setError('');
    try {
      await api(`matches/${id}/demo-unlock`, { method: 'POST', body: '{}' });
      const data = await api<MatchSession>('matches/' + id);
      const page = await api<{ results: EmployerCard[]; next_cursor: number | null }>(`matches/${id}/results`);
      setSession(data); setCards(page.results); setCursor(page.next_cursor); setModal(false);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function more() {
    setBusy(true);
    try { const page = await api<{ results: EmployerCard[]; next_cursor: number | null }>(`matches/${id}/results?cursor=${cursor}`); setCards(c => [...c, ...page.results]); setCursor(page.next_cursor); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  const ready = session?.status === 'ready';
  if (session?.verification_required) return <section className="loader-page shell"><Mail size={48}/><p className="eyebrow">ONE LAST STEP</p><h1>Confirm your <em>email.</em></h1><p className="muted">Your shortlist is saved. Open the confirmation link we sent to see your free sponsor previews. Use this browser to connect the link to your pending shortlist.</p><p className="email-spam-note" role="note"><strong>Check your spam or junk folder too.</strong> If the email lands there, mark it as not spam so future sign-in links reach your inbox.</p><button className="button" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { const response=await fetch('/api/auth/magic-link',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:id})}); const result=await response.json(); if(!response.ok)throw new Error(result.error || 'Email could not be sent.'); setError('Confirmation email sent. Please check your inbox and spam folder.'); } catch(e){setError((e as Error).message);} finally {setBusy(false);} }}>Resend confirmation email</button>{error && <p role="status">{error}</p>}<Link className="text-button" href="/account">Already confirmed? Sign in</Link></section>;
  if (!ready) return <PersonalizedLoader stage={session?.stage} context={session?.loading_context} error={error}/>;
  const direct = cards.filter(c => c.group === 'direct'), related = cards.filter(c => c.group === 'related');
  return <section className="results-shell shell"><div className="results-heading"><div><p className="eyebrow"><span className="status-dot"/>RELEVANT COMPANIES. YOUR NEXT STEP.</p><h1>Your sponsor <em>shortlist.</em></h1><p className="muted">{session.total_count ? `${session.total_count} relevant sponsor ${session.total_count === 1 ? 'company' : 'companies'} to research and approach.` : 'We don’t yet have enough company evidence to recommend sponsors for this profile.'}</p></div><Link href="/match" className="button secondary">Refine my profile <ArrowUpRight size={17}/></Link></div>
    {session.is_demo && <div className="demo-banner"><Compass size={18}/><div><strong>Demonstration shortlist</strong><span>These sample employers, contacts, and evidence are fictional. They show how your matching experience works.</span></div></div>}
    <div className="results-toolbar"><span>{session.access === 'preview' ? 'YOUR FREE PREVIEW' : 'YOUR SAVED SPONSOR SHORTLIST'}</span><div><span className="tag">{session.direct_count || 0} direct</span>{!!session.related_count && <span className="tag">{session.related_count} related</span>}<span className="tiny muted">Relevant companies, with supporting sources</span></div></div>
    {!!direct.length && <><div className="section-label"><h2>Companies for your target roles</h2><span>Company work that connects with your background</span></div><div className="cards-grid">{direct.map(c => <Card key={c.employer_id} employer={c} id={id} position={cards.indexOf(c)}/>)}</div></>}
    {!!related.length && <><div className="section-label"><h2>Companies for related roles</h2><span>Alternative roles you chose to include</span></div><div className="cards-grid">{related.map(c => <Card key={c.employer_id} employer={c} id={id} position={cards.indexOf(c)}/>)}</div></>}
    {!cards.length && <div className="empty-state"><Compass size={38}/><h2>Let’s give your search more direction.</h2><p>There isn’t enough supported company information for this search yet. Try a more specific role, add your skills or responsibilities, or include related roles. This is about the information available, not your potential.</p><Link href="/match" className="button">Refine my profile <ArrowRight size={17}/></Link></div>}
    {!!session.locked_count && <div className="unlock-section"><div className="locked-grid" aria-hidden="true">{Array.from({ length: Math.min(3, session.locked_count) }).map((_, i) => <div className="locked-card" key={i}><div className="blur-content"><div className="fake-avatar"/><h3>A relevant sponsor company</h3><p>Reasons this company may fit</p><div className="fake-line"/><div className="fake-line short"/><span>Available outreach channels</span></div></div>)}</div><div className="unlock-callout"><span className="unlock-icon"><LockKeyhole size={22}/></span><h2>More relevant companies to reach.</h2><p>Unlock {session.locked_count} more sponsor {session.locked_count === 1 ? 'company' : 'companies'} from this saved shortlist, with available contacts and reasons each may fit.</p><button className="button" onClick={() => setModal(true)}>Unlock my full sponsor shortlist <ArrowRight size={18}/></button><small>Demo unlock · no payment details or charge</small></div></div>}
    {cursor !== null && <div className="load-more"><button className="button secondary" disabled={busy} onClick={more}>{busy ? 'Loading…' : 'Show more sponsor companies'}<ArrowRight size={17}/></button></div>}
    {session.access === 'demo_unlocked' && <div className="unlocked-notice"><Check size={17}/>Your full saved shortlist is unlocked. No payment was taken.</div>}
    {error && <p className="error" role="alert">{error}</p>}<p className="qualification">Discover employers and use their official channels to explore opportunities.</p>
    <dialog className="unlock-dialog" ref={dialog} onCancel={() => setModal(false)} aria-labelledby="unlock-title"><button className="dialog-close icon-button" aria-label="Close unlock window" onClick={() => setModal(false)}><X size={20}/></button><span className="unlock-icon"><LockKeyhole size={24}/></span><p className="eyebrow">YOUR FULL SPONSOR SHORTLIST</p><h2 id="unlock-title">More companies.<br/>More ways to reach out.</h2><div className="price">£{session.demo_price_gbp}<span>Example one-time access price</span></div><ul className="unlock-benefits"><li><Check size={17}/>All remaining companies in this saved shortlist</li><li><Check size={17}/>Available company contacts and application routes</li><li><Check size={17}/>Reasons each company may fit, with source details</li></ul><div className="checkout-note"><strong>This is a demonstration checkout.</strong><p>No card details are requested. Continuing unlocks your shortlist without a charge.</p></div><button className="button full" disabled={busy} onClick={unlock}>{busy ? 'Unlocking…' : 'Unlock demo access'}<ArrowRight size={18}/></button>{error && <p className="error" role="alert">{error}</p>}</dialog>
  </section>;
}
