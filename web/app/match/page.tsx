import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { verifiedUser } from '@/lib/server';
import Link from 'next/link';
import { APPLICATIONS_CLOSED_MESSAGE } from '@/lib/applications';
export const metadata: Metadata = { title: 'Applications closed', description: APPLICATIONS_CLOSED_MESSAGE };
export default async function MatchPage({ searchParams }: { searchParams: Promise<{ shortlist?: string; new?: string }> }) {
  const query = await searchParams;
  const shortlist = query.shortlist && /^[a-f0-9-]{36}$/.test(query.shortlist) ? query.shortlist : undefined;
  if (await verifiedUser()) redirect(shortlist ? '/account?shortlist=' + shortlist + '&edit=1' : '/account?new=1');
  return <section className="section shell"><p className="eyebrow">APPLICATIONS CLOSED</p><h1>{APPLICATIONS_CLOSED_MESSAGE}</h1><p className="muted">Existing members can still sign in to access their saved shortlists.</p><Link href="/account" className="button">Sign in</Link></section>;
}
