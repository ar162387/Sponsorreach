'use client';
import { useState, useEffect } from 'react';
import Link from '@/components/navigation-link';
import Image from 'next/image';
import { ArrowUpRight, MapPin, Mail, Phone, Link2, ThumbsUp, Bookmark, BriefcaseBusiness, ShieldCheck, Globe, ChevronDown, Sparkles, LoaderCircle } from 'lucide-react';
import { api, type EmployerCard } from '@/lib/types';
import boardIcons from '@/lib/job-board-icons.json';

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
export function Card({ employer, id, position, dashboard = false, compact = false, onBookmarkChange, onOpenShortlist }: { employer: EmployerCard; id: string; position: number; dashboard?: boolean; compact?: boolean; onOpenShortlist?: (id: string) => void; onBookmarkChange?: (saved: boolean) => void }) {
  const [saved, setSaved] = useState(!!employer.bookmarked), [helpful, setHelpful] = useState(false), [error, setError] = useState('');
  useEffect(() => { if (dashboard) return; api('feedback', { method: 'POST', body: JSON.stringify({ session_id: id, employer_id: employer.employer_id, event: 'impression', position }) }).catch(() => {}); }, [id, employer.employer_id, position, dashboard]);
  async function feedback(event: string) {
    try { await api('feedback', { method: 'POST', body: JSON.stringify({ session_id: id, employer_id: employer.employer_id, event, position }) }); if (event === 'save') setSaved(true); if (event === 'helpful') setHelpful(true); }
    catch { setError('Your feedback couldn’t be saved. Please try again.'); }
  }
  const [saving, setSaving] = useState(false), [expanded, setExpanded] = useState(false);
  useEffect(() => { setSaved(!!employer.bookmarked); }, [employer.bookmarked]);
  async function toggleBookmark() {
    if (saving) return;
    const previous = saved; setSaved(!previous); onBookmarkChange?.(!previous);
    setSaving(true); setError('');
    try {
      const result = await api<{ bookmarked: boolean }>(dashboard ? `account/bookmarks/${employer.employer_id}` : `matches/${id}/bookmarks/${employer.employer_id}`, { method: 'POST', body: JSON.stringify({ saved: !previous }) });
      setSaved(result.bookmarked); if (result.bookmarked !== !previous) onBookmarkChange?.(result.bookmarked);
    } catch (e) { setSaved(previous); onBookmarkChange?.(previous); setError('Bookmark could not be saved. Your previous choice has been restored.'); } finally { setSaving(false); }
  }
  const direct = employer.channels.filter(c => c.kind === 'email' || c.kind === 'phone' || c.kind === 'address');
  const shownDirect = compact && !expanded ? direct.filter((channel, index) => channel.kind !== 'address' && direct.findIndex(item => item.kind === channel.kind) === index) : direct;
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
  return <article className={`employer-card reach-card ${compact ? 'compact-company' : ''} ${expanded ? 'expanded' : ''}`}>
    <div className="reach-card-top"><span className="reach-licence"><ShieldCheck size={14}/>{employer.is_demo ? 'Sample sponsor' : 'Licensed sponsor'}</span><button className={`reach-save ${saved ? 'selected' : ''}`} disabled={saving} aria-busy={saving} aria-pressed={saved} aria-label={saved ? `Remove bookmark for ${employer.name}` : `Bookmark ${employer.name}`} onClick={toggleBookmark}>{saving ? <LoaderCircle size={17} className="spin"/> : <Bookmark size={18} fill={saved ? 'currentColor' : 'none'}/>} </button></div>
    <div className="reach-identity"><h3>{employer.name}</h3><p><MapPin size={13}/>{employer.town || 'UK'}</p></div>
    <div className="reach-fit"><span><Sparkles size={14}/>Why it fits</span><p>{employer.explanation.summary || employer.explanation.text.replace(/^Published business activity:\s*/, '').split(' This aligns with your interest in ')[0]}</p></div>
    {!!shownDirect.length && <div className="reach-contacts">{shownDirect.map(channel => {
      const href = channel.kind === 'address' ? '' : channel.kind === 'email' ? 'mailto:' + channel.value : 'tel:' + channel.value.replace(/[^+\d]/g, '');
      const content=<>{channel.kind === 'email' ? <Mail size={15}/> : channel.kind === 'address' ? <MapPin size={15}/> : <Phone size={15}/>}<span>{channel.value}</span>{channel.kind !== 'address' && <ArrowUpRight size={13}/>}</>;
      return employer.is_demo || channel.kind === 'address' || channel.linkable === false ? <span className="reach-direct disabled" key={channel.kind + channel.value}>{content}</span> : <a className="reach-direct" key={href} href={href} onClick={() => feedback('channel_click')}>{content}</a>;
    })}</div>}
    {!!websiteGroups.length && <div className="reach-route-row">{websiteGroups.map(renderGroup)}</div>}
    {(!compact || expanded) && !!boardGroups.length && <div className="reach-job-boards"><span className="reach-section-label">EXPLORE JOB BOARDS</span><div className="reach-route-row">{boardGroups.map(renderGroup)}</div></div>}
    {(!compact || expanded) && !!employer.verified_open_vacancies.length && <div className="reach-openings">{employer.verified_open_vacancies.filter(v => !employer.channels.some(c => routeKey(c.value) === routeKey(v.url))).map(v => <a href={v.url} key={v.url} target="_blank" rel="noreferrer"><BriefcaseBusiness size={14}/>{v.title}<ArrowUpRight size={13}/></a>)}</div>}
    {compact && <button type="button" className="company-reveal" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Show less' : 'Reveal further details'}<ChevronDown size={14}/></button>}
    {!dashboard && <div className="reach-feedback"><button className={helpful ? 'selected' : ''} onClick={() => feedback('helpful')}><ThumbsUp size={14}/>{helpful ? 'Thanks!' : 'Relevant to me'}</button><button onClick={() => feedback('not_relevant')}>Not relevant</button></div>}{dashboard && employer.session_id && <button className="text-button bookmark-source" onClick={() => onOpenShortlist?.(employer.session_id!)}>Open shortlist<ArrowUpRight size={14}/></button>}{error && <p className="error" role="alert">{error}</p>}
  </article>;
}

