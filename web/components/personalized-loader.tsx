'use client';
import { useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import Link from '@/components/navigation-link';
import { ArrowRight, Pause, Play } from 'lucide-react';
import type { LoadingContext } from '@/lib/types';
import { loadingMessages, captionDuration } from '@/lib/personalization';

export default function PersonalizedLoader({ stage, context, error }: { stage?: string; context?: LoadingContext; error: string }) {
  const contextKey = JSON.stringify(context);
  // Polling returns new objects. Stable content keeps the caption timer alive.
  const messages = useMemo(() => loadingMessages(context), [contextKey]);
  const [index, setIndex] = useState(0), [paused, setPaused] = useState(false), [visible, setVisible] = useState(true);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)'); setPaused(media.matches);
    const change = (event: MediaQueryListEvent) => setPaused(event.matches);
    const visibility = () => setVisible(!document.hidden);
    visibility(); media.addEventListener('change', change); document.addEventListener('visibilitychange', visibility);
    return () => { media.removeEventListener('change', change); document.removeEventListener('visibilitychange', visibility); };
  }, []);
  useEffect(() => {
    if (paused || !visible || error) return;
    const timer = setTimeout(() => setIndex(value => (value + 1) % messages.length), captionDuration(messages[index % messages.length]));
    return () => clearTimeout(timer);
  }, [paused, visible, error, messages, index]);
  const heading = ({ 'Finding relevant sponsor employers': 'Finding relevant licensed sponsors', 'Checking professional relevance': 'Checking how company work fits your background', 'Ranking your shortlist': 'Organising your sponsor shortlist' } as Record<string, string>)[stage || ''] || stage || 'Understanding your background';
  return <section className="loader-page shell">
    <div className="loader-orbit" aria-hidden="true"><div className="loader-ring"/><div className="loader-ring second"/><Image src="/brand/sr-mark.png" width={76} height={68} alt=""/><span className="loader-point"/></div>
    <p className="eyebrow">YOUR BACKGROUND. YOUR SPONSOR SHORTLIST.</p>
    <h1 aria-live="polite" aria-atomic="true">{error ? 'Your sponsor search needs another attempt.' : heading}</h1>
    {error ? <p className="error" role="alert">{error}</p> : <>
      <div className="personal-loader-copy"><p className="muted rotating-message" aria-hidden="true" key={index}>{messages[index % messages.length]}</p><span className="sr-only">Your professional profile is being matched with employer evidence. The current stage is shown above.</span></div>
      <div className="loader-interest-chips" aria-label="Your target roles">{context?.roles.map(role => <span className="tag" key={role}>{role}</span>)}</div>
      <div className="loader-steps"><span className="status-dot"/>Your profile is saved. Matching continues in the background.</div>
      <button className="loader-pause text-button" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? <Play size={13}/> : <Pause size={13}/>}{paused ? 'Resume messages' : 'Pause messages'}</button>
    </>}
    {error && <Link href="/match" className="button">Start a new sponsor search<ArrowRight size={18}/></Link>}
    <Link href="/account" className="text-button">My sponsor shortlists</Link>
  </section>;
}
