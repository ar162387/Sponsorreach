import Link from 'next/link';
import { ArrowLeft, ArrowUpRight } from 'lucide-react';
export default function NotFound() {
  return <section className="page-recovery shell"><p className="eyebrow">404 / A DIFFERENT DIRECTION</p><h1>This page is<br/><em>off the map.</em></h1><p>The address may have changed, or the page may no longer be available. Your next research step is still here.</p><div className="recovery-actions"><Link className="button" href="/match">Build my shortlist <ArrowUpRight size={18}/></Link><Link className="button secondary" href="/"><ArrowLeft size={16}/>Back to home</Link></div></section>;
}
