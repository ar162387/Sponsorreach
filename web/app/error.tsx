'use client';
import Link from 'next/link';
import { RotateCcw } from 'lucide-react';
export default function Error({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return <section className="page-recovery shell"><p className="eyebrow">LET’S TRY THAT AGAIN</p><h1>A pause in<br/><em>your research.</em></h1><p>This page couldn't finish loading. Try again, or return to your saved shortlists.</p><div className="recovery-actions"><button className="button" onClick={retry}>Try again <RotateCcw size={16}/></button><Link className="button secondary" href="/account">My shortlists</Link></div></section>;
}
